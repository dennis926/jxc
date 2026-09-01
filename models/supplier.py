from datetime import datetime
from models import db


class Supplier(db.Model):
    """供应商模型"""
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False, comment='供应商名称')
    contact_person = db.Column(db.String(64), default='', comment='联系人')
    contact_phone = db.Column(db.String(32), default='', comment='联系电话')
    email = db.Column(db.String(128), default='', comment='邮箱')
    address = db.Column(db.String(256), default='', comment='地址')
    description = db.Column(db.Text, default='', comment='备注')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联关系
    purchase_orders = db.relationship('PurchaseOrder', back_populates='supplier', lazy='dynamic')

    def __repr__(self):
        return f'<Supplier {self.name}>'
