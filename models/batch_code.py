from datetime import datetime
from models import db


class BatchCode(db.Model):
    """批次码明细表 - 存储每个单独的商品码"""
    __tablename__ = 'batch_codes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('product_batches.id'), nullable=False, comment='批次ID')
    code = db.Column(db.String(64), nullable=False, comment='商品码')

    status = db.Column(db.String(20), default='in_stock', comment='状态: in_stock/sold/reserved/transferred')

    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), comment='售往客户ID')
    customer_name = db.Column(db.String(128), comment='售往客户名称')

    stock_out_id = db.Column(db.Integer, comment='出库记录ID')
    stock_out_no = db.Column(db.String(64), comment='出库单号')

    sold_at = db.Column(db.DateTime, comment='销售时间')
    transferred_at = db.Column(db.DateTime, comment='调拨时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    customer = db.relationship('Customer', backref='batch_codes')

    __table_args__ = (
        db.Index('idx_batch_code_batch_id', 'batch_id'),
        db.Index('idx_batch_code_status', 'status'),
        db.Index('idx_batch_code_code', 'code'),
    )

    def __repr__(self):
        return f'<BatchCode {self.code}>'
