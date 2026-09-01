"""
财务收支记录模型
"""

from models.database import db
from datetime import datetime


class FinancialTransaction(db.Model):
    """收支记录模型"""
    __tablename__ = 'financial_transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_no = db.Column(db.String(32), unique=True, nullable=False, comment='单号')
    type = db.Column(db.String(32), nullable=False, comment='类型: income-收入, expense-支出, transfer-转账')
    category = db.Column(db.String(64), nullable=False, comment='收支分类')
    amount = db.Column(db.Numeric(12, 2), nullable=False, comment='金额')
    account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), comment='账户ID')
    direction = db.Column(db.String(16), default='in', comment='方向: in-流入, out-流出')
    related_type = db.Column(db.String(32), comment='关联类型: stock_in/stock_out/purchase/sale')
    related_id = db.Column(db.Integer, comment='关联ID')
    counterparty_name = db.Column(db.String(128), comment='对方单位/个人')
    payment_method = db.Column(db.String(32), comment='付款方式: cash-现金, bank-转账, card-刷卡, alipay-支付宝, wechat-微信')
    status = db.Column(db.String(16), default='completed', comment='状态: pending-待确认, completed-已完成, cancelled-已取消')
    transaction_date = db.Column(db.Date, nullable=False, comment='交易日期')
    operator = db.Column(db.String(64), comment='操作人')
    remark = db.Column(db.Text, comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 关联关系
    account = db.relationship('BankAccount', backref='transactions')

    @staticmethod
    def generate_transaction_no(tx_type: str) -> str:
        """生成收支单号"""
        prefix_map = {
            'income': 'INC',
            'expense': 'EXP',
            'transfer': 'TRF'
        }
        prefix = prefix_map.get(tx_type, 'TXN')
        date_str = datetime.now().strftime('%Y%m%d')

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = FinancialTransaction.query.filter(
            FinancialTransaction.created_at >= today_start,
            FinancialTransaction.type == tx_type
        ).count()

        return f'{prefix}{date_str}{str(count + 1).zfill(3)}'

    def __repr__(self):
        return f'<FinancialTransaction {self.transaction_no} {self.type}>'
