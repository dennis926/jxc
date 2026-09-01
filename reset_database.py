#!/usr/bin/env python3
"""
重置数据库脚本
- 清空所有数据
- 保留表结构
- 创建初始管理员
"""

import os
import sys

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db
from models.user import User
from models.role import Role


def reset_database():
    """重置数据库 - 清空数据但保留结构"""
    print('=' * 60)
    print('⚠️  警告：此操作将清空所有数据！')
    print('=' * 60)
    
    app = create_app()
    
    with app.app_context():
        # 清空所有表的数据（按依赖关系顺序）
        print('正在清空数据...')
        
        # 清空操作日志
        from models.operation_log import OperationLog
        OperationLog.query.delete()
        
        # 清空库存记录
        from models.stock_transaction import StockTransaction
        StockTransaction.query.delete()
        
        # 清空库存
        from models.inventory import Inventory
        Inventory.query.delete()
        
        # 清空批次
        from models.product_batch import ProductBatch
        ProductBatch.query.delete()
        
        # 清空批次编码
        from models.batch_code import BatchCode
        BatchCode.query.delete()
        
        # 清空采购订单
        from models.purchase_order import PurchaseOrderItem, PurchaseOrder
        PurchaseOrderItem.query.delete()
        PurchaseOrder.query.delete()
        
        # 清空平台订单
        from models.platform_order import PlatformOrderItem, PlatformOrder
        PlatformOrderItem.query.delete()
        PlatformOrder.query.delete()
        
        # 清空财务数据
        from models.financial_transaction import FinancialTransaction
        FinancialTransaction.query.delete()
        
        from models.accounts import AccountsReceivable, AccountsPayable
        AccountsReceivable.query.delete()
        AccountsPayable.query.delete()
        
        from models.bank_account import BankAccount
        BankAccount.query.delete()
        
        # 清空基础数据
        from models.customer import Customer
        Customer.query.delete()
        
        from models.supplier import Supplier
        Supplier.query.delete()
        
        from models.product import Product
        Product.query.delete()
        
        from models.warehouse import Warehouse
        Warehouse.query.delete()
        
        # 清空用户（保留admin）
        User.query.filter(User.username != 'admin').delete()
        
        # 清空角色（保留系统角色）
        Role.query.filter(Role.is_system != True).delete()
        
        # 清空系统配置
        from models.system_config import SystemConfig
        SystemConfig.query.delete()
        
        # 清空备份记录
        from models.backup_history import BackupHistory
        BackupHistory.query.delete()
        
        # 清空邮件配置
        from models.email_config import EmailConfig
        EmailConfig.query.delete()
        
        db.session.commit()
        print('✅ 所有数据已清空')
        
        # 如果没有admin，创建一个
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
            print('✅ 初始管理员账号已创建')
            print('   用户名: admin')
            print('   密码: Admin@2026!')
        else:
            print('✅ 管理员账号已保留')
        
        # 初始化默认角色（使用中文名）
        from models.role import get_default_permissions, get_operator_default_permissions
        if not Role.query.filter_by(name='管理员').first():
            admin_role = Role(
                name='管理员',
                description='系统管理员，拥有所有权限',
                is_system=True,
                is_active=True
            )
            admin_role.set_permissions_list(get_default_permissions())
            db.session.add(admin_role)
        
        if not Role.query.filter_by(name='操作员').first():
            operator_role = Role(
                name='操作员',
                description='普通操作员，拥有除系统管理外的权限',
                is_system=True,
                is_active=True
            )
            operator_role.set_permissions_list(get_operator_default_permissions())
            db.session.add(operator_role)
        
        db.session.commit()
        print('✅ 系统角色已初始化')
        
    print('=' * 60)
    print('数据库重置完成！')
    print('=' * 60)


if __name__ == '__main__':
    reset_database()
