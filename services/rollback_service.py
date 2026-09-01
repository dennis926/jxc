"""
撤销服务模块
支持所有操作的撤销 - 使用before_data恢复数据
"""

import json
from datetime import datetime
from models.database import db
from models.operation_log import OperationLog
from models.stock_transaction import StockTransaction
from models.inventory import Inventory
from models.batch_code import BatchCode
from models.product import Product
from models.warehouse import Warehouse
from models.customer import Customer
from models.supplier import Supplier
from models.purchase_order import PurchaseOrder, PurchaseOrderItem
from models.user import User
from services.log_service import LogService


class RollbackService:
    
    def _parse_data(self, data):
        """解析JSON数据"""
        if isinstance(data, str):
            try:
                return json.loads(data)
            except:
                return None
        return data
    
    def _check_related_operations(self, log):
        """检查是否有关联的后续操作"""
        reference_id = log.reference_id
        module = log.module
        reference_no = log.reference_no
        log_time = log.created_at
        
        # 查询该reference_id或reference_no相关的后续操作
        related = OperationLog.query.filter(
            OperationLog.created_at > log_time,
            OperationLog.reference_id == reference_id,
            OperationLog.id != log.id
        ).filter(
            OperationLog.operation_type.in_(['delete', 'update'])
        ).all()
        
        return related
    
    def _rollback_inventory_operation(self, log):
        """撤销库存操作（入库、出库、调拨）"""
        before_data = self._parse_data(log.before_data)
        after_data = self._parse_data(log.after_data)
        
        if not before_data and not after_data:
            return False, '操作数据不存在'
        
        product_id = (before_data or after_data).get('product_id')
        warehouse_id = (before_data or after_data).get('warehouse_id')
        quantity = (before_data or after_data).get('quantity')
        transaction_no = (before_data or after_data).get('transaction_no')
        batch_codes = (before_data or after_data).get('batch_codes', [])
        
        if not product_id or not warehouse_id:
            return False, '操作数据不完整'
        
        operation_type = log.operation_type
        
        # 查找对应的库存事务
        tx_type_map = {
            'stock_in': 'stock_in',
            'stock_out': 'stock_out',
            'transfer': 'transfer_out'
        }
        
        tx = None
        if transaction_no:
            tx_type = tx_type_map.get(operation_type)
            if tx_type:
                tx = StockTransaction.query.filter_by(
                    transaction_no=transaction_no,
                    type=tx_type
                ).first()
        
        if operation_type == 'stock_in':
            # 撤销入库：减少库存
            inventory = Inventory.query.filter_by(
                product_id=product_id,
                warehouse_id=warehouse_id
            ).first()
            
            if not inventory:
                return False, '库存记录不存在'
            
            if inventory.quantity < quantity:
                return False, f'库存不足，无法撤销入库'
            
            inventory.quantity -= quantity
            
            # 恢复码段状态
            if batch_codes:
                for code in batch_codes:
                    bc = BatchCode.query.filter_by(code=str(code).strip()).first()
                    if bc:
                        bc.status = 'in_stock'
            
            if tx:
                db.session.delete(tx)
                
        elif operation_type == 'stock_out':
            # 撤销出库：增加库存
            inventory = Inventory.query.filter_by(
                product_id=product_id,
                warehouse_id=warehouse_id
            ).first()
            
            if not inventory:
                inventory = Inventory(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
                db.session.add(inventory)
            
            inventory.quantity += quantity
            
            # 恢复码段状态
            if batch_codes:
                for code in batch_codes:
                    bc = BatchCode.query.filter_by(code=str(code).strip()).first()
                    if bc:
                        bc.status = 'used'
            
            if tx:
                db.session.delete(tx)
                
        elif operation_type == 'transfer':
            # 撤销调拨
            from_warehouse_id = (before_data or after_data).get('from_warehouse_id')
            to_warehouse_id = (before_data or after_data).get('to_warehouse_id')
            
            if not from_warehouse_id or not to_warehouse_id:
                return False, '调拨数据不完整'
            
            # 调出仓库增加库存
            from_inv = Inventory.query.filter_by(
                product_id=product_id,
                warehouse_id=from_warehouse_id
            ).first()
            
            if not from_inv:
                from_inv = Inventory(product_id=product_id, warehouse_id=from_warehouse_id, quantity=0)
                db.session.add(from_inv)
            
            from_inv.quantity += quantity
            
            # 调入仓库减少库存
            to_inv = Inventory.query.filter_by(
                product_id=product_id,
                warehouse_id=to_warehouse_id
            ).first()
            
            if to_inv and to_inv.quantity >= quantity:
                to_inv.quantity -= quantity
            
            # 删除调拨事务
            if tx:
                db.session.delete(tx)
                # 删除对应的调入事务
                if tx.reference_no:
                    in_tx = StockTransaction.query.filter_by(
                        transaction_no=tx.reference_no,
                        type='transfer_in'
                    ).first()
                    if in_tx:
                        db.session.delete(in_tx)
        
        # 记录撤销日志
        LogService.log_operation(
            user_id=log.user_id,
            username=log.username,
            operation_type='rollback',
            module=log.module,
            description=f'撤销{log.module}操作：{log.description}',
            reference_type='rollback',
            reference_id=log.id
        )
        
        db.session.commit()
        return True, '撤销成功'
    
    def _rollback_delete_operation(self, log):
        """撤销删除操作 - 恢复被删除的数据"""
        before_data = self._parse_data(log.before_data)
        
        if not before_data:
            return False, '无备份数据，无法撤销删除'
        
        module = log.module
        model_class = self._get_model_class(module)
        reference_id = log.reference_id
        
        if not model_class:
            return False, f'不支持撤销 {module} 模块的删除操作'
        
        try:
            # 首先检查记录是否还存在（软删除的情况）
            existing_record = model_class.query.get(reference_id) if reference_id else None
            
            # 根据模块类型恢复数据
            if module == 'product':
                if existing_record:
                    # 软删除情况，只恢复is_active
                    existing_record.is_active = before_data.get('is_active', True)
                else:
                    # 硬删除情况，重新创建
                    product = Product(
                        id=before_data.get('id'),
                        sku=before_data.get('sku'),
                        name=before_data.get('name'),
                        category=before_data.get('category'),
                        unit=before_data.get('unit'),
                        cost_price=before_data.get('cost_price'),
                        selling_price=before_data.get('selling_price'),
                        barcode=before_data.get('barcode'),
                        description=before_data.get('description'),
                        is_active=before_data.get('is_active', True),
                        min_stock=before_data.get('min_stock', 0)
                    )
                    db.session.add(product)
                
            elif module == 'customer':
                if existing_record:
                    existing_record.is_active = before_data.get('is_active', True)
                else:
                    customer = Customer(
                        id=before_data.get('id'),
                        name=before_data.get('name'),
                        contact=before_data.get('contact'),
                        phone=before_data.get('phone'),
                        address=before_data.get('address'),
                        email=before_data.get('email'),
                        is_active=before_data.get('is_active', True)
                    )
                    db.session.add(customer)
                
            elif module == 'supplier':
                if existing_record:
                    existing_record.is_active = before_data.get('is_active', True)
                else:
                    supplier = Supplier(
                        id=before_data.get('id'),
                        name=before_data.get('name'),
                        contact=before_data.get('contact'),
                        phone=before_data.get('phone'),
                        address=before_data.get('address'),
                        email=before_data.get('email'),
                        is_active=before_data.get('is_active', True)
                    )
                    db.session.add(supplier)
                
            elif module == 'warehouse':
                if existing_record:
                    existing_record.is_active = before_data.get('is_active', True)
                else:
                    warehouse = Warehouse(
                        id=before_data.get('id'),
                        name=before_data.get('name'),
                        address=before_data.get('address'),
                        contact=before_data.get('contact'),
                        phone=before_data.get('phone'),
                        is_active=before_data.get('is_active', True)
                    )
                    db.session.add(warehouse)
                
            elif module == 'user':
                if existing_record:
                    existing_record.is_active = before_data.get('is_active', True)
                else:
                    user = User(
                        id=before_data.get('id'),
                        username=before_data.get('username'),
                        email=before_data.get('email'),
                        full_name=before_data.get('full_name'),
                        role_id=before_data.get('role_id'),
                        is_active=before_data.get('is_active', True)
                    )
                    db.session.add(user)
                
            elif module == 'purchase':
                if existing_record:
                    existing_record.status = before_data.get('status', 'pending')
                else:
                    po_data = before_data.get('purchase_order', {})
                    po = PurchaseOrder(
                        id=before_data.get('id'),
                        order_no=po_data.get('order_no'),
                        supplier_id=po_data.get('supplier_id'),
                        total_amount=po_data.get('total_amount', 0),
                        status=po_data.get('status', 'pending'),
                        order_date=datetime.strptime(po_data.get('order_date'), '%Y-%m-%d') if po_data.get('order_date') else datetime.now(),
                        expected_date=datetime.strptime(po_data.get('expected_date'), '%Y-%m-%d') if po_data.get('expected_date') else None,
                        remark=po_data.get('remark')
                    )
                    db.session.add(po)
                    
                    items = before_data.get('items', [])
                    for item_data in items:
                        item = PurchaseOrderItem(
                            id=item_data.get('id'),
                            purchase_order_id=po.id,
                            product_id=item_data.get('product_id'),
                            quantity=item_data.get('quantity'),
                            unit_price=item_data.get('unit_price'),
                            subtotal=item_data.get('subtotal', 0)
                        )
                        db.session.add(item)
            
            # 记录撤销日志
            LogService.log_operation(
                user_id=log.user_id,
                username=log.username,
                operation_type='rollback',
                module=log.module,
                description=f'撤销删除：恢复了{self._get_module_name(module)}',
                reference_type='rollback',
                reference_id=log.id
            )
            
            db.session.commit()
            return True, f'成功恢复{self._get_module_name(module)}'
            
        except Exception as e:
            db.session.rollback()
            return False, f'恢复失败: {str(e)}'
    
    def _rollback_create_operation(self, log):
        """撤销创建操作 - 删除刚创建的数据"""
        reference_id = log.reference_id
        module = log.module
        
        if not reference_id:
            return False, '无法找到创建的记录'
        
        model_class = self._get_model_class(module)
        
        if not model_class:
            return False, f'不支持撤销 {module} 模块的创建操作'
        
        try:
            record = model_class.query.get(reference_id)
            
            if not record:
                return False, '找不到要删除的记录'
            
            db.session.delete(record)
            
            # 记录撤销日志
            LogService.log_operation(
                user_id=log.user_id,
                username=log.username,
                operation_type='rollback',
                module=log.module,
                description=f'撤销创建：删除了{self._get_module_name(module)}记录',
                reference_type='rollback',
                reference_id=log.id
            )
            
            db.session.commit()
            return True, f'已删除新创建的{self._get_module_name(module)}记录'
            
        except Exception as e:
            db.session.rollback()
            return False, f'撤销失败: {str(e)}'
    
    def _rollback_update_operation(self, log):
        """撤销更新操作 - 恢复更新前的数据"""
        before_data = self._parse_data(log.before_data)
        
        if not before_data:
            return False, '无备份数据，无法撤销更新'
        
        module = log.module
        reference_id = log.reference_id
        model_class = self._get_model_class(module)
        
        if not model_class:
            return False, f'不支持撤销 {module} 模块的更新操作'
        
        try:
            record = model_class.query.get(reference_id)
            
            if not record:
                return False, '找不到要恢复的记录'
            
            # 恢复字段
            for key, value in before_data.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            
            # 记录撤销日志
            LogService.log_operation(
                user_id=log.user_id,
                username=log.username,
                operation_type='rollback',
                module=log.module,
                description=f'撤销更新：恢复了{self._get_module_name(module)}的更改',
                reference_type='rollback',
                reference_id=log.id
            )
            
            db.session.commit()
            return True, f'已恢复{self._get_module_name(module)}的更改'
            
        except Exception as e:
            db.session.rollback()
            return False, f'撤销失败: {str(e)}'
    
    def _get_model_class(self, module):
        """获取模块对应的模型类"""
        model_map = {
            'product': Product,
            'customer': Customer,
            'supplier': Supplier,
            'warehouse': Warehouse,
            'user': User,
            'purchase': PurchaseOrder,
            'inventory': None,  # 库存通过_special处理
            'transaction': None,  # 事务通过_special处理
        }
        return model_map.get(module)
    
    def _get_module_name(self, module):
        """获取模块中文名称"""
        name_map = {
            'product': '商品',
            'customer': '客户',
            'supplier': '供应商',
            'warehouse': '仓库',
            'user': '用户',
            'purchase': '采购订单',
            'inventory': '库存',
            'transaction': '库存事务',
        }
        return name_map.get(module, module)
    
    def rollback(self, log_id):
        """通用撤销方法"""
        log = OperationLog.query.get(log_id)
        
        if not log:
            return False, '操作日志不存在'
        
        # 检查是否有关联的后续操作
        related = self._check_related_operations(log)
        if related:
            related_desc = '、'.join([f'{r.module}.{r.operation_type}' for r in related[:3]])
            if len(related) > 3:
                related_desc += f'等{len(related)}条'
            return False, f'存在关联的后续操作（{related_desc}），需要先撤销后续操作'
        
        operation_type = log.operation_type
        module = log.module
        
        # 库存相关操作使用专门的撤销逻辑
        if module in ['inventory', 'transaction']:
            return self._rollback_inventory_operation(log)
        
        # 根据操作类型选择撤销方法
        if operation_type == 'delete':
            return self._rollback_delete_operation(log)
        elif operation_type == 'create':
            return self._rollback_create_operation(log)
        elif operation_type == 'update':
            return self._rollback_update_operation(log)
        elif operation_type in ['stock_in', 'stock_out', 'transfer']:
            return self._rollback_inventory_operation(log)
        else:
            return False, f'不支持撤销 {operation_type} 类型的操作'


# 创建单例实例
rollback_service = RollbackService()
