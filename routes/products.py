from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models import db
from models.product import Product
from models.inventory import Inventory
from models.stock_transaction import StockTransaction
from models.purchase_order import PurchaseOrderItem, PurchaseOrder
from services.log_service import LogService
from utils.decorators import login_required
from utils.excel_export import export_to_excel
from datetime import datetime

products_bp = Blueprint('products', __name__, url_prefix='/products')


@products_bp.route('/')
@login_required
def list():
    """商品列表"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    status = request.args.get('status', '').strip()
    sort = request.args.get('sort', 'name')  # 默认按名称排序
    order = request.args.get('order', 'asc')  # 默认升序
    ALLOWED_SORT_FIELDS = {'name', 'sku', 'category', 'unit', 'price', 'stock', 'status', 'created_at'}
    if sort not in ALLOWED_SORT_FIELDS:
        sort = 'name'

    query = Product.query

    # 搜索过滤
    if search:
        query = query.filter(
            db.or_(
                Product.name.like(f'%{search}%'),
                Product.sku.like(f'%{search}%'),
                Product.barcode.like(f'%{search}%')
            )
        )

    # 分类筛选
    if category:
        query = query.filter(Product.category == category)
    
    # 状态筛选
    if status == 'active':
        query = query.filter(Product.is_active == True)
    elif status == 'inactive':
        query = query.filter(Product.is_active == False)

    # 排序
    sort_field = getattr(Product, sort, Product.name)
    if order == 'desc':
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())

    # 分页
    pagination = query.paginate(page=page, per_page=15, error_out=False)

    # 获取所有分类（用于筛选下拉框）
    categories = db.session.query(Product.category).distinct().filter(
        Product.category != ''
    ).all()
    categories = [c[0] for c in categories]

    return render_template('products/list.html',
                           products=pagination.items,
                           pagination=pagination,
                           search=search,
                           category=category,
                           status=status,
                           categories=categories,
                           sort=sort,
                           order=order)


@products_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """新增商品"""
    if request.method == 'POST':
        try:
            product = Product(
                sku=request.form.get('sku', '').strip(),
                name=request.form.get('name', '').strip(),
                barcode=request.form.get('barcode', '').strip() or None,
                specification=request.form.get('specification', '').strip(),
                category=request.form.get('category', '').strip(),
                unit=request.form.get('unit', '个').strip(),
                is_active=request.form.get('is_active') == '1',
                cost_price=request.form.get('cost_price', 0),
                selling_price=request.form.get('selling_price', 0),
                description=request.form.get('description', '').strip(),
                min_stock=request.form.get('min_stock', 0, type=int),
                dosage_form=request.form.get('dosage_form', '').strip(),
                manufacturer=request.form.get('manufacturer', '').strip(),
                approval_no=request.form.get('approval_no', '').strip()
            )

            if not product.sku or not product.name:
                flash('商品编码和名称不能为空', 'danger')
                return render_template('products/form.html', product=product)
            
            # 检查条形码唯一性
            if product.barcode:
                existing = Product.query.filter_by(barcode=product.barcode).first()
                if existing:
                    flash(f'条形码 "{product.barcode}" 已被商品 "{existing.name}" 使用', 'danger')
                    return render_template('products/form.html', product=product)

            db.session.add(product)
            db.session.flush()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='create', module='product', description=f'创建商品: {product.name}({product.sku})')
            db.session.commit()
            flash('商品创建成功', 'success')
            return redirect(url_for('products.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败: {str(e)}', 'danger')

    return render_template('products/form.html', product=None)


@products_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """编辑商品"""
    product = Product.query.get_or_404(id)

    if request.method == 'POST':
        try:
            # 检查条形码唯一性（排除自己）
            new_barcode = request.form.get('barcode', '').strip() or None
            if new_barcode and new_barcode != product.barcode:
                existing = Product.query.filter_by(barcode=new_barcode).first()
                if existing and existing.id != id:
                    flash(f'条形码 "{new_barcode}" 已被商品 "{existing.name}" 使用', 'danger')
                    return render_template('products/form.html', product=product)

            product.sku = request.form.get('sku', '').strip()
            product.name = request.form.get('name', '').strip()
            product.barcode = new_barcode
            product.specification = request.form.get('specification', '').strip()
            product.category = request.form.get('category', '').strip()
            product.unit = request.form.get('unit', '个').strip()
            product.is_active = request.form.get('is_active') == '1'
            product.cost_price = request.form.get('cost_price', 0)
            product.selling_price = request.form.get('selling_price', 0)
            product.description = request.form.get('description', '').strip()
            product.min_stock = request.form.get('min_stock', 0, type=int)
            product.dosage_form = request.form.get('dosage_form', '').strip()
            product.manufacturer = request.form.get('manufacturer', '').strip()
            product.approval_no = request.form.get('approval_no', '').strip()

            if not product.sku or not product.name:
                flash('商品编码和名称不能为空', 'danger')
                return render_template('products/form.html', product=product)

            db.session.commit()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='update', module='product', description=f'编辑商品: {product.name}({product.sku})')
            flash('商品更新成功', 'success')
            return redirect(url_for('products.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败: {str(e)}', 'danger')

    return render_template('products/form.html', product=product)


@products_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """删除商品"""
    product = Product.query.get_or_404(id)
    try:
        # 检查是否有关联的库存记录
        inventory_count = Inventory.query.filter_by(product_id=id).count()
        if inventory_count > 0:
            flash(f'该商品存在 {inventory_count} 条库存记录，无法删除。请先清理相关库存。', 'danger')
            return redirect(url_for('products.list'))

        # 检查是否有关联的出入库记录
        tx_count = StockTransaction.query.filter_by(product_id=id).count()
        if tx_count > 0:
            flash(f'该商品存在 {tx_count} 条出入库记录，无法删除。', 'danger')
            return redirect(url_for('products.list'))

        # 检查是否有关联的采购单明细
        po_count = PurchaseOrderItem.query.filter_by(product_id=id).count()
        if po_count > 0:
            flash(f'该商品存在 {po_count} 条采购单明细，无法删除。', 'danger')
            return redirect(url_for('products.list'))

        db.session.delete(product)
        db.session.commit()
        LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='delete', module='product', description=f'删除商品: {product.name}({product.sku})')
        flash('商品删除成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')
    return redirect(url_for('products.list'))


@products_bp.route('/<int:id>/toggle-status', methods=['POST'])
@login_required
def toggle_status(id):
    """切换商品启用/停用状态"""
    product = Product.query.get_or_404(id)
    data = request.get_json()
    is_active = data.get('is_active', True)
    
    try:
        product.is_active = is_active
        db.session.commit()
        
        action = '启用' if is_active else '停用'
        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='product',
            description=f'{action}商品: {product.name}({product.sku})'
        )
        
        return jsonify({
            'success': True,
            'message': f'商品"{product.name}"已{action}'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


@products_bp.route('/batch-toggle-status', methods=['POST'])
@login_required
def batch_toggle_status():
    """批量切换商品状态"""
    data = request.get_json()
    ids = data.get('ids', [])
    is_active = data.get('is_active', True)
    
    if not ids:
        return jsonify({'success': False, 'error': '未选择任何商品'})
    
    try:
        count = 0
        for product_id in ids:
            product = Product.query.get(product_id)
            if product:
                product.is_active = is_active
                count += 1
        
        db.session.commit()
        
        action = '启用' if is_active else '停用'
        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='product',
            description=f'批量{action}商品: {count}个'
        )
        
        return jsonify({
            'success': True,
            'message': f'已成功{action} {count} 个商品'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


@products_bp.route('/<int:id>/clear-inventory', methods=['POST'])
@login_required
def clear_inventory(id):
    """一键清零商品库存"""
    from services.inventory_service import InventoryService
    
    product = Product.query.get_or_404(id)
    
    try:
        inventories = Inventory.query.filter_by(product_id=id).all()
        if not inventories:
            return jsonify({'success': False, 'error': '该商品没有库存记录'})
        
        cleared_count = 0
        for inv in inventories:
            if inv.quantity > 0:
                InventoryService.adjust(
                    product_id=id,
                    warehouse_id=inv.warehouse_id,
                    new_quantity=0,
                    operator=session.get('username', 'system'),
                    remark=f'清零库存 - {product.name}'
                )
                cleared_count += 1
        
        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='库存',
            description=f'清零商品库存: {product.name}({product.sku})，涉及{cleared_count}个仓库'
        )
        
        return jsonify({'success': True, 'message': f'已成功清零 {cleared_count} 个仓库的库存'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@products_bp.route('/<int:id>/force-delete', methods=['POST'])
@login_required
def force_delete(id):
    """强制删除商品（同时清理所有关联数据）"""
    
    product = Product.query.get_or_404(id)
    
    try:
        inv_count = Inventory.query.filter_by(product_id=id).count()
        tx_count = StockTransaction.query.filter_by(product_id=id).count()
        po_count = PurchaseOrderItem.query.filter_by(product_id=id).count()
        
        # 1. 删除库存记录
        if inv_count > 0:
            Inventory.query.filter_by(product_id=id).delete()
        
        # 2. 删除出入库记录
        if tx_count > 0:
            StockTransaction.query.filter_by(product_id=id).delete()
        
        # 3. 删除采购单明细（如果采购单没有其他明细了，也一并删除采购单）
        if po_count > 0:
            # 找出受影响的采购单
            affected_po_ids = db.session.query(
                PurchaseOrderItem.purchase_order_id
            ).filter_by(product_id=id).distinct().all()
            PurchaseOrderItem.query.filter_by(product_id=id).delete()
            
            # 删除没有明细的空采购单
            for (po_id,) in affected_po_ids:
                remaining = PurchaseOrderItem.query.filter_by(purchase_order_id=po_id).count()
                if remaining == 0:
                    PurchaseOrder.query.filter_by(id=po_id).delete()
        
        # 4. 删除商品
        db.session.delete(product)
        db.session.commit()
        
        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='delete',
            module='product',
            description=f'强制删除商品: {product.name}({product.sku})，清理库存{inv_count}条、出入库{tx_count}条、采购明细{po_count}条'
        )
        
        return jsonify({
            'success': True,
            'message': f'已删除商品"{product.name}"，同时清理了库存记录{inv_count}条、出入库记录{tx_count}条、采购明细{po_count}条'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'删除失败: {str(e)}'})


@products_bp.route('/export')
@login_required
def export():
    """导出商品列表到Excel"""
    from datetime import datetime as dt
    
    products = Product.query.all()
    data = []
    for idx, p in enumerate(products, 1):
        data.append({
            'idx': idx,
            'sku': p.sku,
            'name': p.name,
            'barcode': p.barcode or '',
            'specification': p.specification or '',
            'category': p.category or '',
            'unit': p.unit,
            'is_active': '启用' if p.is_active else '停用',
            'cost_price': p.cost_price,
            'selling_price': p.selling_price,
            'min_stock': p.min_stock,
            'dosage_form': p.dosage_form or '',
            'manufacturer': p.manufacturer or '',
            'approval_no': p.approval_no or '',
            'description': p.description or '',
            'export_time': dt.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    
    headers = [
        ('idx', '序号'),
        ('sku', '商品编码'),
        ('name', '商品名称'),
        ('barcode', '条形码'),
        ('specification', '规格'),
        ('category', '分类'),
        ('unit', '单位'),
        ('dosage_form', '剂型'),
        ('manufacturer', '生产厂家'),
        ('approval_no', '批准文号'),
        ('is_active', '状态'),
        ('cost_price', '成本价'),
        ('selling_price', '售价'),
        ('min_stock', '最低库存'),
        ('description', '备注'),
        ('export_time', '导出时间')
    ]
    
    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='product',
        description='导出商品列表'
    )
    
    return export_to_excel(data, headers, '商品列表.xlsx')


@products_bp.route('/api/<int:id>')
@login_required
def api_get_product(id):
    """获取商品详情API"""
    product = Product.query.get(id)
    if not product:
        return jsonify({'success': False, 'message': '商品不存在'})

    return jsonify({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'sku': product.sku,
            'unit': product.unit,
            'cost_price': float(product.cost_price) if product.cost_price else 0,
            'selling_price': float(product.selling_price) if product.selling_price else 0,
            'specification': product.specification or '',
            'category': product.category or '',
            'is_active': product.is_active
        }
    })


@products_bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete():
    """批量删除商品"""
    ids = request.form.getlist('ids[]')
    if not ids:
        flash('请选择要删除的商品', 'warning')
        return redirect(url_for('products.list'))

    deleted = 0
    skipped = 0
    for id_str in ids:
        try:
            id = int(id_str)
            product = Product.query.get(id)
            if not product:
                continue

            # 检查关联数据
            inventory_count = Inventory.query.filter_by(product_id=id).count()
            tx_count = StockTransaction.query.filter_by(product_id=id).count()
            po_count = PurchaseOrderItem.query.filter_by(product_id=id).count()

            if inventory_count > 0 or tx_count > 0 or po_count > 0:
                skipped += 1
                continue

            db.session.delete(product)
            deleted += 1
        except Exception:
            skipped += 1

    try:
        db.session.commit()
        msg = f'成功删除 {deleted} 个商品'
        if skipped > 0:
            msg += f'，跳过 {skipped} 个（存在关联数据）'
        flash(msg, 'success')
        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='delete',
            module='product',
            description=f'批量删除商品: {deleted}个'
        )
    except Exception as e:
        db.session.rollback()
        flash(f'批量删除失败: {str(e)}', 'danger')

    return redirect(url_for('products.list'))


@products_bp.route('/api/search-by-barcode')
@login_required
def search_by_barcode():
    """通过条形码搜索商品"""
    barcode = request.args.get('barcode', '').strip()
    if not barcode:
        return jsonify({'success': False, 'error': '请输入条形码'})
    
    product = Product.query.filter_by(barcode=barcode).first()
    if not product:
        return jsonify({'success': False, 'error': '未找到该条形码对应的商品'})
    
    if not product.is_active:
        return jsonify({'success': False, 'error': f'商品"{product.name}"已停用，无法进行出入库操作'})
    
    return jsonify({
        'success': True,
        'product': {
            'id': product.id,
            'sku': product.sku,
            'name': product.name,
            'barcode': product.barcode,
            'specification': product.specification,
            'unit': product.unit,
            'cost_price': str(product.cost_price),
            'selling_price': str(product.selling_price)
        }
    })
