from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, send_file, abort
import os
from models import db
from models.email_config import EmailConfig
from models.backup_history import BackupHistory
from models.email_template import EmailTemplate
from services.backup_service import BackupService
from services.scheduler_service import SchedulerService
from services.log_service import LogService
from utils.decorators import admin_required

backup_bp = Blueprint('backup', __name__, url_prefix='/backup')

@backup_bp.route('/')
@admin_required
def index():
    """备份管理首页"""
    email_config = EmailConfig.query.first()

    # 历史列表只展示最近 10 条，避免页面过长
    HISTORY_LIMIT = 10
    history = BackupHistory.query.order_by(
        BackupHistory.created_at.desc()
    ).limit(HISTORY_LIMIT).all()

    # 统计数据走数据库全量聚合。
    # 此前模板直接用 history 列表长度计算，导致"总备份数"实际只是
    # 列表上限（20）内的条数，与标签含义不符；列表截断为 10 条后偏差更大。
    history_total = BackupHistory.query.count()
    backup_stats = {
        'total': history_total,
        'success': BackupHistory.query.filter_by(status='success').count(),
        'failed': BackupHistory.query.filter_by(status='failed').count(),
        'email_sent': BackupHistory.query.filter_by(sent_to_email=True).count(),
    }
    jobs = SchedulerService.get_jobs()
    has_job = any(job.id == 'daily_backup' for job in jobs)
    backup_files = BackupService.list_backup_files()
    # 网盘上传状态（按文件名映射），供"服务器上的备份文件"列表逐行显示
    baidu_map = {}
    for record in BackupHistory.query.filter(BackupHistory.baidu_status.isnot(None)).all():
        baidu_map[record.filename] = {
            'status': record.baidu_status,
            'path': record.baidu_path,
        }
    return render_template('backup/index.html',
                         email_config=email_config,
                         history=history,
                         history_limit=HISTORY_LIMIT,
                         history_total=history_total,
                         backup_stats=backup_stats,
                         has_job=has_job,
                         baidu_map=baidu_map,
                         backup_files=backup_files)

@backup_bp.route('/config', methods=['GET', 'POST'])
@admin_required
def config():
    """邮箱配置"""
    email_config = EmailConfig.query.first()
    jobs = SchedulerService.get_jobs()
    has_backup_job = any(job.id == 'daily_backup' for job in jobs)
    templates_list = EmailTemplate.query.filter_by(is_active=True).order_by(EmailTemplate.sort_order, EmailTemplate.id).all()

    if request.method == 'POST':
        smtp_server = request.form.get('smtp_server', '').strip()
        smtp_port = request.form.get('smtp_port', 587, type=int)
        sender_email = request.form.get('sender_email', '').strip()
        sender_password = request.form.get('sender_password', '').strip()
        receiver_email = request.form.get('receiver_email', '').strip()
        use_tls = request.form.get('use_tls') == 'on'
        backup_hour = request.form.get('backup_hour', 2, type=int)
        backup_minute = request.form.get('backup_minute', 0, type=int)
        enable_auto = request.form.get('enable_auto') == 'on'
        template_id = request.form.get('selected_template_id', type=int)

        if not all([smtp_server, sender_email, sender_password, receiver_email]):
            flash('请填写完整的邮箱配置信息', 'danger')
            return redirect(url_for('backup.config'))

        if email_config:
            email_config.smtp_server = smtp_server
            email_config.smtp_port = smtp_port
            email_config.sender_email = sender_email
            email_config.sender_password = sender_password
            email_config.receiver_email = receiver_email
            email_config.use_tls = use_tls
            email_config.enable_auto_backup = enable_auto
            email_config.backup_hour = backup_hour
            email_config.backup_minute = backup_minute
            email_config.selected_template_id = template_id
        else:
            email_config = EmailConfig(
                smtp_server=smtp_server,
                smtp_port=smtp_port,
                sender_email=sender_email,
                sender_password=sender_password,
                receiver_email=receiver_email,
                use_tls=use_tls,
                enable_auto_backup=enable_auto,
                backup_hour=backup_hour,
                backup_minute=backup_minute,
                selected_template_id=template_id
            )
            db.session.add(email_config)

        db.session.commit()

        # 设置或取消定时任务
        if enable_auto:
            SchedulerService.add_backup_job(backup_hour, backup_minute)
            flash(f'邮箱配置已保存，已启用每日 {backup_hour:02d}:{backup_minute:02d} 自动备份', 'success')
        else:
            SchedulerService.remove_backup_job()
            flash('邮箱配置已保存，自动备份已禁用', 'success')

        return redirect(url_for('backup.index'))

    return render_template('backup/config.html', email_config=email_config, has_backup_job=has_backup_job, templates=templates_list)

@backup_bp.route('/manual', methods=['POST'])
@admin_required
def manual_backup():
    """手动备份"""
    result = BackupService.backup_and_send('manual')
    if result['success']:
        LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='backup', module='backup', description=f'手动备份: {result["filename"]}')
        flash(f'备份成功！文件名：{result["filename"]}', 'success')
        if result['email_sent']:
            flash('备份文件已发送到邮箱', 'success')
        else:
            flash(f'邮件发送失败：{result.get("email_error", "未知错误")}', 'warning')
    else:
        flash(f'备份失败：{result.get("error", "未知错误")}', 'danger')
    return redirect(url_for('backup.index'))

@backup_bp.route('/test-email', methods=['POST'])
@admin_required
def test_email():
    """测试邮件发送"""
    config = EmailConfig.query.first()
    if not config:
        return jsonify({'success': False, 'message': '请先配置邮箱'})

    # 创建一个简单的测试备份
    result = BackupService.create_backup()
    if not result['success']:
        return jsonify({'success': False, 'message': f'创建测试备份失败：{result["error"]}'})

    # 发送邮件
    email_result = BackupService.send_backup_email(result['filepath'], result['filename'])

    # 清理测试备份文件
    try:
        os.remove(result['filepath'])
    except:
        pass

    if email_result['success']:
        return jsonify({'success': True, 'message': '测试邮件发送成功！请检查收件箱'})
    else:
        return jsonify({'success': False, 'message': f'测试邮件发送失败：{email_result["error"]}'})


@backup_bp.route('/restore', methods=['GET', 'POST'])
@admin_required
def restore():
    """数据库恢复"""
    if request.method == 'POST':
        # 检查是否有文件上传
        if 'backup_file' not in request.files:
            flash('请选择备份文件', 'danger')
            return redirect(url_for('backup.restore'))

        file = request.files['backup_file']
        if file.filename == '':
            flash('请选择备份文件', 'danger')
            return redirect(url_for('backup.restore'))

        # 检查文件扩展名
        if not file.filename.endswith('.zip'):
            flash('请上传 .zip 格式的备份文件', 'danger')
            return redirect(url_for('backup.restore'))

        # 保存上传的文件
        import tempfile
        import zipfile

        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, file.filename)
        file.save(zip_path)

        try:
            # 解压zip文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # 查找解压后的.db文件
            db_files = [f for f in os.listdir(temp_dir) if f.endswith('.db')]
            if len(db_files) == 0:
                flash('备份文件中未找到数据库文件', 'danger')
                return redirect(url_for('backup.restore'))

            backup_db_path = os.path.join(temp_dir, db_files[0])

            # 执行恢复
            result = BackupService.restore_backup(backup_db_path)

            if result['success']:
                LogService.log_operation(
                    user_id=session.get('user_id'),
                    username=session.get('username'),
                    operation_type='restore',
                    module='备份',
                    description=f'数据库恢复成功: {file.filename}'
                )
                flash('数据库恢复成功！系统将重新加载。', 'success')
                return redirect(url_for('auth.logout'))
            else:
                flash(f'恢复失败：{result["error"]}', 'danger')

        except Exception as e:
            flash(f'恢复过程出错：{str(e)}', 'danger')
        finally:
            # 清理临时文件
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except:
                pass

        return redirect(url_for('backup.restore'))

    return render_template('backup/restore.html')


@backup_bp.route('/templates')
@admin_required
def templates():
    """邮件模板管理"""
    templates_list = EmailTemplate.query.order_by(EmailTemplate.sort_order, EmailTemplate.id).all()
    return render_template('backup/templates.html', templates=templates_list)


@backup_bp.route('/templates/edit/<int:template_id>', methods=['GET', 'POST'])
@admin_required
def edit_template(template_id):
    """编辑邮件模板"""
    template = EmailTemplate.query.get_or_404(template_id)

    if request.method == 'POST':
        template.name = request.form.get('name', '').strip()
        template.description = request.form.get('description', '').strip()
        template.subject = request.form.get('subject', '').strip()
        template.body = request.form.get('body', '').strip()
        template.is_active = request.form.get('is_active') == 'on'
        db.session.commit()
        flash('模板保存成功！', 'success')
        return redirect(url_for('backup.templates'))

    return render_template('backup/edit_template.html', template=template)


@backup_bp.route('/templates/preview/<int:template_id>', methods=['GET'])
@admin_required
def preview_template(template_id):
    """预览模板渲染效果"""
    template = EmailTemplate.query.get_or_404(template_id)
    return jsonify({
        'success': True,
        'subject': template.subject,
        'body': template.body,
        'variables': BackupService.get_template_variables()
    })


@backup_bp.route('/templates/preview-rendered/<int:template_id>', methods=['GET'])
@admin_required
def preview_rendered_template(template_id):
    """预览渲染后的效果"""
    template = EmailTemplate.query.get_or_404(template_id)
    variables = BackupService.get_template_variables(
        filename='inventory_backup_20260618_120000.zip',
        file_size=512000,
        backup_type='manual',
        trigger_type='手动触发'
    )
    rendered_subject = BackupService.render_template(template.subject, variables)
    rendered_body = BackupService.render_template(template.body, variables)
    return jsonify({
        'success': True,
        'subject': rendered_subject,
        'body': rendered_body,
        'variables': variables
    })


@backup_bp.route('/templates/delete/<int:template_id>', methods=['POST'])
@admin_required
def delete_template(template_id):
    """删除模板（仅限非内置模板）"""
    template = EmailTemplate.query.get_or_404(template_id)
    if template.is_builtin:
        return jsonify({'success': False, 'message': '内置模板不能删除'})

    # 检查是否被配置使用
    config = EmailConfig.query.filter_by(selected_template_id=template_id).first()
    if config:
        config.selected_template_id = None
        db.session.commit()

    db.session.delete(template)
    db.session.commit()
    flash('模板已删除', 'success')
    return redirect(url_for('backup.templates'))


@backup_bp.route('/files')
@admin_required
def files():
    """备份文件列表"""
    backup_files = BackupService.list_backup_files()
    return render_template('backup/files.html', backup_files=backup_files)


@backup_bp.route('/download/<path:filename>')
@admin_required
def download(filename):
    """下载备份文件"""
    fp = BackupService.get_backup_filepath(filename)
    if not fp:
        abort(404)
    return send_file(fp, as_attachment=True, download_name=filename)


@backup_bp.route('/delete-file/<path:filename>', methods=['POST'])
@admin_required
def delete_file(filename):
    """删除备份文件"""
    result = BackupService.delete_backup_file(filename)
    if result['success']:
        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='delete',
            module='备份',
            description=f'删除备份文件: {filename}'
        )
        flash('备份文件已删除', 'success')
    else:
        flash(f'删除失败: {result.get("error", "未知错误")}', 'danger')
    return redirect(url_for('backup.index'))
