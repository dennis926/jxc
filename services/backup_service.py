import os
import time
import shutil
import zipfile
import smtplib
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from flask import current_app
from models import db
from models.email_config import EmailConfig
from models.email_template import EmailTemplate
from models.backup_history import BackupHistory
from models.system_config import SystemConfig


class _Paths:
    """统一管理路径，优先从 Flask 配置获取"""

    @staticmethod
    def _project_root():
        """获取项目根目录：优先使用 current_app，否则从 __file__ 推断"""
        try:
            if current_app:
                # Flask SQLAlchemy 的 URI 格式是 sqlite:///absolute/path
                uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
                if uri.startswith('sqlite:///'):
                    db_file = uri[len('sqlite:///'):]
                    return os.path.dirname(os.path.abspath(db_file))
        except Exception:
            pass
        return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    @staticmethod
    def db_path():
        root = _Paths._project_root()
        return os.path.join(root, 'inventory.db')

    @staticmethod
    def backups_dir():
        root = _Paths._project_root()
        d = os.path.join(root, 'backups')
        os.makedirs(d, exist_ok=True)
        return d

class BackupService:
    @staticmethod
    def format_file_size(size_bytes):
        """格式化文件大小"""
        if not size_bytes:
            return '0 B'
        if size_bytes < 1024:
            return f'{size_bytes} B'
        elif size_bytes < 1024 * 1024:
            return f'{size_bytes / 1024:.2f} KB'
        else:
            return f'{size_bytes / (1024 * 1024):.2f} MB'

    @staticmethod
    def get_template_variables(filename='未知', file_size=0, backup_type='manual', trigger_type='手动触发'):
        """获取模板渲染所需的变量"""
        now = datetime.now()

        # 获取备份统计信息
        total_count = BackupHistory.query.count()
        success_count = BackupHistory.query.filter_by(status='success').count()
        failed_count = BackupHistory.query.filter_by(status='failed').count()
        email_sent_count = BackupHistory.query.filter_by(sent_to_email=True).count()

        # 上次备份信息
        last_backup = BackupHistory.query.order_by(BackupHistory.created_at.desc()).first()
        last_backup_time = last_backup.created_at.strftime('%Y-%m-%d %H:%M:%S') if last_backup else '暂无'
        last_backup_status = '成功' if last_backup and last_backup.status == 'success' else ('失败' if last_backup else '暂无')

        # 系统名称
        try:
            site_name_config = SystemConfig.query.filter_by(config_key='site_name').first()
            system_name = site_name_config.config_value if site_name_config and site_name_config.config_value else '进销存管理系统'
        except Exception:
            system_name = '进销存管理系统'

        # 备份类型显示文本
        backup_type_text = '自动备份' if backup_type == 'auto' else '手动备份'

        variables = {
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
            'send_time': now.strftime('%Y-%m-%d %H:%M:%S'),
            'filename': filename,
            'file_size': BackupService.format_file_size(file_size),
            'file_size_bytes': file_size,
            'backup_type': backup_type_text,
            'trigger_type': trigger_type,
            'total_count': total_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'email_sent_count': email_sent_count,
            'last_backup_time': last_backup_time,
            'last_backup_status': last_backup_status,
            'system_name': system_name,
            'user_name': '管理员',
            'year': now.strftime('%Y'),
            'month': now.strftime('%m'),
            'day': now.strftime('%d'),
        }
        return variables

    @staticmethod
    def render_template(template_text, variables):
        """渲染模板，替换变量"""
        if not template_text:
            return template_text
        result = template_text
        for key, value in variables.items():
            # 支持 {key} 和 {{key}} 两种格式
            result = result.replace('{' + key + '}', str(value))
            result = result.replace('{{' + key + '}}', str(value))
        return result

    @staticmethod
    def _cleanup_files(*paths):
        """清理备份过程中的残留文件（校验失败时调用）

        校验不通过的产物必须删掉：留在 backups 目录里会被
        list_backup_files() 列出来，让人误以为是一份可用的备份。
        """
        for p in paths:
            if not p:
                continue
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception as e:
                print(f'[Backup] 清理残留文件失败 {p}: {e}')

    # 备份体积下限：低于此值几乎不可能是一个含完整业务表的库，
    # 用于拦截"空库/被截断"的产物（历史上出现过只有 22KB 的残缺包）。
    MIN_DB_BYTES = 32 * 1024

    # 备份必须包含的核心业务表，缺任一张即视为不完整
    REQUIRED_TABLES = (
        'users', 'products', 'warehouses', 'inventory', 'stock_transactions',
    )

    @staticmethod
    def validate_backup_db(db_file, source_size=None):
        """校验备份出来的 .db 是否完整可用

        依次检查：
          1. 文件存在且体积不低于 MIN_DB_BYTES
          2. 相对源库没有异常缩水（低于源库 50% 判为可疑）
          3. PRAGMA integrity_check 通过
          4. 核心业务表齐全
          5. users 表可读且至少有一条记录（能真正读到数据页）

        Returns: (ok: bool, error: str|None, info: dict)
        """
        info = {}
        try:
            if not os.path.exists(db_file):
                return False, '备份文件未生成', info

            size = os.path.getsize(db_file)
            info['size'] = size

            if size < BackupService.MIN_DB_BYTES:
                return False, (
                    f'备份文件过小（{BackupService.format_file_size(size)}），'
                    f'疑似空库或写入被中断'
                ), info

            if source_size and size < source_size * 0.5:
                return False, (
                    f'备份文件明显小于源库'
                    f'（备份 {BackupService.format_file_size(size)} / '
                    f'源库 {BackupService.format_file_size(source_size)}），疑似不完整'
                ), info

            conn = sqlite3.connect(db_file, timeout=30)
            try:
                integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
                info['integrity'] = integrity
                if integrity != 'ok':
                    return False, f'数据库完整性校验失败: {integrity}', info

                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
                tables = {r[0] for r in rows}
                info['table_count'] = len(tables)

                missing = [t for t in BackupService.REQUIRED_TABLES if t not in tables]
                if missing:
                    return False, f'备份缺少核心数据表: {", ".join(missing)}', info

                user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
                info['user_count'] = user_count
                if user_count < 1:
                    return False, '备份中用户表为空，疑似备份到了空库', info
            finally:
                conn.close()

            return True, None, info
        except sqlite3.Error as e:
            return False, f'备份文件无法作为 SQLite 数据库读取: {e}', info
        except Exception as e:
            return False, f'备份校验出错: {e}', info

    @staticmethod
    def validate_backup_zip(zip_file, expected_db_size=None):
        """校验压缩包本身可读、未截断，且内含的 .db 尺寸与预期一致

        Returns: (ok: bool, error: str|None, info: dict)
        """
        info = {}
        try:
            if not os.path.exists(zip_file):
                return False, '压缩包未生成', info

            info['zip_size'] = os.path.getsize(zip_file)

            with zipfile.ZipFile(zip_file, 'r') as zf:
                bad = zf.testzip()
                if bad:
                    return False, f'压缩包内文件损坏: {bad}', info

                db_entries = [i for i in zf.infolist() if i.filename.endswith('.db')]
                if not db_entries:
                    return False, '压缩包内未找到 .db 数据库文件', info

                entry = db_entries[0]
                info['entry_name'] = entry.filename
                info['entry_size'] = entry.file_size

                if expected_db_size and entry.file_size != expected_db_size:
                    return False, (
                        f'压缩包内数据库尺寸与备份不一致'
                        f'（包内 {entry.file_size} / 预期 {expected_db_size}）'
                    ), info

            return True, None, info
        except zipfile.BadZipFile as e:
            return False, f'压缩包无法读取，可能写入被中断: {e}', info
        except Exception as e:
            return False, f'压缩包校验出错: {e}', info

    @staticmethod
    def create_backup():
        """创建数据库备份（使用SQLite .backup命令确保一致性）

        备份产出后会经过两级校验（数据库完整性 + 压缩包完整性），
        任一级失败都返回 success=False 并清理残留文件，
        确保不会把残缺的包记入历史或发送到邮箱。
        """
        try:
            # 备份文件名
            # 中间产物 .db 带上 pid + 微秒后缀：即使有多个进程/线程在同一秒
            # 触发备份，也不会算出同一个中间文件名而互相覆盖、截断。
            # 对外可见的 zip 名保持原有格式，不影响已有的下载/恢复逻辑。
            now = datetime.now()
            timestamp = now.strftime('%Y%m%d_%H%M%S')
            unique_suffix = f'{os.getpid()}_{now.microsecond:06d}'
            backup_filename = f'inventory_backup_{timestamp}.db'
            temp_db_filename = f'.tmp_inventory_backup_{timestamp}_{unique_suffix}.db'
            zip_filename = f'inventory_backup_{timestamp}.zip'

            # 统一的路径管理（优先从 SQLALCHEMY_DATABASE_URI 解析，避免 cwd 不固定导致路径问题）
            db_path = _Paths.db_path()
            backups_dir = _Paths.backups_dir()
            backup_path = os.path.join(backups_dir, temp_db_filename)
            zip_path = os.path.join(backups_dir, zip_filename)

            # 检查源数据库文件是否存在
            if not os.path.exists(db_path):
                return {
                    'success': False,
                    'error': f'数据库文件不存在: {db_path}'
                }

            # 确保备份目录存在
            os.makedirs(backups_dir, exist_ok=True)

            # 使用SQLite .backup命令创建一致性备份
            # 这比直接复制文件更安全，即使数据库正在写入也能得到完整一致的备份
            try:
                source_conn = sqlite3.connect(db_path, timeout=30)
                backup_conn = sqlite3.connect(backup_path)

                # 使用SQLite的backup API
                with backup_conn:
                    source_conn.backup(backup_conn, pages=0, progress=None)

                source_conn.close()
                backup_conn.close()
            except sqlite3.Error as e:
                # 如果backup API失败，回退到直接复制（带重试）
                print(f"SQLite backup API failed: {e}, falling back to copy")
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                shutil.copy2(db_path, backup_path)

            # 第一级校验：压缩之前先确认备份出来的库是完整可用的，
            # 避免把空库/半截库打包发走
            source_size = os.path.getsize(db_path)
            ok, err, db_info = BackupService.validate_backup_db(backup_path, source_size)
            if not ok:
                BackupService._cleanup_files(backup_path, zip_path)
                return {'success': False, 'error': f'备份校验未通过：{err}'}

            backup_db_size = db_info.get('size')

            # 压缩备份文件
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(backup_path, backup_filename)

            # 第二级校验：确认压缩包可读、内含库尺寸与刚校验过的一致
            ok, err, zip_info = BackupService.validate_backup_zip(zip_path, backup_db_size)
            if not ok:
                BackupService._cleanup_files(backup_path, zip_path)
                return {'success': False, 'error': f'压缩包校验未通过：{err}'}

            # 删除未压缩的备份文件
            try:
                os.remove(backup_path)
            except:
                pass

            # 获取文件大小
            if not os.path.exists(zip_path):
                return {
                    'success': False,
                    'error': f'压缩后的备份文件不存在: {zip_path}'
                }
            file_size = os.path.getsize(zip_path)

            return {
                'success': True,
                'filename': zip_filename,
                'filepath': zip_path,
                'file_size': file_size,
                # 校验结果一并返回，便于日志/历史记录追溯
                'verified': True,
                'db_size': backup_db_size,
                'table_count': db_info.get('table_count'),
            }
        except Exception as e:
            import traceback
            print(f"[Backup] create_backup error: {e}")
            print(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }

    @staticmethod
    def restore_backup(backup_path):
        """从备份文件恢复数据库"""
        try:
            db_path = _Paths.db_path()

            # 检查备份文件是否存在
            if not os.path.exists(backup_path):
                return {'success': False, 'error': '备份文件不存在'}

            # 检查文件大小是否合理（至少1KB）
            file_size = os.path.getsize(backup_path)
            if file_size < 1024:
                return {'success': False, 'error': '备份文件过小，可能已损坏'}

            # 先验证备份文件是否是有效的SQLite数据库
            try:
                test_conn = sqlite3.connect(backup_path)
                cursor = test_conn.cursor()
                # 尝试查询一些基本表来验证完整性
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 5")
                tables = cursor.fetchall()
                test_conn.close()

                if len(tables) == 0:
                    return {'success': False, 'error': '备份文件不包含有效数据表'}
            except sqlite3.Error as e:
                return {'success': False, 'error': f'备份文件不是有效的SQLite数据库: {str(e)}'}

            # 创建当前数据库的临时备份（以防恢复失败）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_backup = f'{db_path}.auto_backup_{timestamp}'
            try:
                if os.path.exists(db_path):
                    shutil.copy2(db_path, temp_backup)
            except Exception as e:
                return {'success': False, 'error': f'创建临时备份失败: {str(e)}'}

            try:
                # 停止所有数据库连接
                db.session.remove()

                # 替换数据库文件
                shutil.copy2(backup_path, db_path)

                # 删除临时备份（恢复成功）
                if os.path.exists(temp_backup):
                    os.remove(temp_backup)

                return {'success': True, 'message': '数据库恢复成功'}

            except Exception as e:
                # 恢复失败，回滚到原数据库
                try:
                    if os.path.exists(temp_backup):
                        shutil.copy2(temp_backup, db_path)
                        os.remove(temp_backup)
                except:
                    pass
                return {'success': False, 'error': f'恢复失败，已回滚到原数据库: {str(e)}'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def send_backup_email(filepath, filename, template_id=None, trigger_type='手动触发', backup_type='manual'):
        """发送备份文件到邮箱"""
        try:
            config = EmailConfig.query.filter_by(is_active=True).first()
            if not config:
                return {'success': False, 'error': '未配置邮箱'}

            # 发送前再校验一次附件：即使 create_backup 已经验过，
            # 文件在落盘到发信之间仍可能被其他进程覆盖或截断。
            # 校验不通过就不发，避免把残缺包（历史上出现过 22KB）寄出去。
            ok, err, zip_info = BackupService.validate_backup_zip(filepath)
            if not ok:
                return {'success': False, 'error': f'附件校验未通过，已取消发送：{err}'}

            # 获取文件大小
            file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0

            # 获取模板
            template = None
            if template_id:
                template = EmailTemplate.query.get(template_id)
            if not template and config.selected_template_id:
                template = EmailTemplate.query.get(config.selected_template_id)
            if not template:
                # 使用第一个可用的内置模板
                template = EmailTemplate.query.filter_by(is_builtin=True, is_active=True).order_by(EmailTemplate.sort_order).first()

            # 获取变量并渲染模板
            variables = BackupService.get_template_variables(
                filename=filename,
                file_size=file_size,
                backup_type=backup_type,
                trigger_type=trigger_type
            )

            if template:
                subject = BackupService.render_template(template.subject, variables)
                body = BackupService.render_template(template.body, variables)
                template_name = template.name
            else:
                # 默认模板（无模板时使用）
                subject = f'进销存系统数据备份 - {variables["datetime"]}'
                body = f'''您好！

这是进销存管理系统的自动数据备份。
备份时间：{variables["datetime"]}
文件名：{filename}

请妥善保存此备份文件。
如需恢复数据，请在系统【备份管理】-【恢复数据】中上传此文件。
'''
                template_name = '默认模板'

            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = config.sender_email
            msg['To'] = config.receiver_email
            msg['Subject'] = subject

            # 邮件正文
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # 添加附件
            with open(filepath, 'rb') as f:
                attachment = MIMEBase('application', 'octet-stream')
                attachment.set_payload(f.read())
            encoders.encode_base64(attachment)
            attachment.add_header('Content-Disposition', f'attachment; filename={filename}')
            msg.attach(attachment)

            # 发送邮件 - 根据端口选择加密方式
            server = None
            try:
                if config.smtp_port == 465:
                    # SSL加密连接（端口465）
                    server = smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, timeout=30)
                else:
                    # 普通连接（端口587/25）
                    server = smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=30)
                    if config.use_tls:
                        server.ehlo()
                        server.starttls()
                        server.ehlo()

                # 登录
                server.login(config.sender_email, config.sender_password)

                # 发送邮件
                server.send_message(msg)

                return {'success': True, 'template_name': template_name}

            except smtplib.SMTPAuthenticationError as e:
                return {'success': False, 'error': f'邮箱认证失败，请检查邮箱和授权码是否正确。错误码: {e.smtp_code}'}
            except smtplib.SMTPConnectError as e:
                return {'success': False, 'error': f'无法连接到SMTP服务器 {config.smtp_server}:{config.smtp_port}，请检查服务器地址和端口'}
            except smtplib.SMTPServerDisconnected as e:
                return {'success': False, 'error': f'连接被服务器断开，可能是端口或加密方式配置错误'}
            except TimeoutError:
                return {'success': False, 'error': f'连接超时，请检查网络或SMTP服务器地址是否正确'}
            except Exception as e:
                error_msg = str(e)
                if 'Connection unexpectedly closed' in error_msg:
                    return {'success': False, 'error': '连接被意外关闭，请尝试：1.检查端口是否正确(587或465) 2.检查TLS开关 3.确认授权码正确'}
                return {'success': False, 'error': f'发送失败: {error_msg}'}
            finally:
                if server:
                    try:
                        server.quit()
                    except:
                        pass

        except Exception as e:
            return {'success': False, 'error': str(e)}

    # 本机备份保留天数：本机磁盘只留最近若干天，长期归档由百度网盘承担
    # （可用环境变量 JXC_BACKUP_KEEP_DAYS 覆盖，便于按机器调整）
    LOCAL_KEEP_DAYS = int(os.environ.get('JXC_BACKUP_KEEP_DAYS', '3'))

    @staticmethod
    def cleanup_local_backups(keep_days=None):
        """删除本机超过保留天数的备份文件，避免本地磁盘被历史备份占满

        安全措施：无论多旧，始终保留最新一份，避免连续多日无备份时被清空。
        """
        days = BackupService.LOCAL_KEEP_DAYS if keep_days is None else int(keep_days)
        backup_dir = _Paths.backups_dir()
        cutoff = time.time() - days * 86400

        files = [
            os.path.join(backup_dir, name)
            for name in os.listdir(backup_dir)
            if name.startswith('inventory_backup_') and name.endswith('.zip')
        ]
        if not files:
            return []
        files.sort(key=lambda f: os.path.getmtime(f))

        removed = []
        for path in files[:-1]:  # 最后一项（最新）永不删除
            if os.path.getmtime(path) >= cutoff:
                continue
            try:
                os.remove(path)
                removed.append(os.path.basename(path))
            except OSError as exc:
                print(f'[Backup] 清理本机旧备份失败 {os.path.basename(path)}: {exc}')
        if removed:
            print(f'[Backup] 已清理本机旧备份 {len(removed)} 份（本机保留最近 {days} 天）')
        return removed

    @staticmethod
    def backup_and_send(backup_type='manual', template_id=None, trigger_type=None):
        """备份并发送邮件"""
        if trigger_type is None:
            trigger_type = '手动触发' if backup_type == 'manual' else '定时自动'

        # 创建备份
        result = BackupService.create_backup()

        if not result['success']:
            # 记录失败
            history = BackupHistory(
                filename='',
                backup_type=backup_type,
                status='failed',
                error_message=result['error'],
                sent_to_email=False
            )
            db.session.add(history)
            db.session.commit()
            # 发送 QQ 告警附带失败原因
            try:
                import subprocess
                subprocess.run(
                    ['/usr/bin/python3', '/root/.hermes/scripts/qq_notify.py',
                     f'⚠️ 进销存备份失败\n🕐 时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n📋 原因：{result["error"]}'],
                    timeout=10, check=False
                )
            except Exception:
                pass
            return result

        # 发送邮件
        email_result = BackupService.send_backup_email(
            result['filepath'],
            result['filename'],
            template_id=template_id,
            trigger_type=trigger_type,
            backup_type=backup_type
        )

        # 上传百度网盘（失败不影响备份与邮件，仅记录状态，便于事后追溯）
        baidu_ok, baidu_info = False, None
        try:
            from services.baidu_backup import upload_backup
            baidu_ok, baidu_info = upload_backup(result['filepath'])
        except Exception as exc:  # noqa: BLE001
            baidu_ok, baidu_info = False, f'网盘上传异常：{exc}'
        if not baidu_ok:
            print(f"[备份] 百度网盘上传未成功：{baidu_info}")

        # 仅在网盘上传成功后清理旧本机备份，避免远端不可用时仍删除本地副本。
        # 始终保留最新一份的保护由 cleanup_local_backups() 实现。
        if baidu_ok:
            try:
                BackupService.cleanup_local_backups()
            except Exception as exc:  # noqa: BLE001
                print(f"[备份] 清理本机旧备份异常：{exc}")
        else:
            print("[备份] 网盘未确认上传成功，保留本机历史备份")

        # 记录历史
        history = BackupHistory(
            filename=result['filename'],
            file_size=result['file_size'],
            backup_type=backup_type,
            status='success',
            sent_to_email=email_result['success'],
            email_status='sent' if email_result['success'] else 'failed',
            error_message=email_result.get('error') if not email_result['success'] else None,
            baidu_path=baidu_info if baidu_ok else None,
            baidu_status='uploaded' if baidu_ok else 'failed'
        )
        db.session.add(history)
        db.session.commit()

        # 邮件发送失败时发送 QQ 告警
        if not email_result['success']:
            try:
                import subprocess
                subprocess.run(
                    ['/usr/bin/python3', '/root/.hermes/scripts/qq_notify.py',
                     f'⚠️ 进销存备份邮件发送失败\n🕐 时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n📋 原因：{email_result.get("error", "未知")}'],
                    timeout=10, check=False
                )
            except Exception:
                pass

        return {
            'success': True,
            'filename': result['filename'],
            'email_sent': email_result['success'],
            'email_error': email_result.get('error'),
            'template_name': email_result.get('template_name'),
            'baidu_uploaded': baidu_ok,
            'baidu_path': baidu_info if baidu_ok else None,
            'baidu_error': None if baidu_ok else baidu_info
        }

    @staticmethod
    def list_backup_files():
        """列出 backups 目录中的所有备份文件"""
        try:
            backups_dir = _Paths.backups_dir()
            if not os.path.exists(backups_dir):
                return []
            files = []
            for f in sorted(os.listdir(backups_dir), reverse=True):
                fp = os.path.join(backups_dir, f)
                if os.path.isfile(fp) and f.endswith('.zip'):
                    size = os.path.getsize(fp)
                    mtime = datetime.fromtimestamp(os.path.getmtime(fp))
                    files.append({
                        'filename': f,
                        'filepath': fp,
                        'size': size,
                        'size_text': BackupService.format_file_size(size),
                        'modified': mtime.strftime('%Y-%m-%d %H:%M:%S')
                    })
            return files
        except Exception as e:
            print(f"[Backup] list_backup_files error: {e}")
            return []

    @staticmethod
    def get_backup_filepath(filename):
        """根据文件名获取完整路径，防止路径遍历攻击"""
        if not filename or '..' in filename or '/' in filename or '\\' in filename:
            return None
        backups_dir = _Paths.backups_dir()
        fp = os.path.join(backups_dir, filename)
        # 确保最终解析后的路径仍在 backups_dir 内
        if os.path.commonpath([os.path.abspath(fp), os.path.abspath(backups_dir)]) != os.path.abspath(backups_dir):
            return None
        return fp if os.path.exists(fp) else None

    @staticmethod
    def delete_backup_file(filename):
        """删除指定备份文件"""
        fp = BackupService.get_backup_filepath(filename)
        if not fp:
            return {'success': False, 'error': '文件不存在或非法'}
        try:
            os.remove(fp)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

