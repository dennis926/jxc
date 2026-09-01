from datetime import datetime
from models import db


class PlatformOrderItem(db.Model):
    """平台订单明细模型（预留）"""
    __tablename__ = 'platform_order_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platform_order_id = db.Column(db.Integer, db.ForeignKey('platform_orders.id'), nullable=False,
                                  comment='平台订单ID')
    product_name = db.Column(db.String(256), default='', comment='商品名称')
    sku = db.Column(db.String(64), default='', comment='SKU编码')
    quantity = db.Column(db.Integer, default=0, comment='数量')
    unit_price = db.Column(db.Numeric(10, 2), default=0, comment='单价')
    total_price = db.Column(db.Numeric(10, 2), default=0, comment='小计')
    spec = db.Column(db.String(256), default='', comment='规格')

    # 关联关系
    platform_order = db.relationship('PlatformOrder', backref='items')

    def __repr__(self):
        return f'<PlatformOrderItem 订单{self.platform_order_id} {self.product_name}>'


class PlatformOrder(db.Model):
    """平台订单模型（预留）"""
    __tablename__ = 'platform_orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    platform = db.Column(db.String(32), default='', comment='平台: taobao/jd/douyin/pdd')
    platform_order_no = db.Column(db.String(64), default='', comment='平台订单号')
    order_status = db.Column(db.String(32), default='', comment='订单状态')
    buyer_info = db.Column(db.Text, default='', comment='买家信息JSON')
    total_amount = db.Column(db.Numeric(12, 2), default=0, comment='订单金额')
    shipping_fee = db.Column(db.Numeric(10, 2), default=0, comment='运费')
    payment = db.Column(db.Numeric(12, 2), default=0, comment='实付金额')
    order_time = db.Column(db.DateTime, nullable=True, comment='下单时间')
    pay_time = db.Column(db.DateTime, nullable=True, comment='付款时间')
    remark = db.Column(db.Text, default='', comment='备注')
    raw_data = db.Column(db.Text, default='', comment='原始数据JSON')
    synced_at = db.Column(db.DateTime, nullable=True, comment='同步时间')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    def __repr__(self):
        return f'<PlatformOrder {self.platform} {self.platform_order_no}>'
