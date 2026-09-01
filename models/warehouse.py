from datetime import datetime
from models import db


class Warehouse(db.Model):
    """仓库模型"""
    __tablename__ = 'warehouses'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False, comment='仓库名称')
    code = db.Column(db.String(32), unique=True, nullable=False, comment='仓库编码')
    address = db.Column(db.String(256), default='', comment='仓库地址')
    contact_person = db.Column(db.String(64), default='', comment='联系人')
    contact_phone = db.Column(db.String(32), default='', comment='联系电话')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联关系
    inventory_records = db.relationship('Inventory', backref='warehouse', lazy='dynamic')

    def __repr__(self):
        return f'<Warehouse {self.code} - {self.name}>'
