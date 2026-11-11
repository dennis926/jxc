from flask import Flask
from models import db


def init_db(app: Flask):
    """初始化数据库"""
    # 检查是否已初始化，避免重复注册
    if 'sqlalchemy' not in app.extensions:
        db.init_app(app)

    # 导入所有模型，确保表被创建
    from models.product import Product
    from models.warehouse import Warehouse
    from models.supplier import Supplier
    from models.customer import Customer
    from models.inventory import Inventory
    from models.stock_transaction import StockTransaction
    from models.purchase_order import PurchaseOrder, PurchaseOrderItem
    from models.platform_order import PlatformOrder, PlatformOrderItem
    from models.user import User
    from models.role import Role
    from models.operation_log import OperationLog
    from models.system_config import SystemConfig
    from models.bank_account import BankAccount
    from models.financial_transaction import FinancialTransaction
    from models.accounts import AccountsReceivable, AccountsPayable
    from models.product_batch import ProductBatch
    from models.batch_code import BatchCode
    from models.backup_history import BackupHistory
    from models.email_config import EmailConfig
    from models.email_template import EmailTemplate

    # 创建所有表
    with app.app_context():
        db.create_all()

        # SQLite 的 create_all() 不会给既有表补列；为网盘备份功能做幂等迁移。
        # 仅新增可空字段，不改写或删除任何既有备份记录。
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        if 'backup_history' in inspector.get_table_names():
            columns = {column['name'] for column in inspector.get_columns('backup_history')}
            with db.engine.begin() as connection:
                if 'baidu_path' not in columns:
                    connection.execute(text(
                        'ALTER TABLE backup_history ADD COLUMN baidu_path VARCHAR(300)'
                    ))
                if 'baidu_status' not in columns:
                    connection.execute(text(
                        'ALTER TABLE backup_history ADD COLUMN baidu_status VARCHAR(20)'
                    ))

        # 初始化默认管理员账号
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin = User(
                username='admin',
                real_name='系统管理员',
                role='admin',
                is_active=True,
                force_change_password=True
            )
            admin.set_password('Admin@2026!')
            db.session.add(admin)
            db.session.commit()
            print('[初始化] 已创建默认管理员账号（用户名: admin, 密码: Admin@2026!，首次登录请修改密码）')
