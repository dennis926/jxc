from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db
from models.warehouse import Warehouse
from models.inventory import Inventory
from models.stock_transaction import StockTransaction
from services.log_service import LogService
from utils.decorators import login_required
from utils.excel_export import export_to_excel

warehouses_bp = Blueprint('warehouses', __name__, url_prefix='/warehouses')


@warehouses_bp.route('/')
@login_required
def list():
    """仓库列表"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'name')
    order = request.args.get('order', 'asc')
    ALLOWED_SORT_FIELDS = {'name', 'address', 'created_at'}
    if sort not in ALLOWED_SORT_FIELDS:
        sort = 'name'

    query = Warehouse.query

    if search:
        query = query.filter(
            db.or_(
                Warehouse.name.like(f'%{search}%'),
                Warehouse.code.like(f'%{search}%')
            )
        )

    # 排序
    sort_field = getattr(Warehouse, sort, Warehouse.name)
    if order == 'desc':
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())

    pagination = query.paginate(page=page, per_page=15, error_out=False)

    return render_template('warehouses/list.html',
                           warehouses=pagination.items,
                           pagination=pagination,
                           search=search,
                           sort=sort,
                           order=order)


@warehouses_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """新增仓库"""
    if request.method == 'POST':
        try:
            warehouse = Warehouse(
                name=request.form.get('name', '').strip(),
                code=request.form.get('code', '').strip(),
                address=request.form.get('address', '').strip(),
                contact_person=request.form.get('contact_person', '').strip(),
                contact_phone=request.form.get('contact_phone', '').strip(),
                is_active=True
            )

            if not warehouse.name or not warehouse.code:
                flash('仓库名称和编码不能为空', 'danger')
                return render_template('warehouses/form.html', warehouse=warehouse)

            db.session.add(warehouse)
            db.session.commit()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='create', module='warehouse', description=f'创建仓库: {warehouse.name}({warehouse.code})')
            flash('仓库创建成功', 'success')
            return redirect(url_for('warehouses.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败: {str(e)}', 'danger')

    return render_template('warehouses/form.html', warehouse=None)


@warehouses_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """编辑仓库"""
    warehouse = Warehouse.query.get_or_404(id)

    if request.method == 'POST':
        try:
            warehouse.name = request.form.get('name', '').strip()
            warehouse.code = request.form.get('code', '').strip()
            warehouse.address = request.form.get('address', '').strip()
            warehouse.contact_person = request.form.get('contact_person', '').strip()
            warehouse.contact_phone = request.form.get('contact_phone', '').strip()
            warehouse.is_active = 'is_active' in request.form

            if not warehouse.name or not warehouse.code:
                flash('仓库名称和编码不能为空', 'danger')
                return render_template('warehouses/form.html', warehouse=warehouse)

            db.session.commit()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='update', module='warehouse', description=f'编辑仓库: {warehouse.name}({warehouse.code})')
            flash('仓库更新成功', 'success')
            return redirect(url_for('warehouses.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败: {str(e)}', 'danger')

    return render_template('warehouses/form.html', warehouse=warehouse)


@warehouses_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """删除仓库"""
    warehouse = Warehouse.query.get_or_404(id)
    try:
        # 保存删除前的数据，用于撤销
        before_data = {
            'id': warehouse.id,
            'name': warehouse.name,
            'code': warehouse.code,
            'address': warehouse.address,
            'contact': warehouse.contact,
            'phone': warehouse.phone,
            'is_active': warehouse.is_active
        }
        
        # 检查是否有关联的库存记录
        inventory_count = Inventory.query.filter_by(warehouse_id=id).count()
        if inventory_count > 0:
            flash(f'该仓库存在 {inventory_count} 条库存记录，无法删除。请先清理相关库存。', 'danger')
            return redirect(url_for('warehouses.list'))

        # 检查是否有关联的出入库记录
        tx_count = StockTransaction.query.filter_by(warehouse_id=id).count()
        if tx_count > 0:
            flash(f'该仓库存在 {tx_count} 条出入库记录，无法删除。', 'danger')
            return redirect(url_for('warehouses.list'))

        db.session.delete(warehouse)
        db.session.commit()
        LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='delete', module='warehouse', description=f'删除仓库: {warehouse.name}({warehouse.code})', reference_id=id, before_data=before_data)
        flash('仓库删除成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')
    return redirect(url_for('warehouses.list'))


@warehouses_bp.route('/export')
@login_required
def export():
    """导出仓库列表到Excel"""
    warehouses = Warehouse.query.order_by(Warehouse.created_at.desc()).all()
    data = []
    for w in warehouses:
        data.append({
            'name': w.name,
            'code': w.code,
            'address': w.address or '',
            'contact_person': w.contact_person or '',
            'contact_phone': w.contact_phone or '',
            'is_active': '启用' if w.is_active else '停用',
            'created_at': w.created_at.strftime('%Y-%m-%d %H:%M') if w.created_at else ''
        })

    headers = [
        ('name', '仓库名称'),
        ('code', '仓库编码'),
        ('address', '地址'),
        ('contact_person', '联系人'),
        ('contact_phone', '联系电话'),
        ('is_active', '状态'),
        ('created_at', '创建时间')
    ]

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='warehouse',
        description='导出仓库列表'
    )
    
    return export_to_excel(data, headers, '仓库列表.xlsx')
