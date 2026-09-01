from datetime import datetime
from models import db


class StockTransaction(db.Model):
    """出入库记录模型"""
    __tablename__ = 'stock_transactions'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    transaction_no = db.Column(db.String(32), unique=True, nullable=False, comment='单号')
    type = db.Column(db.String(32), nullable=False,
                     comment='类型: stock_in/stock_out/transfer_in/transfer_out/adjustment')
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, comment='商品ID（商品删除后为NULL）')
    product_name = db.Column(db.String(128), default='', comment='商品名称快照')
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False, comment='仓库ID')
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True, comment='客户ID')
    customer_name = db.Column(db.String(128), default='', comment='客户名称')
    customer_address = db.Column(db.String(256), default='', comment='收货地址')
    quantity = db.Column(db.Integer, nullable=False, comment='数量')
    unit_cost = db.Column(db.Numeric(10, 2), default=0, comment='单位成本')
    reference_no = db.Column(db.String(64), default='', comment='关联单号')
    batch_no = db.Column(db.String(64), default='', comment='批次号')
    batch_codes = db.Column(db.Text, default='', comment='批次码列表')
    remark = db.Column(db.String(256), default='', comment='备注')
    operator = db.Column(db.String(64), default='', comment='操作人')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联关系
    product = db.relationship('Product', back_populates='stock_transactions')
    warehouse = db.relationship('Warehouse', backref='stock_transactions')
    customer = db.relationship('Customer', backref='stock_transactions')

    # 索引优化：为常用查询字段添加索引
    __table_args__ = (
        db.Index('ix_stock_transactions_type', 'type'),
        db.Index('ix_stock_transactions_product_id', 'product_id'),
        db.Index('ix_stock_transactions_warehouse_id', 'warehouse_id'),
        db.Index('ix_stock_transactions_created_at', 'created_at'),
        db.Index('ix_stock_transactions_type_created', 'type', 'created_at'),  # 复合索引
    )

    @staticmethod
    def generate_transaction_no(tx_type: str) -> str:
        """
        生成出入库单号
        格式: IN20260516001 / OUT20260516001 / TI20260516001 / TO20260516001 / AD20260516001
        """
        prefix_map = {
            'stock_in': 'IN',
            'stock_out': 'OUT',
            'transfer_in': 'TI',
            'transfer_out': 'TO',
            'adjustment': 'AD'
        }
        prefix = prefix_map.get(tx_type, 'TX')
        date_str = datetime.now().strftime('%Y%m%d')

        # 查询当天已有记录数量，生成序号
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = StockTransaction.query.filter(
            StockTransaction.created_at >= today_start,
            StockTransaction.type == tx_type
        ).count()

        return f'{prefix}{date_str}{str(count + 1).zfill(3)}'

    def __repr__(self):
        return f'<StockTransaction {self.transaction_no} {self.type}>'
