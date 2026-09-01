#!/usr/bin/env python3
"""
创建库存测试数据：3个商品，每个商品2个有效期批次
用于测试库存数量和批次数量一致性问题
"""

import os
import sys
from datetime import datetime, timedelta, date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db
from models.product import Product
from models.warehouse import Warehouse
from models.product_batch import ProductBatch
from models.batch_code import BatchCode
from models.inventory import Inventory


def create_test_data():
    """创建测试数据"""
    print('=' * 60)
    print('开始创建库存测试数据...')
    print('=' * 60)

    app = create_app()
    with app.app_context():
        # 创建仓库
        warehouse = Warehouse.query.filter_by(code='WH001').first()
        if not warehouse:
            warehouse = Warehouse(
                name='测试仓库',
                code='WH001',
                address='测试地址',
                contact_person='测试',
                contact_phone='13800000000',
                is_active=True
            )
            db.session.add(warehouse)
            db.session.flush()
            print('   ✅ 创建仓库: 测试仓库')

        # 创建商品
        products_data = [
            {'name': '商品A', 'sku': 'A001', 'specification': '规格A', 'unit': '盒'},
            {'name': '商品B', 'sku': 'B001', 'specification': '规格B', 'unit': '盒'},
            {'name': '商品C', 'sku': 'C001', 'specification': '规格C', 'unit': '盒'},
        ]

        products = []
        for prod in products_data:
            existing = Product.query.filter_by(sku=prod['sku']).first()
            if existing:
                products.append(existing)
                print(f'   ✅ 已存在商品: {prod["name"]} ({prod["sku"]})')
            else:
                p = Product(
                    name=prod['name'],
                    sku=prod['sku'],
                    specification=prod['specification'],
                    unit=prod['unit'],
                    is_active=True,
                    cost_price=10.00,
                    selling_price=20.00
                )
                db.session.add(p)
                db.session.flush()
                products.append(p)
                print(f'   ✅ 创建商品: {prod["name"]} ({prod["sku"]})')

        # 为每个商品创建2个有效期批次
        print('\n📦 创建批次数据...')
        code_counter = 100000

        for idx, product in enumerate(products):
            # 批次1：有效期较早
            expire_date1 = date.fromisoformat('2026-08-01')
            batch1 = ProductBatch(
                batch_no=f'BATCH{idx+1}A',
                product_id=product.id,
                warehouse_id=warehouse.id,
                code_start=code_counter,
                code_end=code_counter + 9,
                total_quantity=10,
                remaining_quantity=10,
                cost_price=product.cost_price,
                expire_date=expire_date1,
                status='active',
                operator='admin'
            )
            db.session.add(batch1)
            db.session.flush()

            # 创建批次码
            for i in range(10):
                bc = BatchCode(
                    batch_id=batch1.id,
                    code=f'{code_counter + i}',
                    status='in_stock'
                )
                db.session.add(bc)
            code_counter += 10

            # 批次2：有效期较晚
            expire_date2 = date.fromisoformat('2027-08-01')
            batch2 = ProductBatch(
                batch_no=f'BATCH{idx+1}B',
                product_id=product.id,
                warehouse_id=warehouse.id,
                code_start=code_counter,
                code_end=code_counter + 9,
                total_quantity=10,
                remaining_quantity=10,
                cost_price=product.cost_price,
                expire_date=expire_date2,
                status='active',
                operator='admin'
            )
            db.session.add(batch2)
            db.session.flush()

            # 创建批次码
            for i in range(10):
                bc = BatchCode(
                    batch_id=batch2.id,
                    code=f'{code_counter + i}',
                    status='in_stock'
                )
                db.session.add(bc)
            code_counter += 10

            # 创建库存记录（总数量20）
            inventory = Inventory(
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=20
            )
            db.session.add(inventory)

            print(f'   ✅ {product.name} - 批次A(有效期2026-08-01, 10盒) + 批次B(有效期2027-08-01, 10盒)')

        db.session.commit()

        # 打印统计
        print('\n' + '=' * 60)
        print('测试数据创建完成！')
        print('=' * 60)
        print('\n📊 数据统计:')
        print(f'   - 商品: {len(products)} 个')
        print(f'   - 批次: {ProductBatch.query.count()} 个')
        print(f'   - 批次码: {BatchCode.query.count()} 个')
        print(f'   - 库存: {Inventory.query.count()} 条')

        print('\n📋 库存详情:')
        for inv in Inventory.query.all():
            product = Product.query.get(inv.product_id)
            batches = ProductBatch.query.filter(
                ProductBatch.product_id == inv.product_id,
                ProductBatch.warehouse_id == inv.warehouse_id
            ).all()
            batch_info = ', '.join([f'{b.batch_no}: {b.remaining_quantity}盒(效期{b.expire_date})' for b in batches])
            print(f'   - {product.name}: 库存{inv.quantity}盒, 批次: {batch_info}')


if __name__ == '__main__':
    create_test_data()