from datetime import datetime
from models import db


class OperationLog(db.Model):
    """操作日志模型"""
    __tablename__ = 'operation_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), comment='用户ID')
    username = db.Column(db.String(80), comment='用户名（冗余存储，方便查询）')
    operation_type = db.Column(db.String(50), comment='操作类型: login/logout/create/update/delete/import/export等')
    module = db.Column(db.String(50), comment='模块名: 商品/仓库/库存/采购等')
    description = db.Column(db.Text, comment='操作描述')
    reference_type = db.Column(db.String(50), comment='关联类型: order/po/transaction等')
    reference_no = db.Column(db.String(100), comment='关联单号')
    reference_id = db.Column(db.Integer, comment='关联ID')
    before_data = db.Column(db.Text, comment='操作前的数据(JSON)')
    after_data = db.Column(db.Text, comment='操作后的数据(JSON)')
    ip_address = db.Column(db.String(50), comment='IP地址')
    user_agent = db.Column(db.String(200), comment='用户代理')
    request_url = db.Column(db.String(500), comment='请求URL')
    request_method = db.Column(db.String(10), comment='请求方法')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

    # 关联关系
    user = db.relationship('User', backref='operation_logs')

    def __repr__(self):
        return f'<OperationLog {self.id} - {self.username} - {self.operation_type}>'

    @staticmethod
    def get_operation_types():
        """获取所有操作类型"""
        return [
            ('login', '登录'),
            ('logout', '登出'),
            ('create', '创建'),
            ('update', '更新'),
            ('delete', '删除'),
            ('import', '导入'),
            ('export', '导出'),
            ('view', '查看'),
            ('approve', '审批'),
            ('reject', '拒绝'),
            ('print', '打印'),
            ('transfer', '调拨'),
            ('stock_in', '入库'),
            ('stock_out', '出库'),
            ('adjust', '调整'),
            ('collect', '收款'),
            ('pay', '付款'),
            ('backup', '备份'),
        ]

    @staticmethod
    def get_modules():
        """获取所有模块"""
        return [
            ('product', '商品'),
            ('warehouse', '仓库'),
            ('supplier', '供应商'),
            ('customer', '客户'),
            ('inventory', '库存'),
            ('purchase', '采购'),
            ('transaction', '出入库'),
            ('finance', '财务'),
            ('user', '用户'),
            ('role', '角色'),
            ('backup', '备份'),
            ('system', '系统'),
            ('auth', '认证'),
        ]
