from flask_sqlalchemy import SQLAlchemy

# 创建全局数据库实例
db = SQLAlchemy()

# 导入所有模型（确保表被正确创建）
from models.user import User
from models.role import Role
from models.product import Product
from models.warehouse import Warehouse
from models.supplier import Supplier
from models.customer import Customer
from models.inventory import Inventory
from models.stock_transaction import StockTransaction
from models.purchase_order import PurchaseOrder, PurchaseOrderItem
from models.platform_order import PlatformOrder, PlatformOrderItem
from models.email_config import EmailConfig
from models.backup_history import BackupHistory
from models.email_template import EmailTemplate
from models.operation_log import OperationLog
from models.system_config import SystemConfig
from models.bank_account import BankAccount
from models.financial_transaction import FinancialTransaction
from models.accounts import AccountsReceivable, AccountsPayable
from models.product_batch import ProductBatch
from models.batch_code import BatchCode
