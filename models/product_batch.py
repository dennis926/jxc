from datetime import datetime
from models import db


class ProductBatch(db.Model):
    """商品批次表 - 管理入库批次和防窜货码"""
    __tablename__ = 'product_batches'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_no = db.Column(db.String(64), unique=True, nullable=False, comment='批次号')
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, comment='商品ID')
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False, comment='仓库ID')
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), comment='供应商ID')

    code_start = db.Column(db.Integer, nullable=False, comment='码段起始')
    code_end = db.Column(db.Integer, nullable=False, comment='码段结束')
    total_quantity = db.Column(db.Integer, nullable=False, comment='总数量')
    remaining_quantity = db.Column(db.Integer, nullable=False, comment='剩余数量')

    cost_price = db.Column(db.Numeric(10, 2), default=0, comment='采购成本')
    production_date = db.Column(db.Date, comment='生产日期')
    expire_date = db.Column(db.Date, comment='有效期至')

    status = db.Column(db.String(20), default='active', comment='状态: active/used/depleted/cancelled')

    remark = db.Column(db.Text, default='', comment='备注')
    operator = db.Column(db.String(64), default='', comment='操作人')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    product = db.relationship('Product', overlaps="batches")
    warehouse = db.relationship('Warehouse', backref='batches')
    supplier = db.relationship('Supplier', backref='batches')
    codes = db.relationship('BatchCode', backref='batch', lazy='dynamic', cascade='all, delete-orphan')

    @staticmethod
    def generate_batch_no():
        """生成批次号，格式：BATCH-YYYYMMDD-XXX"""
        date_str = datetime.now().strftime('%Y%m%d')
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = ProductBatch.query.filter(
            ProductBatch.created_at >= today_start
        ).count()
        return f'BATCH-{date_str}-{str(count + 1).zfill(3)}'

    @property
    def code_range(self):
        """返回码段范围字符串"""
        return f'{self.code_start}-{self.code_end}'

    def __repr__(self):
        return f'<ProductBatch {self.batch_no}>'
