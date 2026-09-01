from models.database import db
from datetime import datetime

class EmailConfig(db.Model):
    __tablename__ = 'email_configs'
    id = db.Column(db.Integer, primary_key=True)
    smtp_server = db.Column(db.String(100), nullable=False, default='smtp.qq.com')
    smtp_port = db.Column(db.Integer, nullable=False, default=587)
    sender_email = db.Column(db.String(120), nullable=False)
    sender_password = db.Column(db.String(100), nullable=False)  # 授权码/密码
    receiver_email = db.Column(db.String(120), nullable=False)
    use_tls = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)

    # 自动备份设置
    enable_auto_backup = db.Column(db.Boolean, default=False)
    backup_hour = db.Column(db.Integer, default=2)
    backup_minute = db.Column(db.Integer, default=0)

    # 邮件模板设置
    selected_template_id = db.Column(db.Integer, db.ForeignKey('email_templates.id'), comment='当前选用的邮件模板ID')

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联模板
    selected_template = db.relationship('EmailTemplate', foreign_keys=[selected_template_id], backref='configs')
