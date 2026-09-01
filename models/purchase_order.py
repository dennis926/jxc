from datetime import datetime
from models import db


class PurchaseOrderItem(db.Model):
    """采购单明细模型"""
    __tablename__ = 'purchase_order_items'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False, comment='采购单ID')
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, comment='商品ID')
    quantity = db.Column(db.Integer, nullable=False, comment='采购数量')
    unit_cost = db.Column(db.Numeric(10, 2), default=0, comment='单位成本')
    received_quantity = db.Column(db.Integer, default=0, comment='已入库数量')

    # 关联关系
    product = db.relationship('Product', back_populates='purchase_order_items')
    purchase_order = db.relationship('PurchaseOrder', back_populates='items')

    def __repr__(self):
        return f'<PurchaseOrderItem 采购单{self.purchase_order_id} 商品{self.product_id}>'


class PurchaseOrder(db.Model):
    """采购单模型"""
    __tablename__ = 'purchase_orders'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_no = db.Column(db.String(32), unique=True, nullable=False, comment='采购单号')
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False, comment='供应商ID')
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False, comment='入库仓库ID')
    status = db.Column(db.String(32), default='draft',
                       comment='状态: draft/pending/partial/received/cancelled')
    total_amount = db.Column(db.Numeric(12, 2), default=0, comment='总金额')
    remark = db.Column(db.Text, default='', comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 关联关系
    items = db.relationship('PurchaseOrderItem', back_populates='purchase_order', lazy='select',
                            cascade='all, delete-orphan')
    warehouse = db.relationship('Warehouse', backref='purchase_orders')
    supplier = db.relationship('Supplier', back_populates='purchase_orders')

    @staticmethod
    def generate_po_no() -> str:
        """
        生成采购单号
        格式: PO20260516001
        增加重试机制防止并发时单号重复
        """
        date_str = datetime.now().strftime('%Y%m%d')
        max_retries = 10

        for attempt in range(max_retries):
            # 查询当天已有采购单数量
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            count = PurchaseOrder.query.filter(
                PurchaseOrder.created_at >= today_start
            ).count()

            po_no = f'PO{date_str}{str(count + 1).zfill(3)}'

            # 检查是否已存在
            if not PurchaseOrder.query.filter_by(po_no=po_no).first():
                return po_no

        # 如果所有尝试都失败，使用带时间戳的备用方案
        import time
        return f'PO{date_str}{str(int(time.time() * 1000))[-6:]}'

    @staticmethod
    def get_next_po_no() -> str:
        """
        获取下一个可用的采购单号（不保存到数据库）
        用于预览
        """
        return PurchaseOrder.generate_po_no()

    def __repr__(self):
        return f'<PurchaseOrder {self.po_no}>'
