"""
插入出入库测试数据脚本
直接通过数据库插入，确保操作日志被记录
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from random import randint, choice
from models.database import db
from models.product import Product
from models.warehouse import Warehouse
from models.stock_transaction import StockTransaction
from models.inventory import Inventory
from services.log_service import LogService
from app import create_app


def insert_inventory_test_data():
    """插入出入库测试数据"""
    app = create_app()
    
    with app.app_context():
        print("开始插入出入库测试数据...")
        
        # 获取商品和仓库
        products = Product.query.all()
        warehouses = Warehouse.query.all()
        
        if not products:
            print("没有商品数据，请先运行insert_test_data.py")
            return
        
        if not warehouses:
            print("没有仓库数据")
            return
        
        # 创建第二个仓库用于调拨测试
        if len(warehouses) == 1:
            warehouse2 = Warehouse(
                name='第二仓库',
                code='WH002',
                address='北京市海淀区中关村大街2号',
                contact_person='王经理',
                contact_phone='010-77777777',
                is_active=True
            )
            db.session.add(warehouse2)
            db.session.commit()
            warehouses = Warehouse.query.all()
            print("创建第二仓库")
        
        # 执行入库操作
        stock_in_count = 0
        
        for i, product in enumerate(products[:100]):
            warehouse = warehouses[0]
            
            # 随机入库数量
            quantity = randint(10, 50)
            unit_cost = product.cost_price
            
            # 检查是否已有库存
            inventory = Inventory.query.filter_by(
                product_id=product.id,
                warehouse_id=warehouse.id
            ).first()
            
            if not inventory:
                inventory = Inventory(
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    quantity=0
                )
                db.session.add(inventory)
            
            old_quantity = inventory.quantity
            inventory.quantity += quantity
            
            # 生成单号
            transaction_no = StockTransaction.generate_transaction_no('stock_in')
            
            # 创建库存事务
            transaction = StockTransaction(
                transaction_no=transaction_no,
                type='stock_in',
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=quantity,
                reference_no=f'PO{str(i + 1).zfill(6)}',
                unit_cost=unit_cost,
                remark=f'测试入库 - {product.name}'
            )
            db.session.add(transaction)
            db.session.flush()
            
            # 记录操作日志
            LogService.log_operation(
                user_id=1,
                username='admin',
                operation_type='stock_in',
                module='inventory',
                description=f'商品入库：{product.name}，数量：{quantity}，单号：{transaction_no}',
                reference_type='stock_in',
                reference_no=transaction_no,
                reference_id=transaction.id,
                before_data={'quantity': old_quantity},
                after_data={
                    'product': product.name,
                    'product_id': product.id,
                    'warehouse': warehouse.name,
                    'warehouse_id': warehouse.id,
                    'quantity': quantity,
                    'new_total_quantity': inventory.quantity,
                    'unit_cost': float(unit_cost),
                    'transaction_no': transaction_no,
                    'reference_no': f'PO{str(i + 1).zfill(6)}'
                }
            )
            
            stock_in_count += 1
            print(f"\r入库操作: {stock_in_count} / 100", end="")
            
            # 每20个提交一次
            if stock_in_count % 20 == 0:
                db.session.commit()
        
        db.session.commit()
        print(f"\n\n入库操作完成: {stock_in_count} 条")
        
        # 执行出库操作
        stock_out_count = 0
        
        for i, product in enumerate(products[:50]):
            warehouse = warehouses[0]
            
            # 检查库存
            inventory = Inventory.query.filter_by(
                product_id=product.id,
                warehouse_id=warehouse.id
            ).first()
            
            if not inventory or inventory.quantity <= 0:
                continue
            
            # 出库数量（不超过库存的50%）
            quantity = randint(1, max(1, inventory.quantity // 2))
            unit_cost = product.cost_price
            
            old_quantity = inventory.quantity
            inventory.quantity -= quantity
            
            # 生成单号
            transaction_no = StockTransaction.generate_transaction_no('stock_out')
            
            # 创建库存事务
            transaction = StockTransaction(
                transaction_no=transaction_no,
                type='stock_out',
                product_id=product.id,
                warehouse_id=warehouse.id,
                quantity=quantity,
                reference_no=f'SO{str(i + 1).zfill(6)}',
                unit_cost=unit_cost,
                remark=f'测试出库 - {product.name}'
            )
            db.session.add(transaction)
            db.session.flush()
            
            # 记录操作日志
            LogService.log_operation(
                user_id=1,
                username='admin',
                operation_type='stock_out',
                module='inventory',
                description=f'商品出库：{product.name}，数量：{quantity}，单号：{transaction_no}',
                reference_type='stock_out',
                reference_no=transaction_no,
                reference_id=transaction.id,
                before_data={'quantity': old_quantity},
                after_data={
                    'product': product.name,
                    'product_id': product.id,
                    'warehouse': warehouse.name,
                    'warehouse_id': warehouse.id,
                    'quantity': quantity,
                    'new_total_quantity': inventory.quantity,
                    'unit_cost': float(unit_cost),
                    'transaction_no': transaction_no,
                    'reference_no': f'SO{str(i + 1).zfill(6)}'
                }
            )
            
            stock_out_count += 1
            print(f"\r出库操作: {stock_out_count} / 50", end="")
            
            # 每20个提交一次
            if stock_out_count % 20 == 0:
                db.session.commit()
        
        db.session.commit()
        print(f"\n\n出库操作完成: {stock_out_count} 条")
        
        # 执行调拨操作
        transfer_count = 0
        if len(warehouses) >= 2:
            from_warehouse = warehouses[0]
            to_warehouse = warehouses[1]
            
            for i, product in enumerate(products[:30]):
                # 检查出库仓库库存
                from_inventory = Inventory.query.filter_by(
                    product_id=product.id,
                    warehouse_id=from_warehouse.id
                ).first()
                
                if not from_inventory or from_inventory.quantity <= 0:
                    continue
                
                # 调拨数量
                quantity = randint(1, max(1, from_inventory.quantity // 3))
                
                # 更新库存
                from_inventory.quantity -= quantity
                
                to_inventory = Inventory.query.filter_by(
                    product_id=product.id,
                    warehouse_id=to_warehouse.id
                ).first()
                
                if not to_inventory:
                    to_inventory = Inventory(
                        product_id=product.id,
                        warehouse_id=to_warehouse.id,
                        quantity=0
                    )
                    db.session.add(to_inventory)
                
                to_inventory.quantity += quantity
                
                # 生成单号
                transfer_out_no = StockTransaction.generate_transaction_no('transfer_out')
                transfer_in_no = StockTransaction.generate_transaction_no('transfer_in')
                
                # 创建调出事务
                out_transaction = StockTransaction(
                    transaction_no=transfer_out_no,
                    type='transfer_out',
                    product_id=product.id,
                    warehouse_id=from_warehouse.id,
                    quantity=quantity,
                    reference_no=transfer_in_no,
                    remark=f'调拨至仓库{to_warehouse.name}'
                )
                db.session.add(out_transaction)
                
                # 创建调入事务
                in_transaction = StockTransaction(
                    transaction_no=transfer_in_no,
                    type='transfer_in',
                    product_id=product.id,
                    warehouse_id=to_warehouse.id,
                    quantity=quantity,
                    reference_no=transfer_out_no,
                    remark=f'从仓库{from_warehouse.name}调入'
                )
                db.session.add(in_transaction)
                
                db.session.flush()
                
                # 记录操作日志
                LogService.log_operation(
                    user_id=1,
                    username='admin',
                    operation_type='transfer',
                    module='inventory',
                    description=f'商品调拨：{product.name}，数量：{quantity}，从{from_warehouse.name}到{to_warehouse.name}',
                    reference_type='transfer',
                    reference_no=transfer_out_no,
                    reference_id=out_transaction.id,
                    before_data={
                        'from_warehouse': from_warehouse.name,
                        'from_quantity': from_inventory.quantity + quantity,
                        'to_warehouse': to_warehouse.name,
                        'to_quantity': to_inventory.quantity - quantity
                    },
                    after_data={
                        'product': product.name,
                        'product_id': product.id,
                        'from_warehouse': from_warehouse.name,
                        'from_warehouse_id': from_warehouse.id,
                        'to_warehouse': to_warehouse.name,
                        'to_warehouse_id': to_warehouse.id,
                        'quantity': quantity,
                        'transaction_no': transfer_out_no,
                        'new_from_quantity': from_inventory.quantity,
                        'new_to_quantity': to_inventory.quantity
                    }
                )
                
                transfer_count += 1
                print(f"\r调拨操作: {transfer_count} / 30", end="")
                
                # 每10个提交一次
                if transfer_count % 10 == 0:
                    db.session.commit()
        
        db.session.commit()
        print(f"\n\n调拨操作完成: {transfer_count} 条")
        
        print(f"\n\n出入库测试数据插入完成！")
        print(f"入库记录: {stock_in_count}")
        print(f"出库记录: {stock_out_count}")
        print(f"调拨记录: {transfer_count}")
        
        # 统计操作日志数量
        from models.operation_log import OperationLog
        log_count = OperationLog.query.filter(
            OperationLog.operation_type.in_(['stock_in', 'stock_out', 'transfer'])
        ).count()
        
        print(f"操作日志记录: {log_count} 条")
        
        return stock_in_count, stock_out_count, transfer_count


if __name__ == '__main__':
    insert_inventory_test_data()