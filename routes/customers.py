from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from models import db
from models.customer import Customer
from utils.decorators import login_required
from services.log_service import LogService
from sqlalchemy import or_

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')

@customers_bp.route('/')
@login_required
def list():
    """客户列表"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Customer.query

    if search:
        query = query.filter(
            or_(
                Customer.name.like(f'%{search}%'),
                Customer.contact.like(f'%{search}%'),
                Customer.phone.like(f'%{search}%'),
                Customer.address.like(f'%{search}%')
            )
        )

    pagination = query.order_by(Customer.created_at.desc()).paginate(page=page, per_page=15, error_out=False)

    return render_template('customers/list.html',
                           customers=pagination.items,
                           pagination=pagination,
                           search=search)


@customers_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """添加客户"""
    if request.method == 'POST':
        try:
            name = request.form.get('name', '').strip()
            contact = request.form.get('contact', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            email = request.form.get('email', '').strip()
            tax_no = request.form.get('tax_no', '').strip()
            bank = request.form.get('bank', '').strip()
            account_no = request.form.get('account_no', '').strip()
            remark = request.form.get('remark', '').strip()

            if not name:
                return jsonify({'success': False, 'message': '客户名称不能为空'})

            customer = Customer(
                name=name,
                contact=contact,
                phone=phone,
                address=address,
                email=email,
                tax_no=tax_no,
                bank=bank,
                account_no=account_no,
                remark=remark
            )

            db.session.add(customer)
            # 先flush获取ID，再记录日志
            db.session.flush()
            
            LogService.log_operation(
                user_id=session.get('user_id'),
                username=session.get('username'),
                operation_type='create',
                module='customer',
                description=f'添加客户: {name}'
            )
            
            db.session.commit()

            return jsonify({'success': True, 'message': '添加成功'})
        except Exception as e:
            db.session.rollback()
            error_msg = str(e)
            return jsonify({'success': False, 'message': f'添加失败: {error_msg}'})

    return render_template('customers/add.html')


@customers_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """编辑客户"""
    customer = Customer.query.get_or_404(id)

    if request.method == 'POST':
        customer.name = request.form.get('name', '').strip()
        customer.contact = request.form.get('contact', '').strip()
        customer.phone = request.form.get('phone', '').strip()
        customer.address = request.form.get('address', '').strip()
        customer.email = request.form.get('email', '').strip()
        customer.tax_no = request.form.get('tax_no', '').strip()
        customer.bank = request.form.get('bank', '').strip()
        customer.account_no = request.form.get('account_no', '').strip()
        customer.remark = request.form.get('remark', '').strip()

        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='customer',
            description=f'编辑客户: {customer.name}'
        )

        return jsonify({'success': True, 'message': '更新成功'})

    return render_template('customers/edit.html', customer=customer)


@customers_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """删除客户"""
    customer = Customer.query.get_or_404(id)
    
    # 保存删除前的数据，用于撤销
    before_data = {
        'id': customer.id,
        'name': customer.name,
        'contact': customer.contact,
        'phone': customer.phone,
        'address': customer.address,
        'email': customer.email,
        'is_active': customer.is_active
    }

    customer.is_active = False
    db.session.commit()

    LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='delete',
            module='customer',
            description=f'删除客户: {customer.name}',
            reference_id=id,
            before_data=before_data
        )

    return jsonify({'success': True, 'message': '删除成功'})


@customers_bp.route('/search')
@login_required
def search():
    """搜索客户（API）"""
    keyword = request.args.get('keyword', '').strip()
    if keyword:
        customers = Customer.query.filter(
            Customer.is_active == True,
            or_(
                Customer.name.like(f'%{keyword}%'),
                Customer.contact.like(f'%{keyword}%'),
                Customer.phone.like(f'%{keyword}%'),
                Customer.address.like(f'%{keyword}%')
            )
        ).limit(20).all()
    else:
        customers = Customer.query.filter_by(is_active=True).limit(20).all()

    return jsonify({
        'success': True,
        'customers': [{
            'id': c.id,
            'name': c.name,
            'contact': c.contact or '',
            'phone': c.phone or '',
            'address': c.address or ''
        } for c in customers]
    })
