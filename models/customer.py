"""
客户模型
"""

from models.database import db
from datetime import datetime


class Customer(db.Model):
    """客户模型"""
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, comment='客户名称')
    contact = db.Column(db.String(64), comment='联系人')
    phone = db.Column(db.String(20), comment='联系电话')
    address = db.Column(db.String(256), comment='收货地址')
    email = db.Column(db.String(120), comment='电子邮箱')
    tax_no = db.Column(db.String(64), comment='税号')
    bank = db.Column(db.String(128), comment='开户行')
    account_no = db.Column(db.String(64), comment='账号')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    remark = db.Column(db.Text, comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f'<Customer {self.name}>'
