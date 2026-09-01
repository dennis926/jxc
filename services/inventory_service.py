import logging
from models import db
from models.inventory import Inventory
from models.stock_transaction import StockTransaction
from models.product import Product
from models.warehouse import Warehouse
from models.purchase_order import PurchaseOrder, PurchaseOrderItem
from models.batch_code import BatchCode
from models.product_batch import ProductBatch
from models.customer import Customer
from datetime import datetime
from services.log_service import LogService
from flask import session

logger = logging.getLogger(__name__)


class InventoryService:
    """库存业务逻辑服务"""

    @staticmethod
    def _get_or_create_inventory(product_id: int, warehouse_id: int) -> Inventory:
        """获取或创建库存记录"""
        inventory = Inventory.query.filter_by(
            product_id=product_id,
            warehouse_id=warehouse_id
        ).first()

        if not inventory:
            inventory = Inventory(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=0
            )
            db.session.add(inventory)
            db.session.flush()

        return inventory

    @staticmethod
    def _log_operation_safe(operation_type, module, description, **kwargs):
        """安全记录日志，失败不影响主流程"""
        try:
            LogService.log_operation(
                user_id=session.get('user_id'),
                username=session.get('username'),
                operation_type=operation_type,
                module=module,
                description=description,
                **kwargs
            )
        except Exception as e:
            logger.error(f"日志记录失败: {e}", exc_info=True)

    @staticmethod
    def stock_in(product_id: int, warehouse_id: int, quantity: int,
                 unit_cost=0, reference_no='', operator='', remark='', batch_codes=None,
                 production_date=None, expire_date=None):
        """
        入库操作
        :param product_id: 商品ID
        :param warehouse_id: 仓库ID
        :param quantity: 入库数量
        :param unit_cost: 单位成本
        :param reference_no: 关联单号
        :param operator: 操作人
        :param remark: 备注
        :param batch_codes: 批次码列表（可选）
        :param production_date: 生产日期（可选，格式：YYYY-MM-DD）
        :param expire_date: 过期日期（可选，格式：YYYY-MM-DD）
        :return: StockTransaction 记录
        """
        try:
            if quantity <= 0:
                raise ValueError('入库数量必须大于0')

            # 检查商品是否存在且启用
            product = Product.query.get(product_id)
            if not product:
                raise ValueError('商品不存在')
            if not product.is_active:
                raise ValueError(f'商品"{product.name}"已停用，无法进行入库操作')

            # 解析日期
            prod_date = None
            exp_date = None
            if production_date:
                try:
                    prod_date = datetime.strptime(production_date, '%Y-%m-%d').date()
                except Exception:
                    pass
            if expire_date:
                try:
                    exp_date = datetime.strptime(expire_date, '%Y-%m-%d').date()
                except Exception:
                    pass

            # 验证日期逻辑
            if prod_date and exp_date and exp_date <= prod_date:
                raise ValueError('过期日期必须晚于生产日期')

            # 生成入库单号
            transaction_no = StockTransaction.generate_transaction_no('stock_in')

            # 处理范围格式的 batch_codes（如 "100001-100500" 或 "PREFIX100001-PREFIX100500"）
            if batch_codes and isinstance(batch_codes, str):
                if '-' in batch_codes and batch_codes.count(',') == 0:
                    import re
                    range_match = re.match(r'^([A-Za-z]*)(\d+)-([A-Za-z]*)(\d+)$', batch_codes)
                    if range_match:
                        prefix1, start_str, prefix2, end_str = range_match.groups()
                        prefix = prefix1
                        start_num = int(start_str)
                        end_num = int(end_str)
                        if end_num - start_num > 10000:
                            raise ValueError('码段范围过大（超过10000），请缩小范围')
                        batch_codes = [f'{prefix}{str(i).zfill(len(start_str))}' for i in range(start_num, end_num + 1)]
                    else:
                        batch_codes = None
                else:
                    batch_codes = None

            # 创建批次和批次码（如果提供了批次码）
            if batch_codes and len(batch_codes) > 0:
                batch_no = ProductBatch.generate_batch_no()

                import re
                numeric_parts = []
                for c in batch_codes:
                    match = re.search(r'(\d+)$', c)
                    if match:
                        numeric_parts.append(int(match.group(1)))
                    else:
                        numeric_parts.append(0)

                code_start = min(numeric_parts) if numeric_parts else 0
                code_end = max(numeric_parts) if numeric_parts else 0

                batch = ProductBatch(
                    batch_no=batch_no,
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    code_start=code_start,
                    code_end=code_end,
                    total_quantity=len(batch_codes),
                    remaining_quantity=len(batch_codes),
                    cost_price=unit_cost,
                    production_date=prod_date,
                    expire_date=exp_date,
                    remark=remark,
                    operator=operator or 'admin',
                    status='active'
                )
                db.session.add(batch)
                db.session.flush()

                for code in batch_codes:
                    batch_code = BatchCode(
                        batch_id=batch.id,
                        code=str(code),
                        status='in_stock'
                    )
                    db.session.add(batch_code)

                remark = f'{remark}，批次：{batch_no}，码段：{code_start}-{code_end}' if remark else f'批次：{batch_no}，码段：{code_start}-{code_end}'

                transaction_batch_no = batch_no
                transaction_batch_codes = ','.join(str(c) for c in batch_codes)
            else:
                transaction_batch_no = ''
                transaction_batch_codes = ''

            # 创建出入库记录
            transaction = StockTransaction(
                transaction_no=transaction_no,
                type='stock_in',
                product_id=product_id,
                product_name=product.name if product else '',
                warehouse_id=warehouse_id,
                quantity=quantity,
                unit_cost=unit_cost,
                reference_no=reference_no,
                batch_no=transaction_batch_no,
                batch_codes=transaction_batch_codes,
                remark=remark,
                operator=operator
            )
            db.session.add(transaction)
            db.session.flush()

            # 更新库存
            inventory = InventoryService._get_or_create_inventory(product_id, warehouse_id)
            old_quantity = inventory.quantity
            inventory.quantity += quantity

            # 记录日志
            warehouse = Warehouse.query.get(warehouse_id)
            InventoryService._log_operation_safe(
                operation_type='stock_in',
                module='inventory',
                description=f'商品入库：{product.name if product else product_id}，数量：{quantity}，单号：{transaction_no}',
                reference_type='stock_in',
                reference_no=transaction_no,
                reference_id=transaction.id,
                before_data={'quantity': old_quantity},
                after_data={
                    'product': product.name if product else None,
                    'product_id': product_id,
                    'warehouse': warehouse.name if warehouse else None,
                    'warehouse_id': warehouse_id,
                    'quantity': quantity,
                    'new_total_quantity': inventory.quantity,
                    'unit_cost': unit_cost,
                    'transaction_no': transaction_no,
                    'reference_no': reference_no,
                    'batch_no': transaction_batch_no,
                    'batch_codes': batch_codes if batch_codes else []
                }
            )

            db.session.commit()
            return transaction

        except ValueError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f'入库操作失败: {e}', exc_info=True)
            raise ValueError(f'入库操作失败: {str(e)}')

    @staticmethod
    def stock_out(product_id: int, warehouse_id: int, quantity: int,
                  reference_no='', operator='', remark='', customer_id=None, batch_codes=None, unit_cost=None):
        """
        出库操作
        :param product_id: 商品ID
        :param warehouse_id: 仓库ID
        :param quantity: 出库数量
        :param reference_no: 关联单号
        :param operator: 操作人
        :param remark: 备注
        :param customer_id: 客户ID（可选）
        :param batch_codes: 批次码列表（可选）
        :param unit_cost: 单位成本（可选）
        :return: StockTransaction 记录
        """
        try:
            if quantity <= 0:
                raise ValueError('出库数量必须大于0')

            # 检查商品是否存在且启用
            product = Product.query.get(product_id)
            if not product:
                raise ValueError('商品不存在')
            if not product.is_active:
                raise ValueError(f'商品"{product.name}"已停用，无法进行出库操作')

            # 检查库存是否足够
            inventory = Inventory.query.filter_by(
                product_id=product_id,
                warehouse_id=warehouse_id
            ).first()

            if not inventory or inventory.quantity < quantity:
                raise ValueError(f'库存不足，当前库存: {inventory.quantity if inventory else 0}')

            # 获取单位成本
            tx_unit_cost = unit_cost
            if tx_unit_cost is None:
                if batch_codes and len(batch_codes) > 0:
                    first_code = batch_codes[0]
                    batch_code = BatchCode.query.join(
                        ProductBatch, BatchCode.batch_id == ProductBatch.id
                    ).filter(
                        BatchCode.code == first_code,
                        ProductBatch.product_id == product_id,
                        ProductBatch.warehouse_id == warehouse_id
                    ).first()
                    if batch_code and batch_code.batch:
                        tx_unit_cost = batch_code.batch.cost_price
                if tx_unit_cost is None:
                    tx_unit_cost = product.cost_price if product.cost_price else 0

            # 处理批次码
            transaction_batch_no = ''
            transaction_batch_codes = ''
            if batch_codes and len(batch_codes) > 0:
                used_codes = []
                for code in batch_codes:
                    batch_code = BatchCode.query.join(ProductBatch, BatchCode.batch_id == ProductBatch.id).filter(
                        BatchCode.code == code,
                        BatchCode.status == 'in_stock',
                        ProductBatch.product_id == product_id,
                        ProductBatch.warehouse_id == warehouse_id
                    ).first()
                    if not batch_code:
                        raise ValueError(f'批次码 {code} 不存在或已被使用，或不属于该商品/仓库')
                    used_codes.append(batch_code)

                # 更新批次码状态
                customer = Customer.query.get(customer_id) if customer_id else None
                for bc in used_codes:
                    bc.status = 'sold'
                    bc.customer_id = customer_id
                    bc.customer_name = customer.name if customer else None
                    bc.stock_out_no = StockTransaction.generate_transaction_no('stock_out')
                    bc.sold_at = datetime.now()

                # 更新批次剩余数量
                batch_ids = set(bc.batch_id for bc in used_codes)
                batch_no_list = []
                for batch_id in batch_ids:
                    batch = ProductBatch.query.get(batch_id)
                    if batch:
                        batch_no_list.append(batch.batch_no)
                        remaining = BatchCode.query.filter_by(batch_id=batch_id, status='in_stock').count()
                        batch.remaining_quantity = remaining
                        if batch.remaining_quantity == 0:
                            batch.status = 'depleted'

                transaction_batch_no = ','.join(batch_no_list)
                transaction_batch_codes = ','.join(str(c) for c in batch_codes)

                # 自动在备注中补充码段信息
                if transaction_batch_no:
                    code_ranges = []
                    for batch_id in batch_ids:
                        batch = ProductBatch.query.get(batch_id)
                        if batch:
                            code_ranges.append(f'[{batch.batch_no}: {batch.code_start}-{batch.code_end}]')
                    if code_ranges:
                        codes_info = '；'.join(code_ranges)
                        remark = f'{remark}\n批次码段：{codes_info}' if remark else f'批次码段：{codes_info}'

            # 生成出库单号
            transaction_no = StockTransaction.generate_transaction_no('stock_out')

            # 获取客户信息
            customer_name = ''
            if customer_id:
                customer = Customer.query.get(customer_id)
                if customer:
                    customer_name = customer.name

            # 创建出入库记录
            transaction = StockTransaction(
                transaction_no=transaction_no,
                type='stock_out',
                product_id=product_id,
                product_name=product.name if product else '',
                warehouse_id=warehouse_id,
                customer_id=customer_id,
                customer_name=customer_name,
                quantity=quantity,
                unit_cost=tx_unit_cost,
                reference_no=reference_no,
                batch_no=transaction_batch_no,
                batch_codes=transaction_batch_codes,
                remark=remark,
                operator=operator
            )
            db.session.add(transaction)
            db.session.flush()

            # 更新库存
            old_quantity = inventory.quantity
            inventory.quantity -= quantity

            # 记录日志
            warehouse = Warehouse.query.get(warehouse_id)
            InventoryService._log_operation_safe(
                operation_type='stock_out',
                module='inventory',
                description=f'商品出库：{product.name if product else product_id}，数量：{quantity}，单号：{transaction_no}',
                reference_type='stock_out',
                reference_no=transaction_no,
                reference_id=transaction.id,
                before_data={'quantity': old_quantity},
                after_data={
                    'product': product.name if product else None,
                    'product_id': product_id,
                    'warehouse': warehouse.name if warehouse else None,
                    'warehouse_id': warehouse_id,
                    'customer': customer_name,
                    'customer_id': customer_id,
                    'quantity': quantity,
                    'unit_cost': float(tx_unit_cost) if tx_unit_cost else 0,
                    'amount': float(tx_unit_cost * quantity) if tx_unit_cost else 0,
                    'new_total_quantity': inventory.quantity,
                    'transaction_no': transaction_no,
                    'reference_no': reference_no,
                    'batch_no': transaction_batch_no,
                    'batch_codes': batch_codes if batch_codes else []
                }
            )

            db.session.commit()
            return transaction

        except ValueError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f'出库操作失败: {e}', exc_info=True)
            raise ValueError(f'出库操作失败: {str(e)}')

    @staticmethod
    def transfer(product_id: int, from_warehouse_id: int, to_warehouse_id: int,
                 quantity: int, operator='', remark='', batch_codes=None):
        """
        调拨操作（从A仓库调到B仓库）
        """
        try:
            if quantity <= 0:
                raise ValueError('调拨数量必须大于0')

            if from_warehouse_id == to_warehouse_id:
                raise ValueError('调出仓库和调入仓库不能相同')

            # 检查调出仓库库存
            from_inventory = Inventory.query.filter_by(
                product_id=product_id,
                warehouse_id=from_warehouse_id
            ).first()

            if not from_inventory or from_inventory.quantity < quantity:
                raise ValueError(f'调出仓库库存不足，当前库存: {from_inventory.quantity if from_inventory else 0}')

            # 处理批次码
            transaction_batch_no = ''
            transaction_batch_codes = ''
            if batch_codes and len(batch_codes) > 0:
                used_codes = []
                for code in batch_codes:
                    batch_code = BatchCode.query.join(ProductBatch, BatchCode.batch_id == ProductBatch.id).filter(
                        BatchCode.code == code,
                        BatchCode.status == 'in_stock',
                        ProductBatch.product_id == product_id,
                        ProductBatch.warehouse_id == from_warehouse_id
                    ).first()
                    if not batch_code:
                        raise ValueError(f'批次码 {code} 不存在或已被使用，或不属于该商品/调出仓库')
                    used_codes.append(batch_code)

                # 更新批次码状态为已调出
                for bc in used_codes:
                    bc.status = 'transferred'
                    bc.transferred_at = datetime.now()

                # 在调入仓库创建新的批次和批次码
                from_batch_ids = set(bc.batch_id for bc in used_codes)
                for from_batch_id in from_batch_ids:
                    from_batch = ProductBatch.query.get(from_batch_id)
                    if from_batch:
                        transferred_codes = [bc for bc in used_codes if bc.batch_id == from_batch_id]
                        code_list = [bc.code for bc in transferred_codes]

                        import re
                        numeric_parts = []
                        for c in code_list:
                            match = re.search(r'(\d+)$', c)
                            if match:
                                numeric_parts.append(int(match.group(1)))
                            else:
                                numeric_parts.append(0)

                        new_batch = ProductBatch(
                            batch_no=ProductBatch.generate_batch_no(),
                            product_id=product_id,
                            warehouse_id=to_warehouse_id,
                            code_start=min(numeric_parts) if numeric_parts else 0,
                            code_end=max(numeric_parts) if numeric_parts else 0,
                            total_quantity=len(code_list),
                            remaining_quantity=len(code_list),
                            cost_price=from_batch.cost_price,
                            production_date=from_batch.production_date,
                            expire_date=from_batch.expire_date,
                            remark=f'从{from_warehouse_id}仓库调入',
                            operator=operator or 'admin',
                            status='active'
                        )
                        db.session.add(new_batch)
                        db.session.flush()

                        for bc in transferred_codes:
                            new_bc = BatchCode(
                                batch_id=new_batch.id,
                                code=bc.code,
                                status='in_stock'
                            )
                            db.session.add(new_bc)

                # 更新批次剩余数量
                batch_ids = set(bc.batch_id for bc in used_codes)
                batch_no_list = []
                for batch_id in batch_ids:
                    batch = ProductBatch.query.get(batch_id)
                    if batch:
                        batch_no_list.append(batch.batch_no)
                        remaining = BatchCode.query.filter_by(batch_id=batch_id, status='in_stock').count()
                        batch.remaining_quantity = remaining
                        if batch.remaining_quantity == 0:
                            batch.status = 'depleted'

                transaction_batch_no = ','.join(batch_no_list)
                transaction_batch_codes = ','.join(str(c) for c in batch_codes)

            # 获取仓库名称
            from_warehouse = Warehouse.query.get(from_warehouse_id)
            to_warehouse = Warehouse.query.get(to_warehouse_id)
            from_warehouse_name = from_warehouse.name if from_warehouse else str(from_warehouse_id)
            to_warehouse_name = to_warehouse.name if to_warehouse else str(to_warehouse_id)

            # 生成调出单号
            transfer_out_no = StockTransaction.generate_transaction_no('transfer_out')
            transfer_in_no = StockTransaction.generate_transaction_no('transfer_in')

            # 获取商品名称
            product = Product.query.get(product_id)
            product_name = product.name if product else ''

            # 创建调出记录
            out_transaction = StockTransaction(
                transaction_no=transfer_out_no,
                type='transfer_out',
                product_id=product_id,
                product_name=product_name,
                warehouse_id=from_warehouse_id,
                quantity=quantity,
                reference_no=transfer_in_no,
                batch_no=transaction_batch_no,
                batch_codes=transaction_batch_codes,
                remark=remark or f'调拨至{to_warehouse_name}',
                operator=operator
            )
            db.session.add(out_transaction)

            # 创建调入记录
            in_transaction = StockTransaction(
                transaction_no=transfer_in_no,
                type='transfer_in',
                product_id=product_id,
                product_name=product_name,
                warehouse_id=to_warehouse_id,
                quantity=quantity,
                reference_no=transfer_out_no,
                batch_no=transaction_batch_no,
                batch_codes=transaction_batch_codes,
                remark=remark or f'从{from_warehouse_name}调入',
                operator=operator
            )
            db.session.add(in_transaction)

            # 更新库存
            from_inventory.quantity -= quantity
            to_inventory = InventoryService._get_or_create_inventory(product_id, to_warehouse_id)
            to_inventory.quantity += quantity

            # 记录日志
            InventoryService._log_operation_safe(
                operation_type='transfer',
                module='inventory',
                description=f'库存调拨：{product_name} 从{from_warehouse_name}调到{to_warehouse_name}，数量：{quantity}',
                reference_type='transfer',
                reference_no=transfer_out_no,
                after_data={
                    'product_id': product_id,
                    'from_warehouse': from_warehouse_name,
                    'to_warehouse': to_warehouse_name,
                    'quantity': quantity
                }
            )

            db.session.commit()
            return out_transaction, in_transaction

        except ValueError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f'调拨操作失败: {e}', exc_info=True)
            raise ValueError(f'调拨操作失败: {str(e)}')

    @staticmethod
    def adjust(product_id: int, warehouse_id: int, new_quantity: int,
               operator='', remark=''):
        """
        盘点调整
        """
        try:
            if new_quantity < 0:
                raise ValueError('调整后数量不能为负数')

            # 获取当前库存
            inventory = Inventory.query.filter_by(
                product_id=product_id,
                warehouse_id=warehouse_id
            ).first()

            current_quantity = inventory.quantity if inventory else 0
            diff = new_quantity - current_quantity

            if diff == 0:
                raise ValueError('调整后数量与当前库存相同，无需调整')

            # 生成调整单号
            transaction_no = StockTransaction.generate_transaction_no('adjustment')

            # 创建调整记录
            transaction = StockTransaction(
                transaction_no=transaction_no,
                type='adjustment',
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=abs(diff),
                remark=remark or f'盘点调整: {current_quantity} -> {new_quantity}',
                operator=operator
            )
            db.session.add(transaction)

            # 更新库存
            if not inventory:
                inventory = InventoryService._get_or_create_inventory(product_id, warehouse_id)
            inventory.quantity = new_quantity

            # 记录日志
            product = Product.query.get(product_id)
            warehouse = Warehouse.query.get(warehouse_id)
            InventoryService._log_operation_safe(
                operation_type='adjust',
                module='inventory',
                description=f'盘点调整：{product.name if product else product_id}，{warehouse.name if warehouse else warehouse_id}，{current_quantity} -> {new_quantity}',
                reference_type='adjustment',
                reference_no=transaction_no,
                before_data={'quantity': current_quantity},
                after_data={'quantity': new_quantity}
            )

            db.session.commit()
            return transaction

        except ValueError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f'盘点调整失败: {e}', exc_info=True)
            raise ValueError(f'盘点调整失败: {str(e)}')

    @staticmethod
    def get_low_stock_products():
        """获取低库存预警商品列表"""
        products = Product.query.filter(Product.min_stock > 0).all()
        low_stock_list = []

        for product in products:
            total_qty = db.session.query(db.func.sum(Inventory.quantity)).filter(
                Inventory.product_id == product.id
            ).scalar() or 0

            if total_qty <= product.min_stock:
                low_stock_list.append({
                    'product': product,
                    'total_quantity': total_qty,
                    'min_stock': product.min_stock
                })

        return low_stock_list

    @staticmethod
    def verify_inventory_consistency():
        """
        校验库存数据一致性
        :return: dict with 'success' bool, 'errors' list, 'fixed' list
        """
        errors = []
        fixed = []

        try:
            # 获取所有库存记录
            inventories = Inventory.query.all()

            for inv in inventories:
                # 计算该商品在该仓库的批次总量
                batch_total = db.session.query(db.func.sum(ProductBatch.remaining_quantity)).filter(
                    ProductBatch.product_id == inv.product_id,
                    ProductBatch.warehouse_id == inv.warehouse_id
                ).scalar() or 0

                # 计算该商品在该仓库的批次码总量
                code_total = db.session.query(db.func.count(BatchCode.id)).join(
                    ProductBatch, BatchCode.batch_id == ProductBatch.id
                ).filter(
                    ProductBatch.product_id == inv.product_id,
                    ProductBatch.warehouse_id == inv.warehouse_id,
                    BatchCode.status == 'in_stock'
                ).scalar() or 0

                # 检查是否有批次码但库存不匹配
                if batch_total > 0 and inv.quantity != batch_total:
                    product = Product.query.get(inv.product_id)
                    warehouse = Warehouse.query.get(inv.warehouse_id)
                    error_msg = f'商品[{product.name if product else inv.product_id}]在仓库[{warehouse.name if warehouse else inv.warehouse_id}]：库存表={inv.quantity}，批次汇总={batch_total}，码数={code_total}'
                    errors.append(error_msg)

                    # 自动修复：用批次汇总更新库存表
                    inv.quantity = batch_total
                    fixed.append(f'已修复：{error_msg}')

                # 检查库存有数量但无批次记录的异常情况
                if inv.quantity > 0 and batch_total == 0:
                    product = Product.query.get(inv.product_id)
                    warehouse = Warehouse.query.get(inv.warehouse_id)
                    # 检查是否有批次码记录
                    if code_total == 0:
                        error_msg = f'商品[{product.name if product else inv.product_id}]在仓库[{warehouse.name if warehouse else inv.warehouse_id}]：库存表={inv.quantity}，但无批次记录'
                        errors.append(error_msg)
                        # 不自动修复这种情况，因为可能是无批次码的入库

            # 获取有批次但无库存记录的情况
            batches = db.session.query(
                ProductBatch.product_id,
                ProductBatch.warehouse_id,
                db.func.sum(ProductBatch.remaining_quantity).label('total')
            ).group_by(
                ProductBatch.product_id,
                ProductBatch.warehouse_id
            ).all()

            for batch in batches:
                inv = Inventory.query.filter_by(
                    product_id=batch.product_id,
                    warehouse_id=batch.warehouse_id
                ).first()

                if not inv and batch.total > 0:
                    product = Product.query.get(batch.product_id)
                    warehouse = Warehouse.query.get(batch.warehouse_id)
                    error_msg = f'商品[{product.name if product else batch.product_id}]在仓库[{warehouse.name if warehouse else batch.warehouse_id}]有批次={batch.total}但无库存记录'
                    errors.append(error_msg)

                    # 自动创建库存记录
                    inv = Inventory(
                        product_id=batch.product_id,
                        warehouse_id=batch.warehouse_id,
                        quantity=batch.total
                    )
                    db.session.add(inv)
                    fixed.append(f'已修复：{error_msg}')

            if fixed:
                db.session.commit()

            return {
                'success': True,
                'errors': errors,
                'fixed': fixed,
                'total_checks': len(inventories) + len(batches)
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f'库存一致性校验失败: {e}', exc_info=True)
            return {
                'success': False,
                'errors': [f'校验失败: {str(e)}'],
                'fixed': []
            }

    @staticmethod
    def confirm_purchase_order_received(po_id: int, items: list):
        """
        采购入库确认
        """
        try:
            purchase_order = PurchaseOrder.query.get(po_id)
            if not purchase_order:
                raise ValueError('采购单不存在')

            if purchase_order.status == 'cancelled':
                raise ValueError('已取消的采购单不能入库')

            all_received = True

            for item_data in items:
                item_id = item_data.get('item_id')
                received_qty = item_data.get('received_quantity', 0)
                batch_codes = item_data.get('batch_codes')
                production_date = item_data.get('production_date')
                expire_date = item_data.get('expire_date')

                if received_qty <= 0:
                    continue

                po_item = PurchaseOrderItem.query.get(item_id)
                if not po_item or po_item.purchase_order_id != po_id:
                    raise ValueError(f'采购单明细不存在: {item_id}')

                remaining = po_item.quantity - po_item.received_quantity
                if received_qty > remaining:
                    raise ValueError(
                        f'商品"{po_item.product.name}"入库数量{received_qty}超过剩余待入库数量{remaining}'
                    )

                InventoryService.stock_in(
                    product_id=po_item.product_id,
                    warehouse_id=purchase_order.warehouse_id,
                    quantity=received_qty,
                    unit_cost=float(po_item.unit_cost),
                    reference_no=purchase_order.po_no,
                    operator='系统',
                    remark=f'采购单{purchase_order.po_no}入库',
                    batch_codes=batch_codes,
                    production_date=production_date,
                    expire_date=expire_date
                )

                po_item.received_quantity += received_qty

                if po_item.received_quantity < po_item.quantity:
                    all_received = False

            if all_received:
                purchase_order.status = 'received'
            else:
                purchase_order.status = 'partial'

            purchase_order.updated_at = datetime.now()
            db.session.commit()

        except ValueError:
            db.session.rollback()
            raise
        except Exception as e:
            db.session.rollback()
            logger.error(f'采购入库确认失败: {e}', exc_info=True)
            raise ValueError(f'采购入库确认失败: {str(e)}')
