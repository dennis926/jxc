from datetime import datetime
from models import db


class SystemConfig(db.Model):
    """系统配置模型"""
    __tablename__ = 'system_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_key = db.Column(db.String(100), unique=True, nullable=False, comment='配置键')
    config_value = db.Column(db.Text, comment='配置值')
    config_type = db.Column(db.String(20), default='text', comment='配置类型: text/number/image/color/boolean')
    description = db.Column(db.String(200), comment='配置描述')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), comment='更新人ID')

    # 关联关系
    updater = db.relationship('User', backref='updated_configs')

    def __repr__(self):
        return f'<SystemConfig {self.config_key}>'

    @staticmethod
    def get_value(key, default=None):
        """获取配置值"""
        config = SystemConfig.query.filter_by(config_key=key).first()
        if config:
            return config.config_value
        return default

    @staticmethod
    def set_value(key, value, config_type='text', description=None, user_id=None):
        """设置配置值"""
        config = SystemConfig.query.filter_by(config_key=key).first()
        if config:
            config.config_value = value
            config.config_type = config_type
            if description:
                config.description = description
            if user_id:
                config.updated_by = user_id
        else:
            config = SystemConfig(
                config_key=key,
                config_value=value,
                config_type=config_type,
                description=description,
                updated_by=user_id
            )
            db.session.add(config)
        db.session.commit()
        return config

    @staticmethod
    def get_default_configs():
        """获取默认配置项"""
        return [
            ('site_name', '进销存管理系统', 'text', '网站名称'),
            ('site_logo', '', 'image', '网站LOGO'),
            ('copyright', 'Copyright © 2024 进销存管理系统', 'text', '版权信息'),
            ('contact_email', '', 'text', '联系邮箱'),
            ('contact_phone', '', 'text', '联系电话'),
            ('contact_address', '', 'text', '联系地址'),
            ('items_per_page', '20', 'number', '每页显示条数'),
            ('enable_email_notify', 'false', 'boolean', '启用邮件通知'),
            ('low_stock_alert', 'true', 'boolean', '库存预警'),
        ]
