#!/usr/bin/env python3
"""
生成20条完整测试数据
要求：所有字段必须填写完整
"""

import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
import random

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db
from models.product import Product
from models.customer import Customer
from models.supplier import Supplier
from models.warehouse import Warehouse
from models.bank_account import BankAccount
from models.inventory import Inventory
from models.product_batch import ProductBatch
from models.stock_transaction import StockTransaction
from models.financial_transaction import FinancialTransaction


def generate_test_data():
    """生成完整的测试数据"""
    print('=' * 60)
    print('开始生成测试数据...')
    print('=' * 60)

    app = create_app()
    with app.app_context():
        # 1. 创建银行账户（3个）
        print('\n1. 创建银行账户...')
        bank_accounts_data = [
            {'name': '公司基本户', 'code': 'BANK001', 'type': 'bank', 'account_no': '6217002345678901234', 'opening_balance': 100000, 'current_balance': 100000},
            {'name': '现金账户', 'code': 'CASH001', 'type': 'cash', 'account_no': '', 'opening_balance': 50000, 'current_balance': 50000},
            {'name': '支付宝账户', 'code': 'ALIPAY001', 'type': 'bank', 'account_no': 'alipay@company.com', 'opening_balance': 30000, 'current_balance': 30000},
        ]

        for acc_data in bank_accounts_data:
            existing = BankAccount.query.filter_by(code=acc_data['code']).first()
            if not existing:
                account = BankAccount(
                    name=acc_data['name'],
                    code=acc_data['code'],
                    type=acc_data['type'],
                    account_no=acc_data['account_no'],
                    opening_balance=acc_data['opening_balance'],
                    current_balance=acc_data['current_balance'],
                    is_active=True,
                    remark='测试账户'
                )
                db.session.add(account)
                print(f'   ✅ {acc_data["name"]}')
            else:
                print(f'   ⚠️  {acc_data["name"]} 已存在')

        db.session.commit()

        # 2. 创建供应商（5个）
        print('\n2. 创建供应商...')
        suppliers_data = [
            {'name': '青岛诺和诺康生物科技有限公司', 'contact_person': '张经理', 'contact_phone': '0532-88888801', 'email': 'zhang@nuohk.com', 'address': '山东省青岛市高新区xxx路123号'},
            {'name': '东凯（山东）生物科技有限公司', 'contact_person': '李经理', 'contact_phone': '0531-66666602', 'email': 'li@dongkai.com', 'address': '山东省济南市xxx区456号'},
            {'name': '山东医药采购有限公司', 'contact_person': '王经理', 'contact_phone': '0531-77777703', 'email': 'wang@sdyy.com', 'address': '山东省济南市历下区xxx路789号'},
            {'name': '北京健康科技有限公司', 'contact_person': '赵经理', 'contact_phone': '010-88888804', 'email': 'zhao@bjjk.com', 'address': '北京市朝阳区xxx街101号'},
            {'name': '上海医药贸易公司', 'contact_person': '孙经理', 'contact_phone': '021-66666605', 'email': 'sun@shyy.com', 'address': '上海市浦东新区xxx大道202号'},
        ]

        suppliers = []
        for sup_data in suppliers_data:
            existing = Supplier.query.filter_by(name=sup_data['name']).first()
            if not existing:
                supplier = Supplier(
                    name=sup_data['name'],
                    contact_person=sup_data['contact_person'],
                    contact_phone=sup_data['contact_phone'],
                    email=sup_data['email'],
                    address=sup_data['address'],
                    description='长期合作供应商',
                    is_active=True
                )
                db.session.add(supplier)
                db.session.flush()
                suppliers.append(supplier)
                print(f'   ✅ {sup_data["name"]}')
            else:
                suppliers.append(existing)
                print(f'   ⚠️  {sup_data["name"]} 已存在')

        db.session.commit()

        # 3. 创建客户（10个）
        print('\n3. 创建客户...')
        customers_data = [
            {'name': '烟台芝罘区第一药店', 'contact': '刘店长', 'phone': '0535-11110001', 'address': '烟台市芝罘区xx路11号', 'email': 'liudian@163.com', 'tax_no': '91370602MA3C123401', 'bank': '工商银行烟台分行', 'account_no': '6222021601234567801'},
            {'name': '青岛城阳区医药超市', 'contact': '陈经理', 'phone': '0532-22220002', 'address': '青岛市城阳区xx大道22号', 'email': 'chenyy@qq.com', 'tax_no': '91370214MA3C123402', 'bank': '农业银行青岛分行', 'account_no': '6228481234567890022'},
            {'name': '济南历下区诊所', 'contact': '周医生', 'phone': '0531-33330003', 'address': '济南市历下区xx街33号', 'email': 'zhouys@sina.com', 'tax_no': '91370102MA3C123403', 'bank': '建设银行济南分行', 'account_no': '6217002345678900033'},
            {'name': '潍坊奎文区大药房', 'contact': '吴经理', 'phone': '0536-44440004', 'address': '潍坊市奎文区xx路44号', 'email': 'wujy@126.com', 'tax_no': '91370705MA3C123404', 'bank': '中国银行潍坊分行', 'account_no': '6217856123456789004'},
            {'name': '淄博张店区药店', 'contact': '郑店长', 'phone': '0533-55550005', 'address': '淄博市张店区xx巷55号', 'email': 'zhengd@foxmail.com', 'tax_no': '91370303MA3C123405', 'bank': '交通银行淄博分行', 'account_no': '6222601234567890055'},
            {'name': '临沂兰山区医院药房', 'contact': '冯主任', 'phone': '0539-66660006', 'address': '临沂市兰山区xx大道66号', 'email': 'fengzr@163.com', 'tax_no': '91371302MA3C123406', 'bank': '招商银行临沂分行', 'account_no': '6226091234567890066'},
            {'name': '威海环翠区医药店', 'contact': '卫经理', 'phone': '0631-77770007', 'address': '威海市环翠区xx街77号', 'email': 'weihw@qq.com', 'tax_no': '91371002MA3C123407', 'bank': '光大银行威海分行', 'account_no': '6226621234567890077'},
            {'name': '泰安泰山区药店', 'contact': '蒋店长', 'phone': '0538-88880008', 'address': '泰安市泰山区xx路88号', 'email': 'jiangd@sina.com', 'tax_no': '91370902MA3C123408', 'bank': '兴业银行泰安分行', 'account_no': '6229081234567890088'},
            {'name': '德州德城区连锁药房', 'contact': '沈经理', 'phone': '0534-99990009', 'address': '德州市德城区xx巷99号', 'email': 'shenly@126.com', 'tax_no': '91371402MA3C123409', 'bank': '民生银行德州分行', 'account_no': '6226221234567890099'},
            {'name': '济宁任城区医药超市', 'contact': '韩总监', 'phone': '0537-00000010', 'address': '济宁市任城区xx大道100号', 'email': 'hanzj@foxmail.com', 'tax_no': '91370811MA3C123410', 'bank': '浦发银行济宁分行', 'account_no': '6225211234567890100'},
        ]

        customers = []
        for cust_data in customers_data:
            existing = Customer.query.filter_by(name=cust_data['name']).first()
            if not existing:
                customer = Customer(
                    name=cust_data['name'],
                    contact=cust_data['contact'],
                    phone=cust_data['phone'],
                    address=cust_data['address'],
                    email=cust_data['email'],
                    tax_no=cust_data['tax_no'],
                    bank=cust_data['bank'],
                    account_no=cust_data['account_no'],
                    is_active=True,
                    remark='重点客户'
                )
                db.session.add(customer)
                db.session.flush()
                customers.append(customer)
                print(f'   ✅ {cust_data["name"]}')
            else:
                customers.append(existing)
                print(f'   ⚠️  {cust_data["name"]} 已存在')

        db.session.commit()

        # 4. 获取仓库和商品
        warehouses = Warehouse.query.all()
        products = Product.query.all()
        accounts = BankAccount.query.all()

        print(f'\n已加载: {len(warehouses)} 个仓库, {len(products)} 个商品, {len(accounts)} 个账户')

        # 5. 创建入库批次和库存（10条）
        print('\n4. 创建入库批次和库存...')
        today = datetime.now().date()

        batch_count = 0
        for i, product in enumerate(products[:10]):  # 为前10个商品创建批次
            for warehouse in warehouses[:1]:  # 只在第一个仓库创建
                existing_batch = ProductBatch.query.filter_by(
                    product_id=product.id,
                    warehouse_id=warehouse.id
                ).first()

                if not existing_batch:
                    batch_no = f'BATCH-{today.strftime("%Y%m%d")}-{str(i+1).zfill(3)}'
                    supplier = suppliers[i % len(suppliers)]
                    quantity = random.randint(50, 200)
                    cost_price = float(product.cost_price) if product.cost_price else 100

                    batch = ProductBatch(
                        batch_no=batch_no,
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        supplier_id=supplier.id,
                        code_start=100000 + i * 10000,
                        code_end=100000 + i * 10000 + quantity - 1,
                        total_quantity=quantity,
                        remaining_quantity=quantity,
                        cost_price=cost_price,
                        production_date=today - timedelta(days=random.randint(30, 180)),
                        expire_date=today + timedelta(days=random.randint(365, 730)),
                        status='active',
                        remark='测试批次数据',
                        operator='admin'
                    )
                    db.session.add(batch)
                    db.session.flush()

                    # 创建库存记录
                    inventory = Inventory(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        quantity=quantity
                    )
                    db.session.add(inventory)

                    # 创建入库记录
                    stock_in = StockTransaction(
                        transaction_no=StockTransaction.generate_transaction_no('stock_in'),
                        type='stock_in',
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        quantity=quantity,
                        unit_cost=cost_price,
                        batch_no=batch_no,
                        remark='批量入库测试数据',
                        operator='admin'
                    )
                    db.session.add(stock_in)

                    batch_count += 1
                    print(f'   ✅ 批次 {batch_no} - {product.name} x {quantity}')

        db.session.commit()
        print(f'   共创建 {batch_count} 条批次和库存数据')

        # 6. 创建出库记录（5条）
        print('\n5. 创建出库记录...')
        inventory_records = Inventory.query.all()
        out_count = 0

        for i, inv in enumerate(inventory_records[:5]):
            if inv.quantity >= 10:
                product = inv.product
                customer = customers[i % len(customers)]
                out_quantity = random.randint(5, min(20, inv.quantity // 2))
                unit_cost = float(product.cost_price) if product.cost_price else 100

                stock_out = StockTransaction(
                    transaction_no=StockTransaction.generate_transaction_no('stock_out'),
                    type='stock_out',
                    product_id=product.id,
                    warehouse_id=inv.warehouse_id,
                    customer_id=customer.id,
                    customer_name=customer.name,
                    customer_address=customer.address,
                    quantity=out_quantity,
                    unit_cost=unit_cost,
                    remark='销售出库测试数据',
                    operator='admin'
                )
                db.session.add(stock_out)

                # 更新库存
                inv.quantity -= out_quantity

                out_count += 1
                print(f'   ✅ 出库单 {stock_out.transaction_no} - {product.name} x {out_quantity} → {customer.name}')

        db.session.commit()
        print(f'   共创建 {out_count} 条出库记录')

        # 7. 创建财务收支记录（5条）
        print('\n6. 创建财务收支记录...')

        # 收入记录（3条）
        for i in range(3):
            customer = customers[i % len(customers)]
            account = accounts[i % len(accounts)]
            amount = random.uniform(1000, 10000)

            fin_income = FinancialTransaction(
                transaction_no=FinancialTransaction.generate_transaction_no('income'),
                type='income',
                category='sales_revenue',
                amount=round(amount, 2),
                account_id=account.id,
                direction='in',
                related_type='sale',
                counterparty_name=customer.name,
                payment_method='bank',
                status='completed',
                transaction_date=today - timedelta(days=random.randint(1, 30)),
                operator='admin',
                remark='销售收款测试数据'
            )
            db.session.add(fin_income)
            print(f'   ✅ 收入 {fin_income.transaction_no} - {customer.name} +¥{amount:.2f}')

            # 更新账户余额
            account.current_balance = account.current_balance + Decimal(str(amount))

        # 支出记录（2条）
        for i in range(2):
            supplier = suppliers[i % len(suppliers)]
            account = accounts[(i + 1) % len(accounts)]
            amount = random.uniform(5000, 20000)

            fin_expense = FinancialTransaction(
                transaction_no=FinancialTransaction.generate_transaction_no('expense'),
                type='expense',
                category='purchase_payment',
                amount=round(amount, 2),
                account_id=account.id,
                direction='out',
                related_type='purchase',
                counterparty_name=supplier.name,
                payment_method='bank',
                status='completed',
                transaction_date=today - timedelta(days=random.randint(1, 30)),
                operator='admin',
                remark='采购付款测试数据'
            )
            db.session.add(fin_expense)
            print(f'   ✅ 支出 {fin_expense.transaction_no} - {supplier.name} -¥{amount:.2f}')

            # 更新账户余额
            account.current_balance = account.current_balance - Decimal(str(amount))

        db.session.commit()

        print('\n' + '=' * 60)
        print('测试数据生成完成！')
        print('=' * 60)

        # 打印数据统计
        print('\n📊 数据统计:')
        print(f'   - 银行账户: {BankAccount.query.count()} 条')
        print(f'   - 供应商: {Supplier.query.count()} 条')
        print(f'   - 客户: {Customer.query.count()} 条')
        print(f'   - 商品: {Product.query.count()} 条')
        print(f'   - 批次: {ProductBatch.query.count()} 条')
        print(f'   - 库存: {Inventory.query.count()} 条')
        print(f'   - 出入库记录: {StockTransaction.query.count()} 条')
        print(f'   - 收支记录: {FinancialTransaction.query.count()} 条')


if __name__ == '__main__':
    generate_test_data()
