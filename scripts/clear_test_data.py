#!/usr/bin/env python3
"""
清除测试数据脚本
保留：商品、仓库、用户、角色、系统配置
删除：客户、供应商、银行账户、批次、批次码、库存、出入库记录、收支记录、操作日志、表单配置
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db
from models.bank_account import BankAccount
from models.customer import Customer
from models.supplier import Supplier
from models.inventory import Inventory
from models.product_batch import ProductBatch
from models.batch_code import BatchCode
from models.stock_transaction import StockTransaction
from models.financial_transaction import FinancialTransaction
from models.operation_log import OperationLog
from models.form_config import FormConfig, FormFieldConfig
from models.purchase_order import PurchaseOrder, PurchaseOrderItem
from models.platform_order import PlatformOrder
from models.backup_history import BackupHistory


def clear_test_data():
    """清除测试数据"""
    print('=' * 60)
    print('开始清除测试数据...')
    print('=' * 60)

    app = create_app()
    with app.app_context():
        # 1. 清除批次码（先清除，因为关联批次）
        count = BatchCode.query.delete()
        print(f'✅ 清除批次码: {count} 条')

        # 2. 清除批次
        count = ProductBatch.query.delete()
        print(f'✅ 清除批次: {count} 条')

        # 3. 清除库存
        count = Inventory.query.delete()
        print(f'✅ 清除库存: {count} 条')

        # 4. 清除出入库记录
        count = StockTransaction.query.delete()
        print(f'✅ 清除出入库记录: {count} 条')

        # 5. 清除收支记录
        count = FinancialTransaction.query.delete()
        print(f'✅ 清除收支记录: {count} 条')

        # 6. 清除客户
        count = Customer.query.delete()
        print(f'✅ 清除客户: {count} 条')

        # 7. 清除供应商
        count = Supplier.query.delete()
        print(f'✅ 清除供应商: {count} 条')

        # 8. 清除银行账户
        count = BankAccount.query.delete()
        print(f'✅ 清除银行账户: {count} 条')

        # 9. 清除操作日志
        count = OperationLog.query.delete()
        print(f'✅ 清除操作日志: {count} 条')

        # 10. 清除采购订单
        count = PurchaseOrderItem.query.delete()
        print(f'✅ 清除采购订单明细: {count} 条')
        count = PurchaseOrder.query.delete()
        print(f'✅ 清除采购订单: {count} 条')

        # 11. 清除平台订单
        count = PlatformOrder.query.delete()
        print(f'✅ 清除平台订单: {count} 条')

        # 12. 清除备份历史
        count = BackupHistory.query.delete()
        print(f'✅ 清除备份历史: {count} 条')

        # 提交
        db.session.commit()

        print('\n' + '=' * 60)
        print('测试数据已清除！')
        print('=' * 60)
        print('\n📊 保留的数据:')
        print('   - 商品信息')
        print('   - 仓库信息')
        print('   - 用户信息')
        print('   - 角色权限')
        print('   - 系统配置')


if __name__ == '__main__':
    clear_test_data()
