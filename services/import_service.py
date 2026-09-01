"""
数据导入服务模块
提供Excel数据导入功能
"""

import openpyxl
from io import BytesIO
from decimal import Decimal, InvalidOperation
from models import db
from models.product import Product
from models.warehouse import Warehouse
from models.supplier import Supplier
from models.inventory import Inventory
from models.purchase_order import PurchaseOrder, PurchaseOrderItem
from models.stock_transaction import StockTransaction


class ImportService:
    """数据导入服务"""

    # 模板定义
    TEMPLATES = {
        'products': {
            'name': '商品导入模板',
            'headers': ['商品编码*', '商品名称*', '条形码', '分类', '规格', '单位*', '成本价', '售价', '最低库存', '状态', '备注']
        },
        'warehouses': {
            'name': '仓库导入模板',
            'headers': ['仓库名称*', '仓库编码*', '地址', '联系人', '联系电话']
        },
        'suppliers': {
            'name': '供应商导入模板',
            'headers': ['供应商名称*', '联系人', '联系电话', '邮箱', '地址', '备注']
        },
        'inventory': {
            'name': '库存导入模板',
            'headers': ['商品编码*', '仓库编码*', '库存数量*']
        },
        'purchase_orders': {
            'name': '采购单导入模板',
            'headers': ['采购单号*', '供应商名称*', '仓库编码*', '商品编码*', '数量*', '单价', '状态', '备注']
        },
        'transactions': {
            'name': '出入库记录导入模板',
            'headers': ['单号*', '类型*', '商品编码*', '仓库编码*', '数量*', '单位成本', '操作人', '备注']
        }
    }

    @staticmethod
    def _prepare_file_stream(file_stream):
        """
        准备文件流，确保可以正确读取

        Args:
            file_stream: 文件流

        Returns:
            BytesIO对象
        """
        # 重置文件流指针到开头（如果需要）
        if hasattr(file_stream, 'seek'):
            file_stream.seek(0)

        # 读取文件内容到 BytesIO，避免流被关闭的问题
        if hasattr(file_stream, 'read'):
            file_content = file_stream.read()
            return BytesIO(file_content)

        return file_stream

    @staticmethod
    def get_template(template_type):
        """
        获取导入模板

        Args:
            template_type: 模板类型 (products/warehouses/suppliers/inventory/purchase_orders/transactions)

        Returns:
            BytesIO对象，包含Excel模板
        """
        if template_type not in ImportService.TEMPLATES:
            raise ValueError(f'不支持的模板类型: {template_type}')

        template_info = ImportService.TEMPLATES[template_type]

        # 创建工作簿
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = template_info['name']

        # 写入表头
        for col, header in enumerate(template_info['headers'], 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = openpyxl.styles.Font(bold=True)
            cell.fill = openpyxl.styles.PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
            cell.alignment = openpyxl.styles.Alignment(horizontal='center')

        # 调整列宽
        for col in range(1, len(template_info['headers']) + 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 15

        # 保存到BytesIO
        output = BytesIO()
        wb.save(output)
        output.seek(0)

        return output

    @staticmethod
    def parse_decimal(value, default=0):
        """解析Decimal值"""
        if value is None or value == '':
            return Decimal(str(default))
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal(str(default))

    @staticmethod
    def parse_int(value, default=0):
        """解析整数值"""
        if value is None or value == '':
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def import_products(file_stream, operator):
        """
        导入商品数据

        Args:
            file_stream: 文件流
            operator: 操作人用户名

        Returns:
            (success_count, error_count, errors)
        """
        file_stream = ImportService._prepare_file_stream(file_stream)
        wb = openpyxl.load_workbook(file_stream)
        ws = wb.active

        success_count = 0
        error_count = 0
        errors = []

        # 从第2行开始读取数据（第1行是表头）
        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            try:
                # 解析数据
                sku = str(row[0] or '').strip()
                name = str(row[1] or '').strip()
                barcode = str(row[2] or '').strip() or None
                category = str(row[3] or '').strip()
                specification = str(row[4] or '').strip()
                unit = str(row[5] or '个').strip()
                cost_price = ImportService.parse_decimal(row[6], 0)
                selling_price = ImportService.parse_decimal(row[7], 0)
                min_stock = ImportService.parse_int(row[8], 0)
                status_str = str(row[9] or '').strip()
                description = str(row[10] or '').strip()

                # 验证必填字段
                if not sku:
                    errors.append(f'第{row_num}行: 商品编码不能为空')
                    error_count += 1
                    continue
                if not name:
                    errors.append(f'第{row_num}行: 商品名称不能为空')
                    error_count += 1
                    continue

                # 解析状态
                is_active = True
                if status_str in ['停用', '禁用', '否', '0', 'False', 'false']:
                    is_active = False

                # 检查商品编码是否已存在
                existing = Product.query.filter_by(sku=sku).first()
                if existing:
                    # 更新现有商品
                    existing.name = name
                    existing.barcode = barcode
                    existing.category = category
                    existing.specification = specification
                    existing.unit = unit
                    existing.cost_price = cost_price
                    existing.selling_price = selling_price
                    existing.min_stock = min_stock
                    existing.is_active = is_active
                    existing.description = description
                else:
                    # 创建新商品
                    product = Product(
                        sku=sku,
                        name=name,
                        barcode=barcode,
                        category=category,
                        specification=specification,
                        unit=unit,
                        cost_price=cost_price,
                        selling_price=selling_price,
                        min_stock=min_stock,
                        is_active=is_active,
                        description=description
                    )
                    db.session.add(product)

                success_count += 1

            except Exception as e:
                errors.append(f'第{row_num}行: {str(e)}')
                error_count += 1

        db.session.commit()
        return success_count, error_count, errors

    @staticmethod
    def import_warehouses(file_stream, operator):
        """
        导入仓库数据

        Args:
            file_stream: 文件流
            operator: 操作人用户名

        Returns:
            (success_count, error_count, errors)
        """
        file_stream = ImportService._prepare_file_stream(file_stream)
        wb = openpyxl.load_workbook(file_stream)
        ws = wb.active

        success_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            try:
                name = str(row[0] or '').strip()
                code = str(row[1] or '').strip()
                address = str(row[2] or '').strip()
                contact_person = str(row[3] or '').strip()
                contact_phone = str(row[4] or '').strip()

                if not name:
                    errors.append(f'第{row_num}行: 仓库名称不能为空')
                    error_count += 1
                    continue
                if not code:
                    errors.append(f'第{row_num}行: 仓库编码不能为空')
                    error_count += 1
                    continue

                existing = Warehouse.query.filter_by(code=code).first()
                if existing:
                    existing.name = name
                    existing.address = address
                    existing.contact_person = contact_person
                    existing.contact_phone = contact_phone
                else:
                    warehouse = Warehouse(
                        name=name,
                        code=code,
                        address=address,
                        contact_person=contact_person,
                        contact_phone=contact_phone
                    )
                    db.session.add(warehouse)

                success_count += 1

            except Exception as e:
                errors.append(f'第{row_num}行: {str(e)}')
                error_count += 1

        db.session.commit()
        return success_count, error_count, errors

    @staticmethod
    def import_suppliers(file_stream, operator):
        """
        导入供应商数据

        Args:
            file_stream: 文件流
            operator: 操作人用户名

        Returns:
            (success_count, error_count, errors)
        """
        file_stream = ImportService._prepare_file_stream(file_stream)
        wb = openpyxl.load_workbook(file_stream)
        ws = wb.active

        success_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            try:
                name = str(row[0] or '').strip()
                contact_person = str(row[1] or '').strip()
                contact_phone = str(row[2] or '').strip()
                email = str(row[3] or '').strip()
                address = str(row[4] or '').strip()
                description = str(row[5] or '').strip()

                if not name:
                    errors.append(f'第{row_num}行: 供应商名称不能为空')
                    error_count += 1
                    continue

                # 检查供应商名称是否已存在
                existing = Supplier.query.filter_by(name=name).first()
                if existing:
                    existing.contact_person = contact_person
                    existing.contact_phone = contact_phone
                    existing.email = email
                    existing.address = address
                    existing.description = description
                else:
                    supplier = Supplier(
                        name=name,
                        contact_person=contact_person,
                        contact_phone=contact_phone,
                        email=email,
                        address=address,
                        description=description
                    )
                    db.session.add(supplier)

                success_count += 1

            except Exception as e:
                errors.append(f'第{row_num}行: {str(e)}')
                error_count += 1

        db.session.commit()
        return success_count, error_count, errors

    @staticmethod
    def import_inventory(file_stream, operator):
        """
        导入库存数据

        Args:
            file_stream: 文件流
            operator: 操作人用户名

        Returns:
            (success_count, error_count, errors)
        """
        file_stream = ImportService._prepare_file_stream(file_stream)
        wb = openpyxl.load_workbook(file_stream)
        ws = wb.active

        success_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            try:
                product_sku = str(row[0] or '').strip()
                warehouse_code = str(row[1] or '').strip()
                quantity = ImportService.parse_int(row[2], 0)

                if not product_sku:
                    errors.append(f'第{row_num}行: 商品编码不能为空')
                    error_count += 1
                    continue
                if not warehouse_code:
                    errors.append(f'第{row_num}行: 仓库编码不能为空')
                    error_count += 1
                    continue

                # 查找商品和仓库
                product = Product.query.filter_by(sku=product_sku).first()
                if not product:
                    errors.append(f'第{row_num}行: 商品编码 {product_sku} 不存在')
                    error_count += 1
                    continue

                warehouse = Warehouse.query.filter_by(code=warehouse_code).first()
                if not warehouse:
                    errors.append(f'第{row_num}行: 仓库编码 {warehouse_code} 不存在')
                    error_count += 1
                    continue

                # 查找或创建库存记录
                inventory = Inventory.query.filter_by(
                    product_id=product.id,
                    warehouse_id=warehouse.id
                ).first()

                if inventory:
                    inventory.quantity = quantity
                else:
                    inventory = Inventory(
                        product_id=product.id,
                        warehouse_id=warehouse.id,
                        quantity=quantity
                    )
                    db.session.add(inventory)

                success_count += 1

            except Exception as e:
                errors.append(f'第{row_num}行: {str(e)}')
                error_count += 1

        db.session.commit()
        return success_count, error_count, errors

    @staticmethod
    def import_purchase_orders(file_stream, operator):
        """
        导入采购单数据

        Args:
            file_stream: 文件流
            operator: 操作人用户名

        Returns:
            (success_count, error_count, errors)
        """
        file_stream = ImportService._prepare_file_stream(file_stream)
        wb = openpyxl.load_workbook(file_stream)
        ws = wb.active

        success_count = 0
        error_count = 0
        errors = []

        # 用于缓存采购单对象
        po_cache = {}

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            try:
                po_no = str(row[0] or '').strip()
                supplier_name = str(row[1] or '').strip()
                warehouse_code = str(row[2] or '').strip()
                product_sku = str(row[3] or '').strip()
                quantity = ImportService.parse_int(row[4], 0)
                unit_cost = ImportService.parse_decimal(row[5], 0)
                status = str(row[6] or 'draft').strip()
                remark = str(row[7] or '').strip()

                # 验证必填字段
                if not po_no:
                    errors.append(f'第{row_num}行: 采购单号不能为空')
                    error_count += 1
                    continue
                if not supplier_name:
                    errors.append(f'第{row_num}行: 供应商名称不能为空')
                    error_count += 1
                    continue
                if not warehouse_code:
                    errors.append(f'第{row_num}行: 仓库编码不能为空')
                    error_count += 1
                    continue
                if not product_sku:
                    errors.append(f'第{row_num}行: 商品编码不能为空')
                    error_count += 1
                    continue

                # 查找供应商
                supplier = Supplier.query.filter_by(name=supplier_name).first()
                if not supplier:
                    errors.append(f'第{row_num}行: 供应商 {supplier_name} 不存在')
                    error_count += 1
                    continue

                # 查找仓库
                warehouse = Warehouse.query.filter_by(code=warehouse_code).first()
                if not warehouse:
                    errors.append(f'第{row_num}行: 仓库 {warehouse_code} 不存在')
                    error_count += 1
                    continue

                # 查找商品
                product = Product.query.filter_by(sku=product_sku).first()
                if not product:
                    errors.append(f'第{row_num}行: 商品 {product_sku} 不存在')
                    error_count += 1
                    continue

                # 查找或创建采购单
                if po_no in po_cache:
                    po = po_cache[po_no]
                else:
                    po = PurchaseOrder.query.filter_by(po_no=po_no).first()
                    if not po:
                        po = PurchaseOrder(
                            po_no=po_no,
                            supplier_id=supplier.id,
                            warehouse_id=warehouse.id,
                            status=status,
                            remark=remark
                        )
                        db.session.add(po)
                        db.session.flush()  # 获取ID
                    po_cache[po_no] = po

                # 创建采购单明细
                item = PurchaseOrderItem(
                    purchase_order_id=po.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_cost=unit_cost
                )
                db.session.add(item)

                success_count += 1

            except Exception as e:
                errors.append(f'第{row_num}行: {str(e)}')
                error_count += 1

        db.session.commit()
        return success_count, error_count, errors

    @staticmethod
    def import_transactions(file_stream, operator):
        """
        导入出入库记录

        Args:
            file_stream: 文件流
            operator: 操作人用户名

        Returns:
            (success_count, error_count, errors)
        """
        file_stream = ImportService._prepare_file_stream(file_stream)
        wb = openpyxl.load_workbook(file_stream)
        ws = wb.active

        success_count = 0
        error_count = 0
        errors = []

        # 类型映射
        type_map = {
            '入库': 'stock_in',
            '出库': 'stock_out',
            '调拨入': 'transfer_in',
            '调拨出': 'transfer_out',
            '盘点': 'adjustment',
            'stock_in': 'stock_in',
            'stock_out': 'stock_out',
            'transfer_in': 'transfer_in',
            'transfer_out': 'transfer_out',
            'adjustment': 'adjustment'
        }

        for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            try:
                transaction_no = str(row[0] or '').strip()
                tx_type_str = str(row[1] or '').strip()
                product_sku = str(row[2] or '').strip()
                warehouse_code = str(row[3] or '').strip()
                quantity = ImportService.parse_int(row[4], 0)
                unit_cost = ImportService.parse_decimal(row[5], 0)
                tx_operator = str(row[6] or operator).strip()
                remark = str(row[7] or '').strip()

                # 验证必填字段
                if not transaction_no:
                    errors.append(f'第{row_num}行: 单号不能为空')
                    error_count += 1
                    continue
                if not tx_type_str:
                    errors.append(f'第{row_num}行: 类型不能为空')
                    error_count += 1
                    continue
                if not product_sku:
                    errors.append(f'第{row_num}行: 商品编码不能为空')
                    error_count += 1
                    continue
                if not warehouse_code:
                    errors.append(f'第{row_num}行: 仓库编码不能为空')
                    error_count += 1
                    continue

                # 解析类型
                tx_type = type_map.get(tx_type_str)
                if not tx_type:
                    errors.append(f'第{row_num}行: 无效的类型 {tx_type_str}')
                    error_count += 1
                    continue

                # 查找商品
                product = Product.query.filter_by(sku=product_sku).first()
                if not product:
                    errors.append(f'第{row_num}行: 商品 {product_sku} 不存在')
                    error_count += 1
                    continue

                # 查找仓库
                warehouse = Warehouse.query.filter_by(code=warehouse_code).first()
                if not warehouse:
                    errors.append(f'第{row_num}行: 仓库 {warehouse_code} 不存在')
                    error_count += 1
                    continue

                # 检查单号是否已存在
                existing = StockTransaction.query.filter_by(transaction_no=transaction_no).first()
                if existing:
                    errors.append(f'第{row_num}行: 单号 {transaction_no} 已存在')
                    error_count += 1
                    continue

                # 创建出入库记录
                transaction = StockTransaction(
                    transaction_no=transaction_no,
                    type=tx_type,
                    product_id=product.id,
                    warehouse_id=warehouse.id,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    operator=tx_operator,
                    remark=remark
                )
                db.session.add(transaction)

                # 更新库存
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
                    db.session.flush()

                if tx_type in ['stock_in', 'transfer_in']:
                    inventory.quantity += quantity
                elif tx_type in ['stock_out', 'transfer_out']:
                    inventory.quantity -= quantity
                elif tx_type == 'adjustment':
                    inventory.quantity = quantity

                success_count += 1

            except Exception as e:
                errors.append(f'第{row_num}行: {str(e)}')
                error_count += 1

        db.session.commit()
        return success_count, error_count, errors

    @staticmethod
    def preview_data(file_stream, template_type):
        """
        预览导入数据

        Args:
            file_stream: 文件流
            template_type: 模板类型

        Returns:
            (headers, data, error)
        """
        try:
            file_stream = ImportService._prepare_file_stream(file_stream)
            wb = openpyxl.load_workbook(file_stream)
            ws = wb.active

            # 获取表头
            headers = []
            header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), [])
            for cell in header_row:
                headers.append(str(cell) if cell else '')

            # 获取数据（最多10行）
            data = []
            for row in ws.iter_rows(min_row=2, max_row=11, values_only=True):
                row_data = [str(cell) if cell is not None else '' for cell in row]
                if any(row_data):  # 跳过空行
                    data.append(row_data)

            return headers, data, None

        except Exception as e:
            return [], [], str(e)
