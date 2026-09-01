from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db
from models.supplier import Supplier
from models.purchase_order import PurchaseOrder
from services.log_service import LogService
from utils.decorators import login_required
from utils.excel_export import export_to_excel

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')


@suppliers_bp.route('/')
@login_required
def list():
    """供应商列表"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'name')
    order = request.args.get('order', 'asc')
    ALLOWED_SORT_FIELDS = {'name', 'contact_person', 'contact_phone', 'created_at'}
    if sort not in ALLOWED_SORT_FIELDS:
        sort = 'name'

    query = Supplier.query

    if search:
        query = query.filter(
            db.or_(
                Supplier.name.like(f'%{search}%'),
                Supplier.contact_person.like(f'%{search}%'),
                Supplier.phone.like(f'%{search}%')
            )
        )

    # 排序
    sort_field = getattr(Supplier, sort, Supplier.name)
    if order == 'desc':
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())

    pagination = query.paginate(page=page, per_page=15, error_out=False)

    return render_template('suppliers/list.html',
                           suppliers=pagination.items,
                           pagination=pagination,
                           search=search,
                           sort=sort,
                           order=order)


@suppliers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """新增供应商"""
    if request.method == 'POST':
        try:
            supplier = Supplier(
                name=request.form.get('name', '').strip(),
                contact_person=request.form.get('contact_person', '').strip(),
                contact_phone=request.form.get('contact_phone', '').strip(),
                email=request.form.get('email', '').strip(),
                address=request.form.get('address', '').strip(),
                description=request.form.get('description', '').strip()
            )

            if not supplier.name:
                flash('供应商名称不能为空', 'danger')
                return render_template('suppliers/form.html', supplier=supplier)

            db.session.add(supplier)
            db.session.flush()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='create', module='supplier', description=f'创建供应商: {supplier.name}')
            db.session.commit()
            flash('供应商创建成功', 'success')
            return redirect(url_for('suppliers.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败: {str(e)}', 'danger')

    return render_template('suppliers/form.html', supplier=None)


@suppliers_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """编辑供应商"""
    supplier = Supplier.query.get_or_404(id)

    if request.method == 'POST':
        try:
            supplier.name = request.form.get('name', '').strip()
            supplier.contact_person = request.form.get('contact_person', '').strip()
            supplier.contact_phone = request.form.get('contact_phone', '').strip()
            supplier.email = request.form.get('email', '').strip()
            supplier.address = request.form.get('address', '').strip()
            supplier.description = request.form.get('description', '').strip()

            if not supplier.name:
                flash('供应商名称不能为空', 'danger')
                return render_template('suppliers/form.html', supplier=supplier)

            db.session.commit()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='update', module='supplier', description=f'编辑供应商: {supplier.name}')
            flash('供应商更新成功', 'success')
            return redirect(url_for('suppliers.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败: {str(e)}', 'danger')

    return render_template('suppliers/form.html', supplier=supplier)


@suppliers_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """删除供应商"""
    supplier = Supplier.query.get_or_404(id)
    try:
        # 保存删除前的数据，用于撤销
        before_data = {
            'id': supplier.id,
            'name': supplier.name,
            'contact': supplier.contact,
            'phone': supplier.phone,
            'address': supplier.address,
            'email': supplier.email,
            'is_active': supplier.is_active
        }
        
        # 检查是否有关联的采购单
        po_count = PurchaseOrder.query.filter_by(supplier_id=id).count()
        if po_count > 0:
            flash(f'该供应商存在 {po_count} 条采购单记录，无法删除。', 'danger')
            return redirect(url_for('suppliers.list'))

        db.session.delete(supplier)
        db.session.commit()
        LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='delete', module='supplier', description=f'删除供应商: {supplier.name}', reference_id=id, before_data=before_data)
        flash('供应商删除成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')
    return redirect(url_for('suppliers.list'))


@suppliers_bp.route('/export')
@login_required
def export():
    """导出供应商列表到Excel"""
    from datetime import datetime as dt
    
    suppliers = Supplier.query.order_by(Supplier.created_at.desc()).all()
    data = []
    for idx, s in enumerate(suppliers, 1):
        data.append({
            'idx': idx,
            'name': s.name,
            'contact_person': s.contact_person or '',
            'contact_phone': s.contact_phone or '',
            'email': s.email or '',
            'address': s.address or '',
            'description': s.description or '',
            'created_at': s.created_at.strftime('%Y-%m-%d %H:%M') if s.created_at else '',
            'export_time': dt.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    headers = [
        ('idx', '序号'),
        ('name', '供应商名称'),
        ('contact_person', '联系人'),
        ('contact_phone', '联系电话'),
        ('email', '邮箱'),
        ('address', '地址'),
        ('description', '备注'),
        ('created_at', '创建时间'),
        ('export_time', '导出时间')
    ]

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='supplier',
        description='导出供应商列表'
    )
    
    return export_to_excel(data, headers, '供应商列表.xlsx')
