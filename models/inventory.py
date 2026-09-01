from datetime import datetime
from models import db


class Inventory(db.Model):
    """库存模型"""
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, comment='商品ID')
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False, comment='仓库ID')
    quantity = db.Column(db.Integer, default=0, nullable=False, comment='库存数量')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    # 唯一约束：同一商品在同一仓库只能有一条库存记录
    __table_args__ = (
        db.UniqueConstraint('product_id', 'warehouse_id', name='uix_product_warehouse'),
    )

    def __repr__(self):
        return f'<Inventory 商品{self.product_id} 仓库{self.warehouse_id} 数量{self.quantity}>'
