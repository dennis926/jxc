from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db
from models.purchase_order import PurchaseOrder, PurchaseOrderItem
from models.product import Product
from models.warehouse import Warehouse
from models.supplier import Supplier
from services.inventory_service import InventoryService
from services.log_service import LogService
from utils.decorators import login_required
from utils.excel_export import export_to_excel
from sqlalchemy.orm import joinedload

purchase_orders_bp = Blueprint('purchase_orders', __name__, url_prefix='/purchase-orders')


@purchase_orders_bp.route('/')
@login_required
def list():
    """采购单列表"""
    try:
        page = request.args.get('page', 1, type=int)
        status = request.args.get('status', '').strip()
        search = request.args.get('search', '').strip()
        sort = request.args.get('sort', 'created_at')
        order = request.args.get('order', 'desc')
        ALLOWED_SORT_FIELDS = {'po_no', 'supplier_id', 'status', 'total_amount', 'created_at', 'updated_at'}
        if sort not in ALLOWED_SORT_FIELDS:
            sort = 'created_at'

        query = PurchaseOrder.query.options(
            joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product),
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.warehouse)
        )

        # 按状态筛选
        if status:
            query = query.filter(PurchaseOrder.status == status)

        # 按单号搜索
        if search:
            query = query.filter(
                db.or_(
                    PurchaseOrder.po_no.like(f'%{search}%'),
                    PurchaseOrder.supplier.has(Supplier.name.like(f'%{search}%'))
                )
            )

        # 排序
        sort_field = getattr(PurchaseOrder, sort, PurchaseOrder.created_at)
        if order == 'desc':
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())

        pagination = query.paginate(page=page, per_page=15, error_out=False)

        # 状态选项
        status_options = [
            ('draft', '草稿'),
            ('pending', '待入库'),
            ('partial', '部分入库'),
            ('received', '已入库'),
            ('cancelled', '已取消'),
        ]

        return render_template('purchase_orders/list.html',
                               orders=pagination.items,
                               pagination=pagination,
                               status=status,
                               search=search,
                               status_options=status_options,
                               sort=sort,
                               order=order)
    except Exception as e:
        error_msg = str(e)
        flash(f'加载采购单列表失败: {error_msg}', 'danger')
        return render_template('purchase_orders/list.html',
                               orders=[],
                               pagination=None,
                               status=status,
                               search=search,
                               status_options=[('draft', '草稿'), ('pending', '待入库'), ('partial', '部分入库'), ('received', '已入库'), ('cancelled', '已取消')],
                               sort=sort,
                               order=order)


@purchase_orders_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """新增采购单"""
    if request.method == 'POST':
        try:
            # 生成采购单号
            po_no = PurchaseOrder.generate_po_no()

            supplier_id = request.form.get('supplier_id', type=int)
            warehouse_id = request.form.get('warehouse_id', type=int)
            remark = request.form.get('remark', '').strip()

            if not supplier_id or not warehouse_id:
                flash('请选择供应商和入库仓库', 'danger')
                return redirect(url_for('purchase_orders.create'))

            # 创建采购单
            purchase_order = PurchaseOrder(
                po_no=po_no,
                supplier_id=supplier_id,
                warehouse_id=warehouse_id,
                status='draft',
                total_amount=0,
                remark=remark
            )
            db.session.add(purchase_order)
            db.session.flush()

            # 处理采购单明细
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_costs = request.form.getlist('unit_cost[]')

            total_amount = 0
            for i in range(len(product_ids)):
                pid = int(product_ids[i]) if product_ids[i] else 0
                qty = int(quantities[i]) if quantities[i] else 0
                cost = float(unit_costs[i]) if unit_costs[i] else 0

                if pid and qty > 0:
                    item = PurchaseOrderItem(
                        purchase_order_id=purchase_order.id,
                        product_id=pid,
                        quantity=qty,
                        unit_cost=cost,
                        received_quantity=0
                    )
                    db.session.add(item)
                    total_amount += qty * cost

            purchase_order.total_amount = total_amount
            purchase_order.status = 'pending'

            db.session.commit()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='create', module='采购单', description=f'创建采购单: {po_no}')
            flash(f'采购单 {po_no} 创建成功', 'success')
            return redirect(url_for('purchase_orders.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败: {str(e)}', 'danger')

    # 获取可选的供应商、仓库和商品
    suppliers = Supplier.query.order_by(Supplier.name).all()
    warehouses = Warehouse.query.filter_by(is_active=True).all()
    products = Product.query.order_by(Product.name).all()

    return render_template('purchase_orders/form.html',
                           suppliers=suppliers,
                           warehouses=warehouses,
                           products=products,
                           order=None)


@purchase_orders_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """编辑采购单（仅草稿状态可编辑）"""
    order = PurchaseOrder.query.get_or_404(id)

    if order.status not in ('draft', 'pending'):
        flash('当前状态的采购单不可编辑', 'danger')
        return redirect(url_for('purchase_orders.list'))

    if request.method == 'POST':
        try:
            order.supplier_id = request.form.get('supplier_id', type=int)
            order.warehouse_id = request.form.get('warehouse_id', type=int)
            order.remark = request.form.get('remark', '').strip()

            if not order.supplier_id or not order.warehouse_id:
                flash('请选择供应商和入库仓库', 'danger')
                return redirect(url_for('purchase_orders.edit', id=id))

            # 删除旧明细（先保存已入库数量，用于恢复）
            old_items = PurchaseOrderItem.query.filter_by(purchase_order_id=id).all()
            received_map = {}
            for old_item in old_items:
                if old_item.received_quantity and old_item.received_quantity > 0:
                    received_map[old_item.product_id] = old_item.received_quantity
            PurchaseOrderItem.query.filter_by(purchase_order_id=id).delete()

            # 添加新明细
            product_ids = request.form.getlist('product_id[]')
            quantities = request.form.getlist('quantity[]')
            unit_costs = request.form.getlist('unit_cost[]')

            total_amount = 0
            for i in range(len(product_ids)):
                pid = int(product_ids[i]) if product_ids[i] else 0
                qty = int(quantities[i]) if quantities[i] else 0
                cost = float(unit_costs[i]) if unit_costs[i] else 0

                if pid and qty > 0:
                    # 恢复已入库数量
                    recv_qty = received_map.get(pid, 0)
                    item = PurchaseOrderItem(
                        purchase_order_id=id,
                        product_id=pid,
                        quantity=qty,
                        unit_cost=cost,
                        received_quantity=recv_qty
                    )
                    db.session.add(item)
                    total_amount += qty * cost

            order.total_amount = total_amount
            db.session.commit()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='update', module='采购单', description=f'编辑采购单: {order.po_no}')
            flash('采购单更新成功', 'success')
            return redirect(url_for('purchase_orders.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败: {str(e)}', 'danger')

    suppliers = Supplier.query.order_by(Supplier.name).all()
    warehouses = Warehouse.query.filter_by(is_active=True).all()
    products = Product.query.order_by(Product.name).all()
    items = order.items

    return render_template('purchase_orders/form.html',
                           suppliers=suppliers,
                           warehouses=warehouses,
                           products=products,
                           order=order,
                           items=items)


@purchase_orders_bp.route('/cancel/<int:id>', methods=['POST'])
@login_required
def cancel(id):
    """取消采购单"""
    order = PurchaseOrder.query.get_or_404(id)

    if order.status in ('received', 'cancelled'):
        flash('已入库或已取消的采购单不能取消', 'danger')
        return redirect(url_for('purchase_orders.list'))

    order.status = 'cancelled'
    db.session.commit()
    LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='cancel', module='采购单', description=f'取消采购单: {order.po_no}')
    flash('采购单已取消', 'success')
    return redirect(url_for('purchase_orders.list'))


@purchase_orders_bp.route('/receive/<int:id>', methods=['GET', 'POST'])
@login_required
def receive(id):
    """采购入库确认"""
    order = PurchaseOrder.query.get_or_404(id)

    if order.status == 'cancelled':
        flash('已取消的采购单不能入库', 'danger')
        return redirect(url_for('purchase_orders.list'))

    if order.status == 'received':
        flash('该采购单已全部入库', 'warning')
        return redirect(url_for('purchase_orders.list'))

    if request.method == 'POST':
        try:
            items = []
            item_ids = request.form.getlist('item_id[]')
            received_quantities = request.form.getlist('received_quantity[]')
            batch_codes_list = request.form.getlist('batch_code[]')
            production_dates_list = request.form.getlist('production_date[]')
            expire_dates_list = request.form.getlist('expire_date[]')

            for i in range(len(item_ids)):
                item_id = int(item_ids[i]) if item_ids[i] else 0
                received_qty = int(received_quantities[i]) if received_quantities[i] else 0
                batch_code_str = batch_codes_list[i].strip() if i < len(batch_codes_list) else ''
                production_date_str = production_dates_list[i].strip() if i < len(production_dates_list) else ''
                expire_date_str = expire_dates_list[i].strip() if i < len(expire_dates_list) else ''
                
                # 解析单个商品的码段
                batch_codes = None
                if batch_code_str:
                    # 处理范围格式（如 "100001-100500"）
                    if '-' in batch_code_str and ',' not in batch_code_str:
                        batch_codes = batch_code_str
                    # 处理逗号分隔格式
                    elif ',' in batch_code_str:
                        batch_codes = [c.strip() for c in batch_code_str.split(',') if c.strip()]
                    # 处理单个码
                    else:
                        batch_codes = [batch_code_str]

                if item_id and received_qty > 0:
                    items.append({
                        'item_id': item_id,
                        'received_quantity': received_qty,
                        'batch_codes': batch_codes,
                        'production_date': production_date_str if production_date_str else None,
                        'expire_date': expire_date_str if expire_date_str else None
                    })

            if not items:
                flash('请填写入库数量', 'danger')
                return redirect(url_for('purchase_orders.receive', id=id))

            InventoryService.confirm_purchase_order_received(
                order.id, items
            )
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='receive', module='采购单', description=f'采购入库: {order.po_no}')
            flash('入库确认成功', 'success')
            return redirect(url_for('purchase_orders.list'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('purchase_orders.receive', id=id))
        except Exception as e:
            flash(f'入库失败: {str(e)}', 'danger')
            return redirect(url_for('purchase_orders.receive', id=id))

    # 获取采购单明细
    items = order.items

    return render_template('purchase_orders/receive.html',
                           order=order,
                           items=items)


@purchase_orders_bp.route('/export')
@login_required
def export():
    """导出采购单列表到Excel"""
    from datetime import datetime as dt
    
    status = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    query = PurchaseOrder.query

    # 按状态筛选
    if status:
        query = query.filter(PurchaseOrder.status == status)

    # 按单号搜索
    if search:
        query = query.filter(
            db.or_(
                PurchaseOrder.po_no.like(f'%{search}%'),
                PurchaseOrder.supplier.has(Supplier.name.like(f'%{search}%'))
            )
        )

    orders = query.order_by(PurchaseOrder.created_at.desc()).all()

    # 状态映射
    status_map = {
        'draft': '草稿',
        'pending': '待入库',
        'partial': '部分入库',
        'received': '已入库',
        'cancelled': '已取消'
    }

    data = []
    idx = 1
    for order in orders:
        # 展开每个采购单的商品明细
        if order.items:
            for item in order.items:
                data.append({
                    'idx': idx,
                    'po_no': order.po_no,
                    'supplier': order.supplier.name if order.supplier else '',
                    'product_name': item.product.name if item.product else '',
                    'quantity': item.quantity,
                    'warehouse': order.warehouse.name if order.warehouse else '',
                    'status': status_map.get(order.status, order.status),
                    'remark': order.remark or '',
                    'export_time': dt.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                idx += 1
        else:
            # 没有商品的采购单也要显示
            data.append({
                'idx': idx,
                'po_no': order.po_no,
                'supplier': order.supplier.name if order.supplier else '',
                'product_name': '',
                'quantity': 0,
                'warehouse': order.warehouse.name if order.warehouse else '',
                'status': status_map.get(order.status, order.status),
                'remark': order.remark or '',
                'export_time': dt.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            idx += 1

    headers = [
        ('idx', '序号'),
        ('po_no', '采购单号'),
        ('supplier', '供应商'),
        ('product_name', '商品名称'),
        ('quantity', '采购数量'),
        ('warehouse', '入库仓库'),
        ('status', '状态'),
        ('remark', '备注'),
        ('export_time', '导出时间')
    ]

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='purchase',
        description='导出采购单列表'
    )
    
    return export_to_excel(data, headers, '采购单列表.xlsx')
