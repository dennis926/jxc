#!/usr/bin/env python3
"""
生成20条完整的出入库和调拨测试数据
要求：所有字段必须填写完整，用于测试编辑和删除功能
"""

import os
import sys
from datetime import datetime, timedelta
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
from models.product_batch import ProductBatch
from models.stock_transaction import StockTransaction
from models.batch_code import BatchCode


def init_basic_data():
    """初始化基础数据（仓库、商品、客户、供应商）"""
    print('\n📦 初始化基础数据...')

    # 创建仓库
    warehouse1 = Warehouse.query.filter_by(code='WH001').first()
    if not warehouse1:
        warehouse1 = Warehouse(
            name='中央仓库',
            code='WH001',
            address='北京市朝阳区建国路88号',
            contact_person='张三',
            contact_phone='13800138001',
            is_active=True
        )
        db.session.add(warehouse1)
        db.session.flush()
        print('   ✅ 仓库: 中央仓库 (WH001)')

    warehouse2 = Warehouse.query.filter_by(code='WH002').first()
    if not warehouse2:
        warehouse2 = Warehouse(
            name='区域仓库A',
            code='WH002',
            address='上海市浦东新区世纪大道100号',
            contact_person='李四',
            contact_phone='13800138002',
            is_active=True
        )
        db.session.add(warehouse2)
        db.session.flush()
        print('   ✅ 仓库: 区域仓库A (WH002)')

    # 创建供应商
    suppliers_data = [
        {'name': '青岛诺和诺康生物科技有限公司', 'contact_person': '张经理', 'contact_phone': '0532-88888801', 'address': '山东省青岛市'},
        {'name': '东凯（山东）生物科技有限公司', 'contact_person': '李经理', 'contact_phone': '0531-66666602', 'address': '山东省济南市'},
        {'name': '山东医药采购有限公司', 'contact_person': '王经理', 'contact_phone': '0531-77777703', 'address': '山东省济南市'},
    ]

    suppliers = []
    for sup in suppliers_data:
        existing = Supplier.query.filter_by(name=sup['name']).first()
        if not existing:
            s = Supplier(
                name=sup['name'],
                contact_person=sup['contact_person'],
                contact_phone=sup['contact_phone'],
                address=sup['address'],
                is_active=True
            )
            db.session.add(s)
            db.session.flush()
            suppliers.append(s)
            print(f'   ✅ 供应商: {sup["name"]}')
        else:
            suppliers.append(existing)

    # 创建客户
    customers_data = [
        {'name': '烟台芝罘区第一药店', 'contact': '刘店长', 'phone': '0535-11110001', 'address': '烟台市芝罘区'},
        {'name': '青岛城阳区医药超市', 'contact': '陈经理', 'phone': '0532-22220002', 'address': '青岛市城阳区'},
        {'name': '济南历下区诊所', 'contact': '周医生', 'phone': '0531-33330003', 'address': '济南市历下区'},
    ]

    customers = []
    for cust in customers_data:
        existing = Customer.query.filter_by(name=cust['name']).first()
        if not existing:
            c = Customer(
                name=cust['name'],
                contact=cust['contact'],
                phone=cust['phone'],
                address=cust['address'],
                is_active=True
            )
            db.session.add(c)
            db.session.flush()
            customers.append(c)
            print(f'   ✅ 客户: {cust["name"]}')
        else:
            customers.append(existing)

    # 创建商品
    products_data = [
        {'name': '阿莫西林胶囊', 'sku': 'MED001', 'specification': '0.5g×24粒', 'unit': '盒', 'barcode': '6901234567001', 'selling_price': 28.50, 'cost_price': 18.00},
        {'name': '布洛芬缓释片', 'sku': 'MED002', 'specification': '0.3g×20片', 'unit': '盒', 'barcode': '6901234567002', 'selling_price': 15.80, 'cost_price': 9.50},
        {'name': '复方甘草片', 'sku': 'MED003', 'specification': '100片', 'unit': '瓶', 'barcode': '6901234567003', 'selling_price': 12.00, 'cost_price': 7.20},
        {'name': '维生素C片', 'sku': 'MED004', 'specification': '100mg×100片', 'unit': '瓶', 'barcode': '6901234567004', 'selling_price': 8.50, 'cost_price': 5.00},
        {'name': '氨咖黄敏胶囊', 'sku': 'MED005', 'specification': '12粒', 'unit': '盒', 'barcode': '6901234567005', 'selling_price': 6.00, 'cost_price': 3.50},
    ]

    products = []
    for prod in products_data:
        existing = Product.query.filter_by(sku=prod['sku']).first()
        if not existing:
            p = Product(
                name=prod['name'],
                sku=prod['sku'],
                specification=prod['specification'],
                unit=prod['unit'],
                barcode=prod['barcode'],
                selling_price=prod['selling_price'],
                cost_price=prod['cost_price'],
                is_active=True
            )
            db.session.add(p)
            db.session.flush()
            products.append(p)
            print(f'   ✅ 商品: {prod["name"]} ({prod["sku"]})')
        else:
            products.append(existing)

    db.session.commit()
    return warehouse1, warehouse2, suppliers, customers, products


def generate_full_test_data():
    """生成完整的出入库和调拨测试数据"""
    print('=' * 60)
    print('开始生成出入库和调拨测试数据...')
    print('=' * 60)

    app = create_app()
    with app.app_context():
        # 初始化基础数据
        warehouse1, warehouse2, suppliers, customers, products = init_basic_data()
        warehouses = [warehouse1, warehouse2]

        if len(products) < 3:
            print('❌ 商品数据不足，请检查基础数据初始化')
            return

        if len(warehouses) < 2:
            print('❌ 仓库数据不足，需要至少2个仓库进行调拨测试')
            return

        print(f'\n已加载: {len(products)} 个商品, {len(customers)} 个客户, {len(warehouses)} 个仓库')

        today = datetime.now()
        records_created = []
        counter = StockTransaction.query.count()  # 用于生成唯一序号

        # ==================== 入库记录（10条）====================
        print('\n📥 创建入库记录（10条）...')

        for i in range(10):
            counter += 1
            product = products[i % len(products)]
            supplier = suppliers[i % len(suppliers)]
            warehouse = warehouses[0]  # 使用第一个仓库

            # 生成批次号
            batch_no = f'IN{today.strftime("%Y%m%d")}{str(i+1).zfill(3)}'
            # 生成唯一的入库单号
            stock_in_no = f'IN{today.strftime("%Y%m%d")}{str(counter).zfill(4)}'
            quantity = random.randint(50, 200)
            unit_cost = float(product.cost_price) if product.cost_price else 100.00

            # 检查批次是否已存在
            existing_batch = ProductBatch.query.filter_by(batch_no=batch_no).first()
            if existing_batch:
                print(f'   ⚠️  批次 {batch_no} 已存在，跳过')
                continue

            # 创建批次
            batch = ProductBatch(
                batch_no=batch_no,
                product_id=product.id,
                warehouse_id=warehouse.id,
                supplier_id=supplier.id,
                code_start=200000 + i * 10000,
                code_end=200000 + i * 10000 + quantity - 1,
                total_quantity=quantity,
                remaining_quantity=quantity,
                cost_price=unit_cost,
                production_date=today - timedelta(days=random.randint(30, 180)),
                expire_date=today + timedelta(days=random.randint(365, 730)),
                status='active',
                remark=f'测试入库批次 {i+1}',
                operator='admin'
            )
            db.session.add(batch)
            db.session.flush()

            # 创建入库记录（所有字段完整填写）
            stock_in = StockTransaction(
                transaction_no=stock_in_no,
                type='stock_in',
                product_id=product.id,
                product_name=product.name,  # 快照
                warehouse_id=warehouse.id,
                customer_id=None,
                customer_name=None,
                customer_address=None,
                quantity=quantity,
                unit_cost=unit_cost,
                batch_no=batch_no,
                batch_codes=f'{batch.code_start}-{batch.code_end}',  # 码段
                reference_no=f'PO{today.strftime("%Y%m%d")}{str(i+1).zfill(3)}',  # 关联采购单号
                remark=f'测试入库记录 {i+1}，从{supplier.name}采购',
                operator='admin',
                created_at=today - timedelta(days=random.randint(1, 30))
            )
            db.session.add(stock_in)
            db.session.flush()

            # 为批次创建码段记录
            for code_num in range(min(quantity, 100)):  # 最多创建100个码段记录
                code = BatchCode(
                    batch_id=batch.id,
                    code=f'{batch.code_start + code_num}',
                    status='in_stock',
                    created_at=today - timedelta(days=random.randint(1, 30))
                )
                db.session.add(code)

            records_created.append({
                'type': '入库',
                'no': stock_in.transaction_no,
                'batch_no': batch_no,
                'product': product.name,
                'quantity': quantity
            })
            print(f'   ✅ 入库 {stock_in.transaction_no} - {product.name} x {quantity} (批次: {batch_no})')

        db.session.commit()

        # ==================== 出库记录（5条，部分关联入库）====================
        print('\n📤 创建出库记录（5条）...')

        # 获取刚创建的入库记录
        stock_in_records = StockTransaction.query.filter_by(type='stock_in').order_by(StockTransaction.id.desc()).limit(5).all()
        out_counter = counter  # 从入库计数器继续

        for i, stock_in in enumerate(stock_in_records):
            if stock_in.quantity < 10:
                print(f'   ⚠️  入库 {stock_in.transaction_no} 数量不足，跳过创建出库')
                continue

            out_counter += 1
            customer = customers[i % len(customers)]
            out_quantity = random.randint(10, min(30, stock_in.quantity // 2))
            unit_cost = float(stock_in.unit_cost) if stock_in.unit_cost else 100.00
            # 生成唯一的出库单号
            stock_out_no = f'OUT{today.strftime("%Y%m%d")}{str(out_counter).zfill(4)}'

            # 创建出库记录（所有字段完整填写）
            stock_out = StockTransaction(
                transaction_no=stock_out_no,
                type='stock_out',
                product_id=stock_in.product_id,
                product_name=stock_in.product_name,
                warehouse_id=stock_in.warehouse_id,
                customer_id=customer.id,
                customer_name=customer.name,
                customer_address=customer.address,
                quantity=out_quantity,
                unit_cost=unit_cost,
                batch_no=stock_in.batch_no,  # 关联入库批次
                batch_codes=None,
                reference_no=None,
                remark=f'测试出库记录 {i+1}，销售给{customer.name}',
                operator='admin',
                created_at=today - timedelta(days=random.randint(1, 15))
            )
            db.session.add(stock_out)

            # 更新批次剩余数量
            batch = ProductBatch.query.filter_by(batch_no=stock_in.batch_no).first()
            if batch:
                batch.remaining_quantity -= out_quantity

            records_created.append({
                'type': '出库',
                'no': stock_out.transaction_no,
                'batch_no': stock_in.batch_no,
                'product': stock_in.product_name,
                'quantity': out_quantity
            })
            print(f'   ✅ 出库 {stock_out.transaction_no} - {stock_in.product_name} x {out_quantity} (关联批次: {stock_in.batch_no})')

        db.session.commit()

        # ==================== 调拨记录（5条）====================
        print('\n🔄 创建调拨记录（5条）...')

        # 获取更多入库记录用于调拨
        stock_in_for_transfer = StockTransaction.query.filter_by(type='stock_in').order_by(StockTransaction.id.desc()).limit(5).all()
        warehouse2 = warehouses[1] if len(warehouses) > 1 else warehouses[0]
        tr_counter = out_counter  # 从出库计数器继续

        for i, stock_in in enumerate(stock_in_for_transfer):
            if stock_in.quantity < 20:
                print(f'   ⚠️  入库 {stock_in.transaction_no} 数量不足，跳过创建调拨')
                continue

            tr_counter += 1
            transfer_quantity = random.randint(15, min(50, stock_in.quantity // 2))
            unit_cost = float(stock_in.unit_cost) if stock_in.unit_cost else 100.00

            # 生成调拨单号（使用计数器确保唯一）
            transfer_out_no = f'TO{today.strftime("%Y%m%d")}{str(tr_counter).zfill(4)}'
            transfer_in_no = f'TI{today.strftime("%Y%m%d")}{str(tr_counter).zfill(4)}'
            new_batch_no = f'TR{today.strftime("%Y%m%d")}{str(tr_counter).zfill(4)}'

            # 创建调出记录（从原仓库调出）
            transfer_out = StockTransaction(
                transaction_no=transfer_out_no,
                type='transfer_out',
                product_id=stock_in.product_id,
                product_name=stock_in.product_name,
                warehouse_id=stock_in.warehouse_id,  # 原仓库
                customer_id=None,
                customer_name=None,
                customer_address=None,
                quantity=transfer_quantity,
                unit_cost=unit_cost,
                batch_no=stock_in.batch_no,  # 使用原批次
                batch_codes=f'{stock_in.batch_no}-TR{tr_counter}',
                reference_no=transfer_in_no,  # 关联调入单号
                remark=f'测试调拨记录 {i+1}，从{stock_in.warehouse.name}调出',
                operator='admin',
                created_at=today - timedelta(days=random.randint(1, 10))
            )
            db.session.add(transfer_out)

            # 创建调入记录（到新仓库）
            transfer_in = StockTransaction(
                transaction_no=transfer_in_no,
                type='transfer_in',
                product_id=stock_in.product_id,
                product_name=stock_in.product_name,
                warehouse_id=warehouse2.id,  # 新仓库
                customer_id=None,
                customer_name=None,
                customer_address=None,
                quantity=transfer_quantity,
                unit_cost=unit_cost,
                batch_no=new_batch_no,  # 新批次号
                batch_codes=None,
                reference_no=transfer_out_no,  # 关联调出单号
                remark=f'测试调拨记录 {i+1}，到{warehouse2.name}调入',
                operator='admin',
                created_at=today - timedelta(days=random.randint(1, 10))
            )
            db.session.add(transfer_in)

            records_created.append({
                'type': '调拨',
                'no': f'{transfer_out_no}/{transfer_in_no}',
                'batch_no': f'{stock_in.batch_no}->{new_batch_no}',
                'product': stock_in.product_name,
                'quantity': transfer_quantity
            })
            print(f'   ✅ 调拨 {transfer_out_no}/{transfer_in_no} - {stock_in.product_name} x {transfer_quantity}')

        db.session.commit()

        # ==================== 打印统计 ====================
        print('\n' + '=' * 60)
        print('测试数据生成完成！')
        print('=' * 60)

        # 打印数据统计
        print('\n📊 数据统计:')
        print(f'   - 入库记录: {StockTransaction.query.filter_by(type="stock_in").count()} 条')
        print(f'   - 出库记录: {StockTransaction.query.filter_by(type="stock_out").count()} 条')
        print(f'   - 调拨记录: {StockTransaction.query.filter(StockTransaction.type.in_(["transfer_in", "transfer_out"])).count()} 条')
        print(f'   - 批次记录: {ProductBatch.query.count()} 条')
        print(f'   - 码段记录: {BatchCode.query.count()} 条')

        print('\n📋 本次生成的记录:')
        for idx, record in enumerate(records_created, 1):
            print(f'   {idx}. [{record["type"]}] {record["no"]} - {record["product"]} x {record["quantity"]} (批次: {record["batch_no"]})')

        print('\n🔍 测试编辑/删除功能说明:')
        print('   - 入库记录: 可编辑数量（不能低于已出库+已调拨数量），可删除（需无关联）')
        print('   - 出库记录: 可编辑数量（不能超过原入库剩余数量），可删除')
        print('   - 调拨记录: 可编辑数量（不能低于已出库数量），可删除')


if __name__ == '__main__':
    generate_full_test_data()
