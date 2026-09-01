"""
生成新的测试数据：10条商品 + 20条出入库记录
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models.database import db
from models.product import Product
from models.warehouse import Warehouse
from models.customer import Customer
from models.stock_transaction import StockTransaction
from models.product_batch import ProductBatch
from datetime import datetime, timedelta
import random

app = create_app()

with app.app_context():
    print("=== 生成新的测试数据 ===\n")

    try:
        # 1. 创建仓库
        print("1. 创建仓库...")
        warehouse = Warehouse(
            name='中央仓库',
            code='WH001',
            address='北京市朝阳区建国路88号',
            contact_person='张三',
            contact_phone='13800138001',
            is_active=True
        )
        db.session.add(warehouse)
        db.session.flush()
        print(f"   ✅ 仓库: {warehouse.name}")

        # 2. 创建客户
        print("\n2. 创建客户...")
        customer = Customer(
            name='北京医药有限公司',
            contact='李四',
            phone='13900139001',
            address='北京市海淀区中关村大街1号',
            is_active=True,
            remark='长期合作客户'
        )
        db.session.add(customer)
        db.session.flush()
        print(f"   ✅ 客户: {customer.name}")

        # 3. 创建10条商品
        print("\n3. 创建10条商品...")
        products_data = [
            {
                'name': '阿莫西林胶囊',
                'sku': 'MED001',
                'specification': '0.5g×24粒',
                'unit': '盒',
                'category': '西药',
                'barcode': '6901234567001',
                'approval_no': '国药准字H12345678',
                'manufacturer': '北京制药有限公司',
                'dosage_form': '胶囊剂',
                'retail_price': 28.50,
                'cost_price': 18.00,
                'min_stock': 100
            },
            {
                'name': '布洛芬缓释片',
                'sku': 'MED002',
                'specification': '0.3g×20片',
                'unit': '盒',
                'category': '西药',
                'barcode': '6901234567002',
                'approval_no': '国药准字H12345679',
                'manufacturer': '上海制药厂',
                'dosage_form': '片剂',
                'retail_price': 15.80,
                'cost_price': 9.50,
                'min_stock': 150
            },
            {
                'name': '复方甘草片',
                'sku': 'MED003',
                'specification': '100片',
                'unit': '瓶',
                'category': '中成药',
                'barcode': '6901234567003',
                'approval_no': '国药准字Z12345678',
                'manufacturer': '广州中药厂',
                'dosage_form': '片剂',
                'retail_price': 12.00,
                'cost_price': 7.20,
                'min_stock': 200
            },
            {
                'name': '维生素C片',
                'sku': 'MED004',
                'specification': '100mg×100片',
                'unit': '瓶',
                'category': '保健品',
                'barcode': '6901234567004',
                'approval_no': '卫食健字(2000)第1234号',
                'manufacturer': '深圳保健品公司',
                'dosage_form': '片剂',
                'retail_price': 8.50,
                'cost_price': 5.00,
                'min_stock': 300
            },
            {
                'name': '感冒灵颗粒',
                'sku': 'MED005',
                'specification': '10g×9袋',
                'unit': '盒',
                'category': '中成药',
                'barcode': '6901234567005',
                'approval_no': '国药准字Z12345679',
                'manufacturer': '广州制药集团',
                'dosage_form': '颗粒剂',
                'retail_price': 18.00,
                'cost_price': 11.00,
                'min_stock': 200
            },
            {
                'name': '阿司匹林肠溶片',
                'sku': 'MED006',
                'specification': '50mg×30片',
                'unit': '盒',
                'category': '西药',
                'barcode': '6901234567006',
                'approval_no': '国药准字H12345680',
                'manufacturer': '天津制药厂',
                'dosage_form': '片剂',
                'retail_price': 22.00,
                'cost_price': 13.50,
                'min_stock': 120
            },
            {
                'name': '板蓝根颗粒',
                'sku': 'MED007',
                'specification': '10g×20袋',
                'unit': '盒',
                'category': '中成药',
                'barcode': '6901234567007',
                'approval_no': '国药准字Z12345680',
                'manufacturer': '北京中药厂',
                'dosage_form': '颗粒剂',
                'retail_price': 16.50,
                'cost_price': 10.00,
                'min_stock': 180
            },
            {
                'name': '硝苯地平缓释片',
                'sku': 'MED008',
                'specification': '20mg×30片',
                'unit': '盒',
                'category': '西药',
                'barcode': '6901234567008',
                'approval_no': '国药准字H12345681',
                'manufacturer': '上海制药有限公司',
                'dosage_form': '缓释片',
                'retail_price': 35.00,
                'cost_price': 21.00,
                'min_stock': 80
            },
            {
                'name': '双黄连口服液',
                'sku': 'MED009',
                'specification': '10ml×12支',
                'unit': '盒',
                'category': '中成药',
                'barcode': '6901234567009',
                'approval_no': '国药准字Z12345681',
                'manufacturer': '哈尔滨制药厂',
                'dosage_form': '口服液',
                'retail_price': 24.00,
                'cost_price': 14.50,
                'min_stock': 150
            },
            {
                'name': '蒙脱石散',
                'sku': 'MED010',
                'specification': '3g×10袋',
                'unit': '盒',
                'category': '西药',
                'barcode': '6901234567010',
                'approval_no': '国药准字H12345682',
                'manufacturer': '成都制药厂',
                'dosage_form': '散剂',
                'retail_price': 26.00,
                'cost_price': 15.80,
                'min_stock': 100
            }
        ]

        products = []
        for i, prod_data in enumerate(products_data, 1):
            product = Product(
                sku=prod_data['sku'],
                name=prod_data['name'],
                specification=prod_data['specification'],
                unit=prod_data['unit'],
                category=prod_data['category'],
                barcode=prod_data['barcode'],
                approval_no=prod_data['approval_no'],
                manufacturer=prod_data['manufacturer'],
                dosage_form=prod_data['dosage_form'],
                selling_price=prod_data['retail_price'],
                cost_price=prod_data['cost_price'],
                min_stock=prod_data['min_stock'],
                is_active=True
            )
            db.session.add(product)
            db.session.flush()
            products.append(product)
            print(f"   ✅ {i}. {product.name} ({product.sku})")

        db.session.commit()
        print(f"\n   ✅ 成功创建 {len(products)} 条商品")

        # 4. 创建20条出入库记录
        print("\n4. 创建20条出入库记录...")

        today = datetime.now()
        stock_in_count = 0
        stock_out_count = 0

        # 前10条为入库记录
        for i in range(10):
            product = random.choice(products)
            quantity = random.randint(50, 200)
            unit_cost = float(product.cost_price)
            created_at = today - timedelta(days=random.randint(1, 30))

            transaction_no = f"IN{today.strftime('%Y%m%d')}{str(i+1).zfill(3)}"

            # 创建批次
            batch_no = f"BATCH{today.strftime('%Y%m%d')}{str(i+1).zfill(3)}"
            code_start = random.randint(10000000, 50000000)
            batch = ProductBatch(
                batch_no=batch_no,
                product_id=product.id,
                warehouse_id=warehouse.id,
                code_start=code_start,
                code_end=code_start + quantity - 1,
                total_quantity=quantity,
                remaining_quantity=quantity,
                production_date=created_at - timedelta(days=random.randint(30, 180)),
                expire_date=created_at + timedelta(days=random.randint(365, 730)),
                status='active'
            )
            db.session.add(batch)

            # 创建入库记录
            tx = StockTransaction(
                transaction_no=transaction_no,
                type='stock_in',
                product_id=product.id,
                product_name=product.name,
                warehouse_id=warehouse.id,
                quantity=quantity,
                unit_cost=unit_cost,
                batch_no=batch_no,
                operator='admin',
                created_at=created_at
            )
            db.session.add(tx)
            stock_in_count += 1
            print(f"   ✅ 入库 {stock_in_count}: {product.name} × {quantity}")

        # 后10条为出库记录
        for i in range(10):
            product = random.choice(products)
            quantity = random.randint(10, 50)
            unit_cost = float(product.cost_price)
            created_at = today - timedelta(days=random.randint(1, 15))

            transaction_no = f"OUT{today.strftime('%Y%m%d')}{str(i+1).zfill(3)}"

            # 创建出库记录
            tx = StockTransaction(
                transaction_no=transaction_no,
                type='stock_out',
                product_id=product.id,
                product_name=product.name,
                warehouse_id=warehouse.id,
                customer_id=customer.id,
                customer_name=customer.name,
                quantity=quantity,
                unit_cost=unit_cost,
                operator='admin',
                created_at=created_at
            )
            db.session.add(tx)
            stock_out_count += 1
            print(f"   ✅ 出库 {stock_out_count}: {product.name} × {quantity}")

        db.session.commit()

        print(f"\n   ✅ 成功创建 {stock_in_count} 条入库记录")
        print(f"   ✅ 成功创建 {stock_out_count} 条出库记录")

        print("\n" + "=" * 50)
        print("✅ 测试数据生成完成！")
        print(f"   📦 商品: {len(products)} 条")
        print(f"   📥 入库: {stock_in_count} 条")
        print(f"   📤 出库: {stock_out_count} 条")
        print("=" * 50)

    except Exception as e:
        db.session.rollback()
        print(f"\n❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
