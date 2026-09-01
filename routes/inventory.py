from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
from models import db
from models.inventory import Inventory
from models.product import Product
from models.warehouse import Warehouse
from models.purchase_order import PurchaseOrder
from models.customer import Customer
from models.product_batch import ProductBatch
from services.inventory_service import InventoryService
from services.log_service import LogService
from utils.decorators import login_required
from utils.excel_export import export_to_excel

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')


@inventory_bp.route('/')
@login_required
def list():
    """库存查询列表"""
    page = request.args.get('page', 1, type=int)
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'product_name')
    order = request.args.get('order', 'asc')

    query = Inventory.query.join(Product, Inventory.product_id == Product.id).join(
        Warehouse, Inventory.warehouse_id == Warehouse.id).filter(
        Inventory.quantity > 0
    )

    # 按仓库筛选
    if warehouse_id:
        query = query.filter(Inventory.warehouse_id == warehouse_id)

    # 按商品搜索
    if search:
        query = query.filter(
            db.or_(
                Product.name.like(f'%{search}%'),
                Product.sku.like(f'%{search}%')
            )
        )

    # 排序 - 支持关联字段
    if sort == 'product_name':
        sort_field = Product.name
    elif sort == 'product_sku':
        sort_field = Product.sku
    elif sort == 'warehouse_name':
        sort_field = Warehouse.name
    elif sort == 'quantity':
        sort_field = Inventory.quantity
    elif sort == 'updated_at':
        sort_field = Inventory.updated_at
    else:
        sort_field = Product.name

    if order == 'desc':
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())

    pagination = query.paginate(page=page, per_page=15, error_out=False)

    # 获取批次信息并计算有效期
    today = datetime.now().date()
    for inv in pagination.items:
        # 查询该商品在该仓库的所有有效批次
        batches = ProductBatch.query.filter(
            ProductBatch.product_id == inv.product_id,
            ProductBatch.warehouse_id == inv.warehouse_id,
            ProductBatch.remaining_quantity > 0,
            ProductBatch.status.in_(['active', 'partial'])
        ).order_by(ProductBatch.production_date.asc()).all()

        inv.batches_info = []
        for batch in batches:
            batch_info = {
                'production_date': batch.production_date.strftime('%Y-%m-%d') if batch.production_date else None,
                'expire_date': batch.expire_date.strftime('%Y-%m-%d') if batch.expire_date else None,
                'remaining_quantity': batch.remaining_quantity,
                'days_remaining': 0
            }
            # 计算剩余天数（确保类型一致）
            if batch.expire_date:
                expire_date = batch.expire_date.date() if hasattr(batch.expire_date, 'date') else batch.expire_date
                delta = expire_date - today
                batch_info['days_remaining'] = int(delta.days) if delta.days is not None else 0
            inv.batches_info.append(batch_info)

    # 获取所有启用的仓库
    warehouses = Warehouse.query.filter_by(is_active=True).all()

    return render_template('inventory/list.html',
                           inventories=pagination.items,
                           pagination=pagination,
                           warehouses=warehouses,
                           warehouse_id=warehouse_id,
                           search=search,
                           sort=sort,
                           order=order)


@inventory_bp.route('/stock_in', methods=['GET', 'POST'])
@login_required
def stock_in():
    """入库操作"""
    if request.method == 'POST':
        try:
            product_id = request.form.get('product_id', type=int)
            warehouse_id = request.form.get('warehouse_id', type=int)
            quantity = request.form.get('quantity', type=int)
            unit_cost = request.form.get('unit_cost', 0, type=float)
            reference_no = request.form.get('reference_no', '').strip()
            operator = request.form.get('operator', '').strip()
            remark = request.form.get('remark', '').strip()
            batch_codes_str = request.form.get('batch_codes', '').strip()
            production_date_str = request.form.get('production_date', '').strip()
            expire_date_str = request.form.get('expire_date', '').strip()

            if not product_id or not warehouse_id or not quantity:
                flash('请填写完整的入库信息', 'danger')
                return redirect(url_for('inventory.stock_in'))

            # 解析批次码
            batch_codes = []
            if batch_codes_str:
                batch_codes = batch_codes_str.split(',')

            InventoryService.stock_in(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity,
                unit_cost=unit_cost,
                reference_no=reference_no,
                operator=operator,
                remark=remark,
                batch_codes=batch_codes,
                production_date=production_date_str if production_date_str else None,
                expire_date=expire_date_str if expire_date_str else None
            )

            flash('入库成功', 'success')
            return redirect(url_for('inventory.list'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('inventory.stock_in'))
        except Exception as e:
            flash(f'入库失败: {str(e)}', 'danger')
            return redirect(url_for('inventory.stock_in'))

    # 获取可选的仓库和商品（只显示启用的）
    warehouses = Warehouse.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    # 获取待入库的采购单（状态为pending或partial）
    purchase_orders = PurchaseOrder.query.filter(
        PurchaseOrder.status.in_(['pending', 'partial'])
    ).all()

    return render_template('inventory/stock_in.html',
                           warehouses=warehouses,
                           products=products,
                           purchase_orders=purchase_orders)


@inventory_bp.route('/stock_out', methods=['GET', 'POST'])
@login_required
def stock_out():
    """出库操作"""
    if request.method == 'POST':
        try:
            product_id = request.form.get('product_id', type=int)
            warehouse_id = request.form.get('warehouse_id', type=int)
            customer_id = request.form.get('customer_id', type=int)
            quantity = request.form.get('quantity', type=int)
            reference_no = request.form.get('reference_no', '').strip()
            operator = request.form.get('operator', '').strip()
            remark = request.form.get('remark', '').strip()
            batch_codes_str = request.form.get('batch_codes', '').strip()

            if not product_id or not warehouse_id or not quantity:
                flash('请填写完整的出库信息', 'danger')
                return redirect(url_for('inventory.stock_out'))

            # 解析批次码
            batch_codes = []
            if batch_codes_str:
                batch_codes = batch_codes_str.split(',')

            InventoryService.stock_out(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity,
                reference_no=reference_no,
                operator=operator,
                remark=remark,
                customer_id=customer_id,
                batch_codes=batch_codes
            )

            flash('出库成功', 'success')
            return redirect(url_for('inventory.list'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('inventory.stock_out'))
        except Exception as e:
            flash(f'出库失败: {str(e)}', 'danger')
            return redirect(url_for('inventory.stock_out'))

    # 获取可选的仓库和商品（只显示启用的）
    warehouses = Warehouse.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()

    return render_template('inventory/stock_out.html',
                           warehouses=warehouses,
                           products=products,
                           customers=customers)


@inventory_bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """调拨操作"""
    if request.method == 'POST':
        try:
            product_id = request.form.get('product_id', type=int)
            from_warehouse_id = request.form.get('from_warehouse_id', type=int)
            to_warehouse_id = request.form.get('to_warehouse_id', type=int)
            quantity = request.form.get('quantity', type=int)
            operator = request.form.get('operator', '').strip()
            remark = request.form.get('remark', '').strip()
            batch_codes_str = request.form.get('batch_codes', '').strip()

            # 解析批次码
            batch_codes = []
            if batch_codes_str:
                batch_codes = batch_codes_str.split(',')

            if not product_id or not from_warehouse_id or not to_warehouse_id or not quantity:
                error_msg = '请填写完整的调拨信息'
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.content_type:
                    return jsonify({'success': False, 'message': error_msg})
                flash(error_msg, 'danger')
                return redirect(url_for('inventory.transfer'))

            InventoryService.transfer(
                product_id=product_id,
                from_warehouse_id=from_warehouse_id,
                to_warehouse_id=to_warehouse_id,
                quantity=quantity,
                operator=operator,
                remark=remark,
                batch_codes=batch_codes
            )
            
            # 记录操作日志
            product = Product.query.get(product_id)
            from_warehouse = Warehouse.query.get(from_warehouse_id)
            to_warehouse = Warehouse.query.get(to_warehouse_id)
            product_name = product.name if product else ''
            from_warehouse_name = from_warehouse.name if from_warehouse else ''
            to_warehouse_name = to_warehouse.name if to_warehouse else ''
            LogService.log_operation(
                user_id=session.get('user_id'),
                username=session.get('username'),
                operation_type='transfer',
                module='inventory',
                description=f'调拨: 商品={product_name}, 从={from_warehouse_name}, 到={to_warehouse_name}, 数量={quantity}',
                reference_type='transfer'
            )

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.content_type:
                return jsonify({'success': True, 'message': '调拨成功'})
            flash('调拨成功', 'success')
            return redirect(url_for('inventory.list'))
        except ValueError as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.content_type:
                return jsonify({'success': False, 'message': str(e)})
            flash(str(e), 'danger')
            return redirect(url_for('inventory.transfer'))
        except Exception as e:
            error_msg = str(e)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.content_type:
                return jsonify({'success': False, 'message': f'调拨失败: {error_msg}'})
            flash(f'调拨失败: {error_msg}', 'danger')
            return redirect(url_for('inventory.transfer'))

    # 获取可选的仓库和商品（只显示启用的）
    warehouses = Warehouse.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    return render_template('inventory/transfer.html',
                           warehouses=warehouses,
                           products=products)


@inventory_bp.route('/export')
@login_required
def export():
    """导出库存列表到Excel"""
    from models.product_batch import ProductBatch
    from datetime import datetime as dt
    
    query = Inventory.query.join(Product, Inventory.product_id == Product.id).join(
        Warehouse, Inventory.warehouse_id == Warehouse.id)
    
    inventories = query.all()
    data = []
    for idx, inv in enumerate(inventories, 1):
        # 获取该商品在该仓库最早过期的批次信息
        batch = ProductBatch.query.filter_by(
            product_id=inv.product_id,
            warehouse_id=inv.warehouse_id,
            status='active'
        ).order_by(ProductBatch.expire_date.asc()).first()
        
        production_date = ''
        expire_date = ''
        if batch:
            production_date = batch.production_date.strftime('%Y-%m-%d') if batch.production_date else ''
            expire_date = batch.expire_date.strftime('%Y-%m-%d') if batch.expire_date else ''
        
        data.append({
            'idx': idx,
            'sku': inv.product.sku,
            'name': inv.product.name,
            'quantity': inv.quantity,
            'warehouse': inv.warehouse.name,
            'production_date': production_date,
            'expire_date': expire_date,
            'updated_at': inv.updated_at.strftime('%Y-%m-%d %H:%M') if inv.updated_at else '',
            'export_time': dt.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    headers = [
        ('idx', '序号'),
        ('sku', '商品编码'),
        ('name', '商品名称'),
        ('quantity', '库存数量'),
        ('warehouse', '仓库'),
        ('production_date', '生产日期'),
        ('expire_date', '有效日期'),
        ('updated_at', '更新时间'),
        ('export_time', '导出时间')
    ]
    
    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='inventory',
        description='导出库存列表'
    )
    
    return export_to_excel(data, headers, '库存列表.xlsx')


@inventory_bp.route('/adjust', methods=['GET', 'POST'])
@login_required
def adjust():
    """库存盘点调整"""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        warehouse_id = request.form.get('warehouse_id', type=int)
        new_quantity = request.form.get('new_quantity', type=int)
        reason = request.form.get('reason', '').strip()
        
        if not product_id or not warehouse_id or new_quantity is None:
            flash('请填写完整的盘点信息', 'danger')
            return redirect(url_for('inventory.adjust'))
        
        try:
            InventoryService.adjust(
                product_id=product_id,
                warehouse_id=warehouse_id,
                new_quantity=new_quantity,
                operator=session.get('real_name', session.get('username', '')),
                remark=reason
            )
            
            # 记录操作日志
            product = Product.query.get(product_id)
            warehouse = Warehouse.query.get(warehouse_id)
            product_name = product.name if product else ''
            warehouse_name = warehouse.name if warehouse else ''
            LogService.log_operation(
                user_id=session.get('user_id'),
                username=session.get('username'),
                operation_type='adjust',
                module='inventory',
                description=f'库存调整: 商品={product_name}, 仓库={warehouse_name}, 调整后数量={new_quantity}, 原因={reason}',
                reference_type='adjust'
            )
            
            flash('库存盘点调整成功', 'success')
            return redirect(url_for('inventory.list'))
        except Exception as e:
            flash(f'盘点调整失败: {str(e)}', 'danger')
            return redirect(url_for('inventory.adjust'))
    
    warehouses = Warehouse.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    return render_template('inventory/adjust.html',
                         warehouses=warehouses,
                         products=products)


@inventory_bp.route('/api/check')
@login_required
def api_check():
    """AJAX API: 检查指定仓库商品的当前库存"""
    warehouse_id = request.args.get('warehouse_id', type=int)
    product_id = request.args.get('product_id', type=int)
    
    if not warehouse_id or not product_id:
        return jsonify({'success': False, 'message': '参数错误'})
    
    inventory = Inventory.query.filter_by(
        warehouse_id=warehouse_id,
        product_id=product_id
    ).first()
    
    if inventory:
        return jsonify({
            'success': True,
            'quantity': inventory.quantity,
            'updated_at': inventory.updated_at.strftime('%Y-%m-%d %H:%M') if inventory.updated_at else None
        })
    else:
        return jsonify({
            'success': True,
            'quantity': 0,
            'message': '该商品在此仓库无库存记录'
        })


@inventory_bp.route('/api/products-by-warehouse')
@login_required
def api_products_by_warehouse():
    """AJAX API: 获取指定仓库有库存的商品列表"""
    warehouse_id = request.args.get('warehouse_id', type=int)
    
    if not warehouse_id:
        return jsonify({'success': False, 'message': '参数错误'})
    
    # 查询该仓库有库存的商品
    inventories = Inventory.query.filter(
        Inventory.warehouse_id == warehouse_id,
        Inventory.quantity > 0
    ).all()
    
    products = []
    for inv in inventories:
        product = Product.query.get(inv.product_id)
        if product and product.is_active:
            products.append({
                'id': product.id,
                'name': product.name,
                'sku': product.sku,
                'barcode': product.barcode,
                'quantity': inv.quantity
            })
    
    return jsonify({
        'success': True,
        'products': products
    })
