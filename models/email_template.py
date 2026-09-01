from models import db
from datetime import datetime


class EmailTemplate(db.Model):
    """邮件模板模型"""
    __tablename__ = 'email_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='模板名称')
    description = db.Column(db.String(255), comment='模板描述')
    subject = db.Column(db.String(200), nullable=False, comment='邮件主题')
    body = db.Column(db.Text, nullable=False, comment='邮件正文（支持变量）')
    is_builtin = db.Column(db.Boolean, default=False, comment='是否内置模板（不可删除）')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    sort_order = db.Column(db.Integer, default=0, comment='排序')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    def __repr__(self):
        return f'<EmailTemplate {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'subject': self.subject,
            'body': self.body,
            'is_builtin': self.is_builtin,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }

    @staticmethod
    def get_default_templates():
        """获取默认内置模板列表"""
        return [
            {
                'name': '标准备份通知',
                'description': '简洁规范的备份通知模板',
                'subject': '【进销存系统】数据备份通知 - {date}',
                'body': '''尊敬的 {user_name}：

您好！

进销存管理系统已于 {datetime} 自动完成数据备份。

┌─────────────────────────────────┐
│  📦 备份信息                      │
├─────────────────────────────────┤
│  文件名：{filename}              │
│  备份大小：{file_size}            │
│  备份类型：{backup_type}          │
│  备份时间：{datetime}             │
│  累计备份：第 {total_count} 次    │
│  成功次数：{success_count} 次      │
└─────────────────────────────────┘

请妥善保存此备份文件。如需恢复数据，请登录系统后进入
【备份管理】→【恢复数据】页面，上传此备份文件即可。

系统名称：{system_name}
发送时间：{send_time}

本邮件由系统自动发送，请勿直接回复。''',
                'sort_order': 10
            },
            {
                'name': '简洁通知',
                'description': '简短直接的备份通知',
                'subject': '系统备份 {date}',
                'body': '''{user_name}，您好：

已完成 {date} 的数据备份。

📁 文件：{filename}
💾 大小：{file_size}
⏰ 时间：{datetime}

—— {system_name}''',
                'sort_order': 20
            },
            {
                'name': '详细报告',
                'description': '包含详细备份统计信息',
                'subject': '【{system_name}】数据备份详细报告 - {date}',
                'body': '''═══════════════════════════════════
   📊  数据备份报告
═══════════════════════════════════

尊敬的 {user_name}：

以下是本次数据备份的详细信息：

【基本信息】
  ◆ 备份时间：{datetime}
  ◆ 备份类型：{backup_type}
  ◆ 备份文件：{filename}
  ◆ 文件大小：{file_size}

【历史统计】
  ◆ 累计备份：{total_count} 次
  ◆ 成功次数：{success_count} 次
  ◆ 失败次数：{failed_count} 次
  ◆ 邮件送达：{email_sent_count} 次
  ◆ 上次备份：{last_backup_time}
  ◆ 上次结果：{last_backup_status}

【重要提示】
1. 建议保留最近 30 天的备份文件
2. 定期将备份下载到本地或异地存储
3. 如需恢复数据，请使用本邮件附件

如有任何问题，请联系系统管理员。

───────────────────────────────────
{system_name}
{send_time}
───────────────────────────────────
本邮件由系统自动发送，请勿直接回复。''',
                'sort_order': 30
            },
            {
                'name': '紧急告警',
                'description': '用于重要数据备份或异常情况通知',
                'subject': '⚠️【重要】系统数据备份通知 - {date}',
                'body': '''【紧急通知】

{system_name} 系统已完成 {date} 的关键数据备份。

⚠️  本次备份信息 ⚠️
━━━━━━━━━━━━━━━━━━
📅 备份时间：{datetime}
📁 备份文件：{filename}
💾 文件大小：{file_size}
📝 备份类型：{backup_type}
👤 触发方式：{trigger_type}
━━━━━━━━━━━━━━━━━━

请尽快下载附件并保存到安全位置！

恢复方法：登录系统 → 备份管理 → 恢复数据 → 上传此文件

—— {system_name} 运维团队
{send_time}''',
                'sort_order': 40
            },
            {
                'name': '极简模式',
                'description': '只包含必要信息',
                'subject': '{date} 备份完成',
                'body': '''{datetime} 备份完成。
文件：{filename}（{file_size}）
{system_name}''',
                'sort_order': 50
            }
        ]

    @staticmethod
    def init_builtin_templates():
        """初始化内置模板（仅在表为空时执行）"""
        if EmailTemplate.query.first() is not None:
            return

        for template_data in EmailTemplate.get_default_templates():
            template = EmailTemplate(
                name=template_data['name'],
                description=template_data['description'],
                subject=template_data['subject'],
                body=template_data['body'],
                is_builtin=True,
                is_active=True,
                sort_order=template_data['sort_order']
            )
            db.session.add(template)
        db.session.commit()
