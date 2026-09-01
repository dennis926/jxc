#!/usr/bin/env python3
import os
import sys
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db
from models.product import Product
from models.warehouse import Warehouse
from models.inventory import Inventory
from models.product_batch import ProductBatch
from models.stock_transaction import StockTransaction

app = create_app()

with app.app_context():
    print("=" * 60)
    print("创建测试数据")
    print("=" * 60)
    
    warehouse = Warehouse.query.filter_by(code='WH001').first()
    if not warehouse:
        warehouse = Warehouse(name='中央仓库', code='WH001')
        db.session.add(warehouse)
        db.session.commit()
        print("✅ 创建仓库: 中央仓库")
    
    products = []
    for idx, name in enumerate(['A', 'B', 'C'], 1):
        product = Product.query.filter_by(sku=f'SP00{idx}').first()
        if not product:
            product = Product(
                sku=f'SP00{idx}',
                name=f'商品{name}',
                unit='盒',
                cost_price=10 + idx*5,
                selling_price=20 + idx*5,
                is_active=True
            )
            db.session.add(product)
        products.append(product)
    
    db.session.commit()
    print("✅ 创建商品: 商品A, 商品B, 商品C")
    
    for idx, product in enumerate(products, 1):
        expire_dates = [f'2026-0{idx}-01', f'2027-0{idx}-01']
        for expiry_idx, expire_date in enumerate(expire_dates, 1):
            existing_batch = ProductBatch.query.filter(
                ProductBatch.product_id == product.id,
                ProductBatch.warehouse_id == warehouse.id,
                ProductBatch.expire_date == expire_date
            ).first()
            if not existing_batch:
                batch = ProductBatch(
                    batch_no=f'BATCH{idx}{expiry_idx}',
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    code_start=idx * 1000 + expiry_idx * 100,
                    code_end=idx * 1000 + expiry_idx * 100 + 9,
                    total_quantity=10,
                    remaining_quantity=10,
                    cost_price=product.cost_price,
                    production_date=f'2025-0{idx}-01',
                    expire_date=expire_date,
                    operator='系统管理员'
                )
                db.session.add(batch)
                
                record = StockTransaction(
                    transaction_no=f'IN{datetime.now().strftime("%Y%m%d")}{idx}{expiry_idx}',
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    type='stock_in',
                    quantity=10,
                    unit_cost=product.cost_price,
                    batch_no=f'BATCH{idx}{expiry_idx}',
                    operator='系统管理员',
                    remark=f'测试入库: 商品{name} 有效期{expiry_idx}'
                )
                db.session.add(record)
        
        inv = Inventory.query.filter(
            Inventory.product_id == product.id,
            Inventory.warehouse_id == warehouse.id
        ).first()
        if not inv:
            inv = Inventory(
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=20
            )
            db.session.add(inv)
    
    db.session.commit()
    print("✅ 创建库存记录: 每个商品2条不同有效期，各10盒")
    
    print("\n" + "=" * 60)
    print("测试数据创建完成！")
    print("=" * 60)
    print("\n库存状态:")
    inventories = Inventory.query.all()
    for inv in inventories:
        prod = Product.query.get(inv.product_id)
        print(f"  Inventory表: {prod.name} - 总数量: {inv.quantity}盒")
    
    print("\n批次状态:")
    batches = ProductBatch.query.all()
    for batch in batches:
        prod = Product.query.get(batch.product_id)
        print(f"  ProductBatch表: {prod.name} - 有效期: {batch.expire_date} - 剩余数量: {batch.remaining_quantity}盒")
