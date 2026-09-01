#!/usr/bin/env python3
"""
检查库存数据
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db
from models.product import Product
from models.warehouse import Warehouse
from models.product_batch import ProductBatch
from models.batch_code import BatchCode
from models.inventory import Inventory
from models.stock_transaction import StockTransaction


def check_data():
    app = create_app()
    with app.app_context():
        print('=' * 60)
        print('当前数据状态')
        print('=' * 60)
        
        print('\n📦 仓库列表:')
        for wh in Warehouse.query.all():
            print(f'   ID={wh.id}, 名称={wh.name}, 编码={wh.code}')
        
        print('\n📋 商品列表:')
        for p in Product.query.all():
            print(f'   ID={p.id}, 名称={p.name}, SKU={p.sku}')
        
        print('\n📊 库存记录:')
        for inv in Inventory.query.all():
            p = Product.query.get(inv.product_id)
            w = Warehouse.query.get(inv.warehouse_id)
            print(f'   商品={p.name}({p.id}), 仓库={w.name}({w.id}), 数量={inv.quantity}')
        
        print('\n📦 批次记录:')
        for batch in ProductBatch.query.all():
            p = Product.query.get(batch.product_id)
            w = Warehouse.query.get(batch.warehouse_id)
            print(f'   批次={batch.batch_no}, 商品={p.name}, 仓库={w.name}, 剩余={batch.remaining_quantity}, 效期={batch.expire_date}')
        
        print('\n🔢 批次码数量:')
        print(f'   总码数: {BatchCode.query.count()}')
        
        print('\n📝 出入库记录:')
        for tx in StockTransaction.query.all():
            print(f'   单号={tx.transaction_no}, 类型={tx.type}, 数量={tx.quantity}')


if __name__ == '__main__':
    check_data()