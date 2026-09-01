from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from models import db
from models.product_batch import ProductBatch
from models.batch_code import BatchCode
from models.product import Product
from models.warehouse import Warehouse
from models.supplier import Supplier
from models.inventory import Inventory
from models.stock_transaction import StockTransaction
from utils.decorators import login_required
from services.log_service import LogService
from datetime import datetime
from decimal import Decimal

batches_bp = Blueprint('batches', __name__, url_prefix='/batches')


@batches_bp.route('/')
@login_required
def list():
    """批次列表"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    product_id = request.args.get('product_id', 0, type=int)
    status = request.args.get('status', '').strip()

    query = ProductBatch.query

    if search:
        query = query.filter(
            db.or_(
                ProductBatch.batch_no.like(f'%{search}%'),
                ProductBatch.product.has(Product.name.like(f'%{search}%'))
            )
        )

    if warehouse_id:
        query = query.filter(ProductBatch.warehouse_id == warehouse_id)

    if product_id:
        query = query.filter(ProductBatch.product_id == product_id)

    if status:
        query = query.filter(ProductBatch.status == status)

    pagination = query.order_by(ProductBatch.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    warehouses = Warehouse.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).all()

    return render_template('batches/list.html',
                           batches=pagination.items,
                           pagination=pagination,
                           search=search,
                           warehouse_id=warehouse_id,
                           product_id=product_id,
                           status=status,
                           warehouses=warehouses,
                           products=products)


@batches_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """添加批次"""
    if request.method == 'POST':
        product_id = request.form.get('product_id', type=int)
        warehouse_id = request.form.get('warehouse_id', type=int)
        supplier_id = request.form.get('supplier_id', type=int) or None
        code_start = request.form.get('code_start', '').strip()
        code_end = request.form.get('code_end', '').strip()
        cost_price = request.form.get('cost_price', '').strip()
        production_date = request.form.get('production_date', '').strip()
        expire_date = request.form.get('expire_date', '').strip()
        remark = request.form.get('remark', '').strip()

        if not all([product_id, warehouse_id, code_start, code_end]):
            return jsonify({'success': False, 'message': '请填写必填项'})

        try:
            code_start = int(code_start)
            code_end = int(code_end)
            if code_end < code_start:
                return jsonify({'success': False, 'message': '结束码必须大于起始码'})
            total_quantity = code_end - code_start + 1
        except ValueError:
            return jsonify({'success': False, 'message': '码段必须是数字'})

        try:
            cost_price = Decimal(cost_price) if cost_price else Decimal('0')
        except:
            cost_price = Decimal('0')

        product = Product.query.get(product_id)
        if not product:
            return jsonify({'success': False, 'message': '商品不存在'})

        batch = ProductBatch(
            batch_no=ProductBatch.generate_batch_no(),
            product_id=product_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
            code_start=code_start,
            code_end=code_end,
            total_quantity=total_quantity,
            remaining_quantity=total_quantity,
            cost_price=cost_price,
            production_date=datetime.strptime(production_date, '%Y-%m-%d').date() if production_date else None,
            expire_date=datetime.strptime(expire_date, '%Y-%m-%d').date() if expire_date else None,
            remark=remark,
            operator=session.get('real_name', session.get('username', 'admin')),
            status='active'
        )

        db.session.add(batch)
        db.session.flush()

        for i in range(code_start, code_end + 1):
            batch_code = BatchCode(
                batch_id=batch.id,
                code=str(i),
                status='in_stock'
            )
            db.session.add(batch_code)

        inventory = Inventory.query.filter_by(
            product_id=product_id,
            warehouse_id=warehouse_id
        ).first()

        if not inventory:
            inventory = Inventory(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=total_quantity
            )
            db.session.add(inventory)
        else:
            inventory.quantity += total_quantity

        transaction = StockTransaction(
            transaction_no=f'IN{datetime.now().strftime("%Y%m%d%H%M%S")}{i}',
            type='stock_in',
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=total_quantity,
            unit_cost=cost_price,
            reference_no=batch.batch_no,
            remark=f'批次入库：{batch.batch_no}，码段：{code_start}-{code_end}',
            operator=session.get('username', 'admin')
        )
        db.session.add(transaction)

        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='create',
            module='product_batch',
            description=f'添加批次: {batch.batch_no}，码段：{code_start}-{code_end}'
        )

        return jsonify({'success': True, 'message': '批次添加成功'})

    warehouses = Warehouse.query.filter_by(is_active=True).all()
    products = Product.query.filter_by(is_active=True).all()
    suppliers = Supplier.query.filter_by(is_active=True).all()

    return render_template('batches/add.html',
                           warehouses=warehouses,
                           products=products,
                           suppliers=suppliers)


@batches_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """编辑批次"""
    batch = ProductBatch.query.get_or_404(id)

    if request.method == 'POST':
        remark = request.form.get('remark', '').strip()
        production_date = request.form.get('production_date', '').strip()
        expire_date = request.form.get('expire_date', '').strip()

        batch.remark = remark
        batch.production_date = datetime.strptime(production_date, '%Y-%m-%d').date() if production_date else None
        batch.expire_date = datetime.strptime(expire_date, '%Y-%m-%d').date() if expire_date else None

        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='product_batch',
            description=f'编辑批次: {batch.batch_no}'
        )

        return jsonify({'success': True, 'message': '更新成功'})

    return render_template('batches/edit.html', batch=batch)


@batches_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """删除批次"""
    batch = ProductBatch.query.get_or_404(id)

    if batch.remaining_quantity < batch.total_quantity:
        return jsonify({'success': False, 'message': '该批次已有出库记录，无法删除'})

    BatchCode.query.filter_by(batch_id=batch.id).delete()

    inventory = Inventory.query.filter_by(
        product_id=batch.product_id,
        warehouse_id=batch.warehouse_id
    ).first()

    if inventory:
        inventory.quantity -= batch.total_quantity

    StockTransaction.query.filter_by(reference_no=batch.batch_no).delete()

    db.session.delete(batch)
    db.session.commit()

    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='delete',
        module='product_batch',
        description=f'删除批次: {batch.batch_no}'
    )

    return jsonify({'success': True, 'message': '删除成功'})


@batches_bp.route('/codes/<int:id>')
@login_required
def codes(id):
    """查看批次码明细"""
    batch = ProductBatch.query.get_or_404(id)
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '').strip()

    query = BatchCode.query.filter_by(batch_id=id)

    if status:
        query = query.filter(BatchCode.status == status)

    pagination = query.order_by(BatchCode.code.asc()).paginate(
        page=page, per_page=50, error_out=False
    )

    return render_template('batches/codes.html',
                           batch=batch,
                           codes=pagination.items,
                           pagination=pagination,
                           status=status)


@batches_bp.route('/query-codes')
@login_required
def query_codes():
    """查询可用码段（用于出库选择）"""
    product_id = request.args.get('product_id', type=int)
    warehouse_id = request.args.get('warehouse_id', type=int)
    quantity = request.args.get('quantity', type=int, default=0)

    if not product_id:
        return jsonify({'success': False, 'message': '请选择商品'})

    # 查询该商品的所有有效批次
    batches = ProductBatch.query.filter(
        ProductBatch.product_id == product_id,
        ProductBatch.status.in_(['active', 'partial']),
        ProductBatch.remaining_quantity > 0
    ).all()

    # 如果指定了仓库，筛选该仓库的批次
    if warehouse_id:
        batches = [b for b in batches if b.warehouse_id == warehouse_id]

    codes_data = []
    total_available = 0

    for batch in batches:
        # 查询该批次所有可用码（按码值排序）
        available_codes = BatchCode.query.filter_by(
            batch_id=batch.id,
            status='in_stock'
        ).order_by(BatchCode.code.asc()).all()

        total_available += len(available_codes)

        for code in available_codes:
            codes_data.append({
                'id': code.id,
                'code': code.code,
                'batch_id': batch.id,
                'batch_no': batch.batch_no,
                'warehouse_name': batch.warehouse.name if batch.warehouse else ''
            })

    return jsonify({
        'success': True,
        'codes': codes_data,
        'total_available': total_available,
        'requested_quantity': quantity
    })


@batches_bp.route('/select-codes')
@login_required
def select_codes():
    """选择码段页面（出库时调用）"""
    product_id = request.args.get('product_id', type=int)
    warehouse_id = request.args.get('warehouse_id', 0, type=int)
    quantity = request.args.get('quantity', 0, type=int)

    batches = ProductBatch.query.filter(
        ProductBatch.product_id == product_id,
        ProductBatch.status == 'active',
        ProductBatch.remaining_quantity > 0
    ).all()

    if warehouse_id:
        batches = [b for b in batches if b.warehouse_id == warehouse_id]

    return render_template('batches/select_codes.html',
                           batches=batches,
                           product_id=product_id,
                           warehouse_id=warehouse_id,
                           quantity=quantity)
