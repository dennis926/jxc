from flask import Blueprint, render_template, request, Response, session, jsonify
from models.stock_transaction import StockTransaction
from models.product import Product
from models.warehouse import Warehouse
from models.product_batch import ProductBatch
from models.customer import Customer
from models.inventory import Inventory
from models.batch_code import BatchCode
from models import db
from utils.decorators import login_required
from utils.excel_export import export_to_excel, ExcelExport
from services.log_service import LogService
from datetime import datetime
from sqlalchemy.orm import joinedload

stock_transactions_bp = Blueprint('stock_transactions', __name__, url_prefix='/stock-transactions')


@stock_transactions_bp.route('/')
@login_required
def list():
    """出入库记录列表"""
    page = request.args.get('page', 1, type=int)
    tx_type = request.args.get('type', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip()
    product_name = request.args.get('product_name', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')
    ALLOWED_SORT_FIELDS = {'transaction_no', 'type', 'product_name', 'warehouse_name', 'quantity', 'created_at'}
    if sort not in ALLOWED_SORT_FIELDS:
        sort = 'created_at'

    query = StockTransaction.query

    # 按类型筛选
    if tx_type:
        query = query.filter(StockTransaction.type == tx_type)

    # 按日期范围筛选
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(StockTransaction.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59)
            query = query.filter(StockTransaction.created_at <= end_dt)
        except ValueError:
            pass

    # 按商品名称或客户名称筛选
    if product_name:
        query = query.outerjoin(Product).outerjoin(
            Customer, StockTransaction.customer_id == Customer.id
        ).filter(
            db.or_(
                Product.name.like(f'%{product_name}%'),
                StockTransaction.customer_name.like(f'%{product_name}%'),
                Customer.name.like(f'%{product_name}%')
            )
        )

    # 按仓库筛选
    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)

    # 按单号或商品搜索
    if search:
        query = query.filter(
            db.or_(
                StockTransaction.transaction_no.like(f'%{search}%'),
                StockTransaction.reference_no.like(f'%{search}%'),
                StockTransaction.product.has(Product.name.like(f'%{search}%')),
                StockTransaction.product.has(Product.sku.like(f'%{search}%'))
            )
        )

    # 排序
    sort_field = getattr(StockTransaction, sort, StockTransaction.created_at)
    if order == 'desc':
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())

    pagination = query.paginate(page=page, per_page=15, error_out=False)

    # 获取批次信息并计算有效期
    today = datetime.now().date()
    for tx in pagination.items:
        tx.batch_info = None
        if tx.batch_no:
            # 取第一个批次号查询（支持多批次情况）
            first_batch_no = tx.batch_no.split(',')[0].strip()
            batch = ProductBatch.query.filter_by(batch_no=first_batch_no).first()
            if batch:
                tx.batch_info = {
                    'production_date': batch.production_date.strftime('%Y-%m-%d') if batch.production_date else None,
                    'expire_date': batch.expire_date.strftime('%Y-%m-%d') if batch.expire_date else None,
                    'days_remaining': 0
                }
                # 计算剩余天数（确保类型一致）
                if batch.expire_date:
                    expire_date = batch.expire_date.date() if hasattr(batch.expire_date, 'date') else batch.expire_date
                    delta = expire_date - today
                    tx.batch_info['days_remaining'] = int(delta.days) if delta.days is not None else 0
        elif tx.product_id and tx.warehouse_id:
            # 尝试从批次表查询该商品在该仓库的有效批次
            batch = ProductBatch.query.filter_by(
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id
            ).filter(ProductBatch.status.in_(['active', 'partial'])).first()
            if batch:
                tx.batch_info = {
                    'production_date': batch.production_date.strftime('%Y-%m-%d') if batch.production_date else None,
                    'expire_date': batch.expire_date.strftime('%Y-%m-%d') if batch.expire_date else None,
                    'days_remaining': 0
                }
                # 计算剩余天数（确保类型一致）
                if batch.expire_date:
                    expire_date = batch.expire_date.date() if hasattr(batch.expire_date, 'date') else batch.expire_date
                    delta = expire_date - today
                    tx.batch_info['days_remaining'] = int(delta.days) if delta.days is not None else 0

    # 类型选项
    type_options = [
        ('stock_in', '入库'),
        ('stock_out', '出库'),
        ('transfer_in', '调入'),
        ('transfer_out', '调出'),
        ('adjustment', '盘点调整'),
    ]

    # 获取所有仓库
    warehouses = Warehouse.query.filter_by(is_active=True).all()

    return render_template('stock_transactions/list.html',
                           transactions=pagination.items,
                           pagination=pagination,
                           tx_type=tx_type,
                           start_date=start_date,
                           end_date=end_date,
                           search=search,
                           product_name=product_name,
                           warehouse_id=warehouse_id,
                           warehouses=warehouses,
                           type_options=type_options,
                           sort=sort,
                           order=order)


@stock_transactions_bp.route('/export')
@login_required
def export():
    """导出出入库记录到Excel"""
    from datetime import datetime as dt

    tx_type = request.args.get('type', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip()
    product_name = request.args.get('product_name', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)

    query = _build_query(tx_type, start_date, end_date, search, product_name, warehouse_id)
    transactions = query.order_by(StockTransaction.created_at.desc()).all()

    # 类型映射
    type_map = {
        'stock_in': '入库',
        'stock_out': '出库',
        'transfer_in': '调入',
        'transfer_out': '调出',
        'adjustment': '盘点调整'
    }

    data = []
    for idx, tx in enumerate(transactions, 1):
        data.append({
            'idx': idx,
            'transaction_no': tx.transaction_no,
            'type': type_map.get(tx.type, tx.type),
            'product_name': tx.product.name if tx.product else '',
            'product_sku': tx.product.sku if tx.product else '',
            'warehouse_name': tx.warehouse.name if tx.warehouse else '',
            'customer_name': tx.customer_name or (tx.customer.name if tx.customer else ''),
            'quantity': tx.quantity,
            'reference_no': tx.reference_no or '',
            'operator': tx.operator or '',
            'remark': tx.remark or '',
            'created_at': tx.created_at.strftime('%Y-%m-%d %H:%M') if tx.created_at else '',
            'export_time': dt.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    headers = [
        ('idx', '序号'),
        ('transaction_no', '单号'),
        ('type', '类型'),
        ('product_name', '商品名称'),
        ('product_sku', '商品编码'),
        ('warehouse_name', '仓库'),
        ('customer_name', '收货方'),
        ('quantity', '数量'),
        ('reference_no', '关联单号'),
        ('operator', '操作人'),
        ('remark', '备注'),
        ('created_at', '时间'),
        ('export_time', '导出时间')
    ]

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='transaction',
        description='导出出入库记录'
    )

    return export_to_excel(data, headers, '出入库记录.xlsx')


@stock_transactions_bp.route('/export/stock-in')
@login_required
def export_stock_in():
    """导出入库记录到Excel - 使用表单配置"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    product_name = request.args.get('product_name', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    ids_str = request.args.get('ids', '').strip()

    # 获取表单配置
    form_config, form_fields = _get_form_config('stock_in_form')

    # 使用 joinedload 一次性加载关联数据
    if ids_str:
        ids = [int(i) for i in ids_str.split(',') if i.strip()]
        transactions = StockTransaction.query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse)
        ).filter(
            StockTransaction.id.in_(ids),
            StockTransaction.type == 'stock_in'
        ).order_by(StockTransaction.created_at.desc()).all()
    else:
        query = _build_query('stock_in', start_date, end_date, '', product_name, warehouse_id)
        transactions = query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse)
        ).order_by(StockTransaction.created_at.desc()).all()

    # 预加载批次信息
    batch_dict = _get_batch_dict(transactions)

    # 生成数据行
    data = []
    for idx, tx in enumerate(transactions, 1):
        product = tx.product
        batch_info = batch_dict.get(tx.batch_no.split(',')[0].strip() if tx.batch_no else '')

        row_data = {'idx': idx}
        for field in form_fields:
            row_data[field.field_code] = _get_field_value(tx, field.field_code, batch_info, product)
        data.append(row_data)

    # 生成表头
    headers = [('idx', '序号')]
    for field in form_fields:
        headers.append((field.field_code, field.field_name))

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='transaction',
        description='导出入库记录'
    )

    return export_to_excel(data, headers, '入库记录.xlsx')


@stock_transactions_bp.route('/export/stock-out')
@login_required
def export_stock_out():
    """导出出库记录到Excel - 使用表单配置"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    product_name = request.args.get('product_name', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    ids_str = request.args.get('ids', '').strip()

    # 获取表单配置
    form_config, form_fields = _get_form_config('stock_out_form')

    # 使用 joinedload 一次性加载关联数据
    if ids_str:
        ids = [int(i) for i in ids_str.split(',') if i.strip()]
        transactions = StockTransaction.query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.customer)
        ).filter(
            StockTransaction.id.in_(ids),
            StockTransaction.type == 'stock_out'
        ).order_by(StockTransaction.created_at.desc()).all()
    else:
        query = _build_query('stock_out', start_date, end_date, '', product_name, warehouse_id)
        transactions = query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.customer)
        ).order_by(StockTransaction.created_at.desc()).all()

    # 预加载批次信息
    batch_dict = _get_batch_dict(transactions)

    # 生成数据行
    data = []
    for idx, tx in enumerate(transactions, 1):
        product = tx.product
        customer = tx.customer
        batch_info = batch_dict.get(tx.batch_no.split(',')[0].strip() if tx.batch_no else '')

        row_data = {'idx': idx}
        for field in form_fields:
            row_data[field.field_code] = _get_field_value(tx, field.field_code, batch_info, product, customer)
        data.append(row_data)

    # 生成表头
    headers = [('idx', '序号')]
    for field in form_fields:
        headers.append((field.field_code, field.field_name))

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='transaction',
        description='导出出库记录'
    )

    return export_to_excel(data, headers, '出库记录.xlsx')


@stock_transactions_bp.route('/export/delivery-note')
@login_required
def export_delivery_note():
    """导出随货同行单 - 使用表单配置"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    product_name = request.args.get('product_name', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    ids_str = request.args.get('ids', '').strip()

    # 获取表单配置
    form_config, form_fields = _get_form_config('delivery_note_form')

    # 使用 joinedload 一次性加载所有关联数据
    if ids_str:
        ids = [int(i) for i in ids_str.split(',') if i.strip()]
        transactions = StockTransaction.query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.customer)
        ).filter(
            StockTransaction.id.in_(ids),
            StockTransaction.type == 'stock_out'
        ).order_by(StockTransaction.created_at.desc()).all()
    else:
        query = _build_query('stock_out', start_date, end_date, '', product_name, warehouse_id)
        transactions = query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.customer)
        ).order_by(StockTransaction.created_at.desc()).all()

    # 预加载批次信息
    batch_dict = _get_batch_dict(transactions)

    # 生成数据行
    data = []
    for tx in transactions:
        product = tx.product
        customer = tx.customer
        batch_info = batch_dict.get(tx.batch_no.split(',')[0].strip() if tx.batch_no else '')

        row_data = {}
        for field in form_fields:
            row_data[field.field_code] = _get_field_value(tx, field.field_code, batch_info, product, customer)
        data.append(row_data)

    # 生成表头
    headers = []
    for field in form_fields:
        headers.append((field.field_code, field.field_name))

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='transaction',
        description='导出随货同行单'
    )

    return export_to_excel(data, headers, '随货同行单.xlsx')


@stock_transactions_bp.route('/print/stock-in')
@login_required
def print_stock_in():
    """打印入库记录 - 使用表单配置"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    product_name = request.args.get('product_name', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    ids_str = request.args.get('ids', '').strip()

    # 获取表单配置
    form_config, form_fields = _get_form_config('stock_in_form')

    # 使用 joinedload 一次性加载关联数据
    if ids_str:
        ids = [int(i) for i in ids_str.split(',') if i.strip()]
        transactions = StockTransaction.query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse)
        ).filter(
            StockTransaction.id.in_(ids),
            StockTransaction.type == 'stock_in'
        ).order_by(StockTransaction.created_at.desc()).all()
    else:
        query = _build_query('stock_in', start_date, end_date, '', product_name, warehouse_id)
        transactions = query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse)
        ).order_by(StockTransaction.created_at.desc()).all()

    # 预加载批次信息
    batch_dict = _get_batch_dict(transactions)

    total_qty = 0
    items = []
    for idx, tx in enumerate(transactions, 1):
        product = tx.product
        batch_info = batch_dict.get(tx.batch_no.split(',')[0].strip() if tx.batch_no else '')

        item = {'seq': idx}
        for field in form_fields:
            item[field.field_code] = _get_field_value(tx, field.field_code, batch_info, product)
        items.append(item)
        total_qty += tx.quantity

    today = datetime.now()
    
    # 获取仓库名称
    warehouse_name = ''
    if transactions:
        warehouse_name = transactions[0].warehouse.name if transactions[0].warehouse else ''

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='print',
        module='transaction',
        description='打印入库记录'
    )

    return render_template('stock_transactions/print_stock_in.html',
                           items=items,
                           form_fields=form_fields,
                           form_config=form_config,
                           warehouse_name=warehouse_name,
                           total_qty=total_qty,
                           today=today.strftime('%Y-%m-%d %H:%M'),
                           start_date=start_date,
                           end_date=end_date)


@stock_transactions_bp.route('/print/stock-out')
@login_required
def print_stock_out():
    """打印出库记录 - 使用表单配置"""
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    product_name = request.args.get('product_name', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    ids_str = request.args.get('ids', '').strip()

    # 获取表单配置
    form_config, form_fields = _get_form_config('stock_out_form')

    # 使用 joinedload 一次性加载关联数据
    if ids_str:
        ids = [int(i) for i in ids_str.split(',') if i.strip()]
        transactions = StockTransaction.query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.customer)
        ).filter(
            StockTransaction.id.in_(ids),
            StockTransaction.type == 'stock_out'
        ).order_by(StockTransaction.created_at.desc()).all()
    else:
        query = _build_query('stock_out', start_date, end_date, '', product_name, warehouse_id)
        transactions = query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.customer)
        ).order_by(StockTransaction.created_at.desc()).all()

    # 预加载批次信息
    batch_dict = _get_batch_dict(transactions)

    total_qty = 0
    items = []
    for idx, tx in enumerate(transactions, 1):
        product = tx.product
        customer = tx.customer
        batch_info = batch_dict.get(tx.batch_no.split(',')[0].strip() if tx.batch_no else '')

        item = {'seq': idx}
        for field in form_fields:
            item[field.field_code] = _get_field_value(tx, field.field_code, batch_info, product, customer)
        items.append(item)
        total_qty += tx.quantity

    today = datetime.now()
    
    # 获取仓库名称
    warehouse_name = ''
    if transactions:
        warehouse_name = transactions[0].warehouse.name if transactions[0].warehouse else ''

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='print',
        module='transaction',
        description='打印出库记录'
    )

    return render_template('stock_transactions/print_stock_out.html',
                           items=items,
                           form_fields=form_fields,
                           form_config=form_config,
                           warehouse_name=warehouse_name,
                           total_qty=total_qty,
                           today=today.strftime('%Y-%m-%d %H:%M'),
                           start_date=start_date,
                           end_date=end_date)


@stock_transactions_bp.route('/print/delivery-note')
@login_required
def print_delivery_note():
    """打印随货同行单 - 使用表单配置"""
    from models.user import User

    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    product_name = request.args.get('product_name', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    ids_str = request.args.get('ids', '').strip()

    # 获取当前登录用户信息
    user_id = session.get('user_id')
    user = User.query.get(user_id) if user_id else None
    operator_name = user.real_name if (user and user.real_name) else (user.username if user else '未知')

    # 获取表单配置
    form_config, form_fields = _get_form_config('delivery_note_form')

    # 查询出库记录 - 使用 joinedload 一次性加载关联数据
    if ids_str:
        ids = [int(i) for i in ids_str.split(',') if i.strip()]
        transactions = StockTransaction.query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.customer)
        ).filter(
            StockTransaction.id.in_(ids),
            StockTransaction.type == 'stock_out'
        ).order_by(StockTransaction.created_at.desc()).all()
    else:
        query = _build_query('stock_out', start_date, end_date, '', product_name, warehouse_id)
        transactions = query.options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.customer)
        ).order_by(StockTransaction.created_at.desc()).all()

    # 获取仓库名称
    warehouse_name = '默认仓库'
    if transactions and transactions[0].warehouse:
        warehouse_name = transactions[0].warehouse.name

    # 预加载批次信息
    batch_dict = _get_batch_dict(transactions)

    # 生成单号
    today = datetime.now()
    serial_no = f"{today.strftime('%Y%m%d')}-{str(len(transactions)+1).zfill(5)}"

    # 计算总金额
    total_amount = 0
    items = []
    recipient_name = ''
    recipient_address = ''
    for idx, tx in enumerate(transactions, 1):
        product = tx.product
        customer = tx.customer
        batch_info = batch_dict.get(tx.batch_no.split(',')[0].strip() if tx.batch_no else '')

        amount = (tx.unit_cost or 0) * tx.quantity
        total_amount += amount

        # 获取收货方信息（从第一条记录）
        if idx == 1:
            recipient_name = tx.customer_name or (customer.name if customer else '')
            recipient_address = tx.customer_address or (customer.address if customer else '')

        item = {'seq': idx}
        for field in form_fields:
            item[field.field_code] = _get_field_value(tx, field.field_code, batch_info, product, customer)
        items.append(item)

    # 大写金额
    def num2chinese(num):
        digits = '零壹贰叁肆伍陆柒捌玖'
        units = ['元', '拾', '佰', '仟', '万', '拾', '佰', '仟', '亿']
        decimals = ['角', '分']

        num_str = str(round(num, 2))
        if '.' in num_str:
            integer_part, decimal_part = num_str.split('.')
            decimal_part = decimal_part.ljust(2, '0')
        else:
            integer_part = num_str
            decimal_part = '00'

        result = ''
        integer_part = integer_part[::-1]

        for i, digit in enumerate(integer_part):
            if digit != '0':
                result = digits[int(digit)] + units[i] + result
            else:
                if i == 0 or (i > 0 and integer_part[i-1] != '0'):
                    result = '零' + result

        if result == '':
            result = '零'

        result += '元'

        if decimal_part[0] != '0':
            result += digits[int(decimal_part[0])] + '角'
        elif decimal_part[1] != '0':
            result += '零'

        if decimal_part[1] != '0':
            result += digits[int(decimal_part[1])] + '分'
        else:
            result += '整'

        return result

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='print',
        module='transaction',
        description='打印随货同行单'
    )

    return render_template('stock_transactions/print_delivery_note.html',
                           items=items,
                           form_fields=form_fields,
                           form_config=form_config,
                           total_amount=round(total_amount, 2),
                           total_amount_chinese=num2chinese(total_amount),
                           serial_no=serial_no,
                           today=today.strftime('%Y-%m-%d'),
                           warehouse=warehouse_name,
                           operator=operator_name,
                           recipient_name=recipient_name,
                           recipient_address=recipient_address)


def _build_query(tx_type=None, start_date=None, end_date=None, search=None, product_name=None, warehouse_id=None):
    """构建查询条件"""
    query = StockTransaction.query

    # 按类型筛选
    if tx_type:
        query = query.filter(StockTransaction.type == tx_type)

    # 按日期范围筛选
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(StockTransaction.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(
                hour=23, minute=59, second=59)
            query = query.filter(StockTransaction.created_at <= end_dt)
        except ValueError:
            pass

    # 按商品名称或客户名称筛选
    if product_name:
        query = query.outerjoin(Product).outerjoin(
            Customer, StockTransaction.customer_id == Customer.id
        ).filter(
            db.or_(
                Product.name.like(f'%{product_name}%'),
                StockTransaction.customer_name.like(f'%{product_name}%'),
                Customer.name.like(f'%{product_name}%')
            )
        )

    # 按仓库筛选
    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)

    # 按单号搜索
    if search:
        query = query.filter(
            db.or_(
                StockTransaction.transaction_no.like(f'%{search}%'),
                StockTransaction.reference_no.like(f'%{search}%')
            )
        )

    return query


def _get_form_config(form_code):
    """获取表单配置"""
    from models.form_config import FormConfig, FormFieldConfig
    form_config = FormConfig.query.filter_by(form_code=form_code, is_active=True).first()
    if not form_config:
        return None, []
    fields = FormFieldConfig.query.filter_by(
        form_config_id=form_config.id,
        is_visible=True
    ).order_by(FormFieldConfig.sort_order).all()
    return form_config, fields


def _get_batch_dict(transactions):
    """预加载批次信息"""
    batch_nos = []
    for tx in transactions:
        if tx.batch_no:
            first_batch_no = tx.batch_no.split(',')[0].strip()
            if first_batch_no:
                batch_nos.append(first_batch_no)

    batch_dict = {}
    if batch_nos:
        batches = ProductBatch.query.filter(ProductBatch.batch_no.in_(batch_nos)).all()
        for batch in batches:
            batch_dict[batch.batch_no] = {
                'batch_no': batch.batch_no,
                'production_date': batch.production_date.strftime('%Y-%m-%d') if batch.production_date else '',
                'expire_date': batch.expire_date.strftime('%Y-%m-%d') if batch.expire_date else ''
            }
    return batch_dict


def _get_field_value(tx, field_code, batch_info=None, product=None, customer=None):
    """根据字段代码获取字段值"""
    # 字段别名映射（兼容不同命名）
    field_aliases = {
        'product': 'product_name',
        'warehouse': 'warehouse_name',
        'customer': 'customer_name',
    }
    
    # 解析实际字段代码
    actual_code = field_aliases.get(field_code, field_code)
    
    # 基础字段映射
    value_map = {
        'transaction_no': tx.transaction_no,
        'product_name': product.name if product else (tx.product_name or ''),
        'product_sku': product.sku if product else '',
        'product_spec': product.specification if product else '',
        'specification': product.specification if product else '',
        'barcode': product.barcode if product else '',
        'warehouse_name': tx.warehouse.name if tx.warehouse else '',
        'customer_name': tx.customer_name or (customer.name if customer else ''),
        'customer_address': tx.customer_address or (customer.address if customer else ''),
        'quantity': tx.quantity,
        'unit_cost': tx.unit_cost,
        'batch_no': tx.batch_no or '',
        'production_date': batch_info.get('production_date', '') if batch_info else '',
        'expire_date': batch_info.get('expire_date', '') if batch_info else '',
        'expiry_date': batch_info.get('expire_date', '') if batch_info else '',
        'reference_no': tx.reference_no or '',
        'remark': tx.remark or '',
        'operator': tx.operator or '',
        'created_at': tx.created_at.strftime('%Y-%m-%d %H:%M') if tx.created_at else '',
        # 随货同行单专用字段
        'model': product.dosage_form if (product and product.dosage_form) else '',
        'manufacturer': product.manufacturer if (product and product.manufacturer) else '',
        'unit': product.unit if product else '',
        'unit_price': tx.unit_cost or 0,
        'amount': (tx.unit_cost or 0) * tx.quantity,
        'approval_no': product.approval_no if (product and product.approval_no) else '',
    }
    return value_map.get(actual_code, '')


# ============================================================
# 删除出入库记录
# ============================================================

def _delete_transfer_pair(tx_out, tx_in):
    """成对删除调拨记录，正确回滚库存"""
    try:
        # 确定哪个是调出、哪个是调入
        if tx_out.type == 'transfer_out':
            out_tx, in_tx = tx_out, tx_in
        else:
            out_tx, in_tx = tx_in, tx_out

        # 1. 回滚调出仓库库存（调出时减少了，删除时恢复）
        out_inv = Inventory.query.filter_by(
            product_id=out_tx.product_id, warehouse_id=out_tx.warehouse_id
        ).first()
        if out_inv:
            out_inv.quantity += out_tx.quantity

        # 2. 回滚调入仓库库存（调入时增加了，删除时减少）
        in_inv = Inventory.query.filter_by(
            product_id=in_tx.product_id, warehouse_id=in_tx.warehouse_id
        ).first()
        if in_inv:
            in_inv.quantity = max(0, in_inv.quantity - in_tx.quantity)
            if in_inv.quantity <= 0:
                db.session.delete(in_inv)

        # 3. 恢复调出仓库的批次和码段（支持多批次）
        if out_tx.batch_no and out_tx.product_id:
            batch_nos = [b.strip() for b in out_tx.batch_no.split(',') if b.strip()]
            for b_no in batch_nos:
                out_batch = ProductBatch.query.filter_by(
                    batch_no=b_no, product_id=out_tx.product_id,
                    warehouse_id=out_tx.warehouse_id
                ).first()
                if out_batch:
                    out_batch.remaining_quantity += out_tx.quantity
                    out_batch.total_quantity += out_tx.quantity
                    if out_batch.remaining_quantity > 0:
                        out_batch.status = 'active'

        # 4. 删除调入仓库的批次和码段（支持多批次）
        if in_tx.batch_no and in_tx.product_id:
            batch_nos = [b.strip() for b in in_tx.batch_no.split(',') if b.strip()]
            for b_no in batch_nos:
                in_batch = ProductBatch.query.filter_by(
                    batch_no=b_no, product_id=in_tx.product_id,
                    warehouse_id=in_tx.warehouse_id
                ).first()
                if in_batch:
                    # 删除该批次下的码段
                    BatchCode.query.filter_by(batch_id=in_batch.id).delete()
                    db.session.delete(in_batch)

        # 5. 恢复调出仓库的码段状态（transferred → in_stock）
        if out_tx.batch_codes:
            codes = [c.strip() for c in out_tx.batch_codes.split(',') if c.strip()]
            for code in codes:
                bc = BatchCode.query.filter_by(code=code, status='transferred').first()
                if bc:
                    bc.status = 'in_stock'
                    bc.transferred_at = None

        # 6. 删除两条交易记录
        out_no = out_tx.transaction_no
        in_no = in_tx.transaction_no
        db.session.delete(out_tx)
        db.session.delete(in_tx)
        db.session.commit()

        # 记录操作日志
        try:
            LogService.log_operation(
                user_id=session.get('user_id'),
                username=session.get('username'),
                operation_type='delete',
                module='transaction',
                description=f'删除调拨记录（调出{out_no}，调入{in_no}）'
            )
        except Exception:
            pass

        return jsonify({
            'success': True,
            'message': f'调拨记录已删除（调出{out_no} + 调入{in_no}）'
        })
        
    except Exception as e:
        db.session.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'删除调拨记录失败: {e}', exc_info=True)
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


@stock_transactions_bp.route('/delete/<int:tx_id>', methods=['POST'])
@login_required
def delete_transaction(tx_id):
    """删除出入库记录，检查关联数据"""
    try:
        tx = StockTransaction.query.get_or_404(tx_id)
        
        # 调拨记录必须成对删除
        if tx.type in ['transfer_out', 'transfer_in']:
            paired_no = tx.reference_no
            if paired_no:
                paired_tx = StockTransaction.query.filter_by(transaction_no=paired_no).first()
                if paired_tx:
                    return _delete_transfer_pair(tx, paired_tx)
                else:
                    return jsonify({
                        'success': False,
                        'message': f'该调拨记录的配对记录（{paired_no}）已被删除，数据不完整。请联系管理员处理。',
                        'related_nos': []
                    })
            else:
                return jsonify({
                    'success': False,
                    'message': '该调拨记录缺少配对单号，数据异常。请联系管理员处理。',
                    'related_nos': []
                })
        
        # 检查关联数据
        blockers = []
        related_nos = []
        
        if tx.type == 'stock_in' and tx.batch_no:
            batch_nos = [b.strip() for b in tx.batch_no.split(',') if b.strip()]
            for batch_no in batch_nos:
                out_txs = StockTransaction.query.filter(
                    StockTransaction.type == 'stock_out',
                    StockTransaction.batch_no.like(f'%{batch_no}%'),
                    StockTransaction.product_id == tx.product_id,
                    StockTransaction.id != tx.id
                ).all()
                if out_txs:
                    blockers.append(f'有 {len(out_txs)} 条出库记录关联批次 {batch_no}')
                    related_nos.extend([t.transaction_no for t in out_txs])
                
                transfer_txs = StockTransaction.query.filter(
                    StockTransaction.type.in_(['transfer_in', 'transfer_out']),
                    StockTransaction.batch_no.like(f'%{batch_no}%'),
                    StockTransaction.product_id == tx.product_id,
                    StockTransaction.id != tx.id
                ).all()
                if transfer_txs:
                    blockers.append(f'有 {len(transfer_txs)} 条调拨记录关联批次 {batch_no}')
                    related_nos.extend([t.transaction_no for t in transfer_txs])
        
        elif tx.type in ['transfer_in', 'transfer_out'] and tx.batch_no:
            batch_nos = [b.strip() for b in tx.batch_no.split(',') if b.strip()]
            for batch_no in batch_nos:
                out_txs = StockTransaction.query.filter(
                    StockTransaction.type == 'stock_out',
                    StockTransaction.batch_no.like(f'%{batch_no}%'),
                    StockTransaction.product_id == tx.product_id,
                    StockTransaction.id != tx.id
                ).all()
                if out_txs:
                    blockers.append(f'有 {len(out_txs)} 条出库记录关联批次 {batch_no}')
                    related_nos.extend([t.transaction_no for t in out_txs])
        
        if blockers:
            return jsonify({
                'success': False,
                'message': '；'.join(blockers) + '。请先处理关联数据后再删除。',
                'related_nos': related_nos
            })
        
        # 执行删除并更新库存
        transaction_no = tx.transaction_no
        tx_type = tx.type
        product_id = tx.product_id
        warehouse_id = tx.warehouse_id
        quantity = tx.quantity
        batch_no = tx.batch_no
        batch_codes = tx.batch_codes
        
        # 1. 更新 Inventory 表的库存数量
        inventory = Inventory.query.filter_by(
            product_id=product_id,
            warehouse_id=warehouse_id
        ).first()
        
        if inventory:
            if tx_type == 'stock_in':
                inventory.quantity = max(0, inventory.quantity - quantity)
            elif tx_type == 'stock_out':
                inventory.quantity = inventory.quantity + quantity
            elif tx_type == 'transfer_out':
                inventory.quantity = max(0, inventory.quantity - quantity)
            elif tx_type == 'transfer_in':
                inventory.quantity = inventory.quantity + quantity
            
            if inventory.quantity <= 0:
                db.session.delete(inventory)
        
        # 2. 恢复 BatchCode 状态（出库→入库，调拨出→调拨入）
        if (tx_type == 'stock_out') and batch_codes:
            codes = [c.strip() for c in batch_codes.split(',') if c.strip()]
            for code in codes:
                bc = BatchCode.query.filter_by(code=code, status='sold').first()
                if bc:
                    bc.status = 'in_stock'
                    bc.customer_id = None
                    bc.customer_name = None
                    bc.stock_out_no = None
                    bc.sold_at = None
        elif tx_type == 'transfer_out' and batch_codes:
            codes = [c.strip() for c in batch_codes.split(',') if c.strip()]
            for code in codes:
                bc = BatchCode.query.filter_by(code=code, status='transferred').first()
                if bc:
                    bc.status = 'in_stock'
                    bc.transferred_at = None
        
        # 3. 更新 ProductBatch 的 remaining_quantity
        if batch_no and product_id and warehouse_id:
            batch_nos = [b.strip() for b in batch_no.split(',') if b.strip()]
            for b_no in batch_nos:
                batch = ProductBatch.query.filter_by(
                    batch_no=b_no,
                    product_id=product_id,
                    warehouse_id=warehouse_id
                ).first()
                if batch:
                    if tx_type == 'stock_in':
                        # 删除入库：减少批次数量或删除批次
                        if batch_codes:
                            # 有批次码的入库，删除整个批次及其码
                            BatchCode.query.filter_by(batch_id=batch.id).delete()
                            db.session.delete(batch)
                        else:
                            # 无批次码，减少数量
                            batch.remaining_quantity = max(0, batch.remaining_quantity - quantity)
                            batch.total_quantity = max(0, batch.total_quantity - quantity)
                            if batch.remaining_quantity == 0:
                                batch.status = 'exhausted'
                    
                    elif tx_type == 'stock_out':
                        # 删除出库：根据当前批次码状态重新计算
                        remaining = BatchCode.query.filter_by(batch_id=batch.id, status='in_stock').count()
                        batch.remaining_quantity = remaining
                        batch.total_quantity = max(batch.total_quantity, remaining)
                        if remaining > 0:
                            batch.status = 'active'
                        else:
                            batch.status = 'exhausted'
                    
                    elif tx_type == 'transfer_out':
                        # 删除调拨出：恢复批次码后重新计算
                        remaining = BatchCode.query.filter_by(batch_id=batch.id, status='in_stock').count()
                        batch.remaining_quantity = remaining
                        if remaining > 0:
                            batch.status = 'active'
                        else:
                            batch.status = 'exhausted'
                    
                    elif tx_type == 'transfer_in':
                        # 删除调入：减少批次数量或删除批次
                        if batch_codes:
                            BatchCode.query.filter_by(batch_id=batch.id).delete()
                            db.session.delete(batch)
                        else:
                            batch.remaining_quantity = max(0, batch.remaining_quantity - quantity)
                            batch.total_quantity = max(0, batch.total_quantity - quantity)
                            if batch.remaining_quantity == 0:
                                batch.status = 'exhausted'
        
        # 4. 删除交易记录
        db.session.delete(tx)
        db.session.commit()
        
        # 记录操作日志
        try:
            LogService.log_operation(
                user_id=session.get('user_id'),
                username=session.get('username'),
                operation_type='delete',
                module='transaction',
                description=f'删除出入库记录 {transaction_no}'
            )
        except Exception:
            pass
        
        return jsonify({'success': True, 'message': '删除成功'})
        
    except Exception as e:
        db.session.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'删除出入库记录失败: {e}', exc_info=True)
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500


# ============================================================
# 库存一致性校验
# ============================================================

@stock_transactions_bp.route('/verify-consistency', methods=['POST'])
@login_required
def verify_inventory_consistency():
    """校验库存数据一致性"""
    from services.inventory_service import InventoryService
    
    try:
        result = InventoryService.verify_inventory_consistency()
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'库存一致性校验失败: {e}', exc_info=True)
        return jsonify({'success': False, 'message': f'校验失败: {str(e)}'}), 500
