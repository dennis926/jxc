"""
用户管理路由
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db
from models.user import User, validate_password_strength
from services.log_service import LogService
from utils.decorators import login_required, admin_required
from utils.excel_export import export_to_excel
from datetime import datetime

users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.route('/')
@admin_required
def list():
    """用户列表（分页、搜索）"""
    from models.role import Role

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role_id', '').strip()
    roles = Role.query.filter_by(is_active=True).all()

    query = User.query

    # 搜索过滤（按用户名或真实姓名）
    if search:
        query = query.filter(
            db.or_(
                User.username.like(f'%{search}%'),
                User.real_name.like(f'%{search}%')
            )
        )

    # 角色筛选
    if role_filter:
        query = query.filter(User.role_id == int(role_filter))

    # 按创建时间倒序
    query = query.order_by(User.created_at.desc())

    # 分页
    pagination = query.paginate(page=page, per_page=15, error_out=False)

    return render_template('users/list.html',
                           users=pagination.items,
                           pagination=pagination,
                           search=search,
                           role_filter=role_filter,
                           roles=roles)


@users_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create():
    """新增用户"""
    from models.role import Role
    roles = Role.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            real_name = request.form.get('real_name', '').strip()
            role = request.form.get('role', 'user').strip()
            role_id = request.form.get('role_id', type=int)
            phone = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip()

            if not username:
                flash('用户名不能为空', 'danger')
                return render_template('users/form.html', user=None, roles=roles)

            if not password:
                flash('密码不能为空', 'danger')
                return render_template('users/form.html', user=None, roles=roles)
            
            # 验证密码强度
            is_valid, error_msg = validate_password_strength(password)
            if not is_valid:
                flash(error_msg, 'danger')
                return render_template('users/form.html', user=None)

            # 检查用户名是否已存在
            existing = User.query.filter_by(username=username).first()
            if existing:
                flash('用户名已存在', 'danger')
                return render_template('users/form.html', user=None, roles=roles)

            user = User(
                username=username,
                real_name=real_name,
                role=role,
                role_id=role_id,
                phone=phone,
                email=email,
                force_change_password=True  # 新用户首次登录需修改密码
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='create', module='user', description=f'创建用户: {user.username}')
            flash('用户创建成功，该用户首次登录需修改密码', 'success')
            return redirect(url_for('users.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'创建失败: {str(e)}', 'danger')

    return render_template('users/form.html', user=None, roles=roles)


@users_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit(id):
    """编辑用户"""
    from models.role import Role
    user = User.query.get_or_404(id)
    roles = Role.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        try:
            user.real_name = request.form.get('real_name', '').strip()
            user.role = request.form.get('role', 'user').strip()
            user.role_id = request.form.get('role_id', type=int)
            user.phone = request.form.get('phone', '').strip()
            user.email = request.form.get('email', '').strip()

            # 如果填写了新密码则更新
            new_password = request.form.get('password', '').strip()
            if new_password:
                # 验证密码强度
                is_valid, error_msg = validate_password_strength(new_password)
                if not is_valid:
                    flash(error_msg, 'danger')
                    return render_template('users/form.html', user=user, roles=roles)
                user.set_password(new_password)
                user.password_changed_at = datetime.now()
                user.force_change_password = False

            # 状态切换
            is_active = request.form.get('is_active')
            user.is_active = bool(is_active)

            db.session.commit()
            LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='update', module='user', description=f'编辑用户: {user.username}')
            flash('用户更新成功', 'success')
            return redirect(url_for('users.list'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败: {str(e)}', 'danger')

    return render_template('users/form.html', user=user, roles=roles)


@users_bp.route('/delete/<int:id>', methods=['POST'])
@admin_required
def delete(id):
    """删除用户"""
    user = User.query.get_or_404(id)

    # 不允许删除admin用户
    if user.username == 'admin':
        flash('不能删除默认管理员账号', 'danger')
        return redirect(url_for('users.list'))

    # 不允许删除自己
    if user.id == session.get('user_id'):
        flash('不能删除当前登录账号', 'danger')
        return redirect(url_for('users.list'))

    try:
        # 保存删除前的数据，用于撤销
        before_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.full_name,
            'role_id': user.role_id,
            'is_active': user.is_active
        }
        
        db.session.delete(user)
        db.session.commit()
        LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='delete', module='user', description=f'删除用户: {user.username}', reference_id=id, before_data=before_data)
        flash('用户删除成功', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'删除失败: {str(e)}', 'danger')
    return redirect(url_for('users.list'))


@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """个人资料页面"""
    # 从session获取当前用户ID
    current_user_id = session.get('user_id')
    current_user = User.query.get_or_404(current_user_id)

    if request.method == 'POST':
        try:
            # 记录操作前的数据
            before_data = {
                'real_name': current_user.real_name,
                'phone': current_user.phone,
                'email': current_user.email
            }
            
            current_user.real_name = request.form.get('real_name', '').strip()
            current_user.phone = request.form.get('phone', '').strip()
            current_user.email = request.form.get('email', '').strip()

            db.session.commit()
            
            # 记录日志
            after_data = {
                'real_name': current_user.real_name,
                'phone': current_user.phone,
                'email': current_user.email
            }
            LogService.log_operation(
                user_id=session.get('user_id'),
                username=session.get('username'),
                operation_type='update',
                module='user',
                description=f'更新个人资料: {current_user.username}',
                before_data=before_data,
                after_data=after_data
            )
            
            # 更新session中的real_name
            session['real_name'] = current_user.real_name or current_user.username
            flash('个人资料更新成功', 'success')
            return redirect(url_for('users.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'更新失败: {str(e)}', 'danger')

    return render_template('users/profile.html', user=current_user)


@users_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """修改密码页面"""
    # 从session获取当前用户ID
    current_user_id = session.get('user_id')
    current_user = User.query.get_or_404(current_user_id)

    if request.method == 'POST':
        old_password = request.form.get('old_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not old_password or not new_password or not confirm_password:
            flash('请填写所有密码字段', 'danger')
            return render_template('users/change_password.html')

        if not current_user.check_password(old_password):
            flash('原密码不正确', 'danger')
            return render_template('users/change_password.html')

        # 验证密码强度
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            flash(error_msg, 'danger')
            return render_template('users/change_password.html')

        if new_password != confirm_password:
            flash('两次输入的新密码不一致', 'danger')
            return render_template('users/change_password.html')

        try:
            current_user.set_password(new_password)
            current_user.password_changed_at = datetime.now()
            current_user.force_change_password = False  # 清除强制修改标记
            db.session.commit()
            
            # 记录日志
            LogService.log_operation(
                user_id=session.get('user_id'),
                username=session.get('username'),
                operation_type='update',
                module='认证',
                description=f'修改密码: {current_user.username}'
            )
            
            flash('密码修改成功', 'success')
            return redirect(url_for('users.change_password'))
        except Exception as e:
            db.session.rollback()
            flash(f'修改失败: {str(e)}', 'danger')

    return render_template('users/change_password.html')


@users_bp.route('/export')
@admin_required
def export():
    """导出用户列表到Excel"""
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role_id', '').strip()

    query = User.query

    # 搜索过滤
    if search:
        query = query.filter(
            db.or_(
                User.username.like(f'%{search}%'),
                User.real_name.like(f'%{search}%')
            )
        )

    # 角色筛选
    if role_filter:
        query = query.filter(User.role_id == int(role_filter))

    users = query.order_by(User.created_at.desc()).all()

    data = []
    for user in users:
        data.append({
            'username': user.username,
            'real_name': user.real_name or '',
            'role': user.user_role.name if user.user_role else '未分配',
            'phone': user.phone or '',
            'email': user.email or '',
            'is_active': '启用' if user.is_active else '停用',
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else ''
        })

    headers = [
        ('username', '用户名'),
        ('real_name', '真实姓名'),
        ('role', '角色'),
        ('phone', '电话'),
        ('email', '邮箱'),
        ('is_active', '状态'),
        ('created_at', '创建时间')
    ]

    return export_to_excel(data, headers, '用户列表.xlsx')
