"""
应收应付模型
"""

from models.database import db
from datetime import datetime


class AccountsReceivable(db.Model):
    """应收款模型"""
    __tablename__ = 'accounts_receivable'

    id = db.Column(db.Integer, primary_key=True)
    transaction_no = db.Column(db.String(32), unique=True, nullable=False, comment='单号')
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), comment='客户ID')
    customer_name = db.Column(db.String(128), nullable=False, comment='客户名称')
    customer_address = db.Column(db.String(256), comment='收货地址')
    amount = db.Column(db.Numeric(12, 2), nullable=False, comment='应收金额')
    paid_amount = db.Column(db.Numeric(12, 2), default=0, comment='已收金额')
    pending_amount = db.Column(db.Numeric(12, 2), nullable=False, comment='待收金额')
    invoice_no = db.Column(db.String(64), comment='发票号')
    due_date = db.Column(db.Date, comment='到期日')
    related_type = db.Column(db.String(32), comment='关联类型: stock_out')
    related_id = db.Column(db.Integer, comment='关联ID')
    related_no = db.Column(db.String(64), comment='关联单号')
    status = db.Column(db.String(16), default='pending', comment='状态: pending-待收款, partial-部分收款, received-已收清, written_off-已核销')
    remark = db.Column(db.Text, comment='备注')
    operator = db.Column(db.String(64), comment='操作人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联关系
    customer = db.relationship('Customer', backref='receivables')

    @staticmethod
    def generate_transaction_no():
        """生成应收单号"""
        date_str = datetime.now().strftime('%Y%m%d')
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = AccountsReceivable.query.filter(
            AccountsReceivable.created_at >= today_start
        ).count()
        return f'AR{date_str}{str(count + 1).zfill(3)}'

    def __repr__(self):
        return f'<AccountsReceivable {self.transaction_no}>'


class AccountsPayable(db.Model):
    """应付款模型"""
    __tablename__ = 'accounts_payable'

    id = db.Column(db.Integer, primary_key=True)
    transaction_no = db.Column(db.String(32), unique=True, nullable=False, comment='单号')
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), comment='供应商ID')
    supplier_name = db.Column(db.String(128), nullable=False, comment='供应商名称')
    supplier_contact = db.Column(db.String(64), comment='供应商联系人')
    supplier_phone = db.Column(db.String(20), comment='供应商电话')
    amount = db.Column(db.Numeric(12, 2), nullable=False, comment='应付金额')
    paid_amount = db.Column(db.Numeric(12, 2), default=0, comment='已付金额')
    pending_amount = db.Column(db.Numeric(12, 2), nullable=False, comment='待付金额')
    invoice_no = db.Column(db.String(64), comment='发票号')
    due_date = db.Column(db.Date, comment='到期日')
    related_type = db.Column(db.String(32), comment='关联类型: purchase_order')
    related_id = db.Column(db.Integer, comment='关联ID')
    related_no = db.Column(db.String(64), comment='关联单号')
    status = db.Column(db.String(16), default='pending', comment='状态: pending-待付款, partial-部分付款, paid-已付清, cancelled-已取消')
    remark = db.Column(db.Text, comment='备注')
    operator = db.Column(db.String(64), comment='操作人')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联关系
    supplier = db.relationship('Supplier', backref='payables')

    @staticmethod
    def generate_transaction_no():
        """生成应付单号"""
        date_str = datetime.now().strftime('%Y%m%d')
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = AccountsPayable.query.filter(
            AccountsPayable.created_at >= today_start
        ).count()
        return f'AP{date_str}{str(count + 1).zfill(3)}'

    def __repr__(self):
        return f'<AccountsPayable {self.transaction_no}>'
