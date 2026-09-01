from datetime import datetime
from models import db


class Product(db.Model):
    """商品模型"""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sku = db.Column(db.String(64), unique=True, nullable=False, comment='商品编码')
    name = db.Column(db.String(128), nullable=False, comment='商品名称')
    category = db.Column(db.String(64), default='', comment='商品分类')
    unit = db.Column(db.String(32), default='个', comment='计量单位')

    # 新增字段
    specification = db.Column(db.String(256), default='', comment='商品规格')
    barcode = db.Column(db.String(128), unique=True, nullable=True, comment='条形码(防串货)')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')

    # 药品相关字段
    dosage_form = db.Column(db.String(64), default='', comment='剂型')
    manufacturer = db.Column(db.String(256), default='', comment='生产厂家')
    approval_no = db.Column(db.String(128), default='', comment='批准文号')

    cost_price = db.Column(db.Numeric(10, 2), default=0, comment='成本价')
    selling_price = db.Column(db.Numeric(10, 2), default=0, comment='售价')
    description = db.Column(db.Text, default='', comment='商品描述')
    min_stock = db.Column(db.Integer, default=0, comment='最低库存预警值')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联关系
    inventory_records = db.relationship('Inventory', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    stock_transactions = db.relationship('StockTransaction', lazy='dynamic')  # 保留历史数据，不级联删除
    purchase_order_items = db.relationship('PurchaseOrderItem', lazy='dynamic', cascade='all, delete-orphan')
    batches = db.relationship('ProductBatch', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Product {self.sku} - {self.name}>'
