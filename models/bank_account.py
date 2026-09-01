"""
账户模型
"""

from models.database import db
from datetime import datetime


class BankAccount(db.Model):
    """账户模型"""
    __tablename__ = 'bank_accounts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, comment='账户名称')
    code = db.Column(db.String(32), comment='账户编码')
    type = db.Column(db.String(32), default='bank', comment='类型: cash-现金, bank-银行, card-信用卡')
    account_no = db.Column(db.String(64), comment='账号')
    opening_balance = db.Column(db.Numeric(12, 2), default=0, comment='期初余额')
    current_balance = db.Column(db.Numeric(12, 2), default=0, comment='当前余额')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    remark = db.Column(db.Text, comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f'<BankAccount {self.name}>'
