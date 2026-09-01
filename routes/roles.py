"""
角色管理路由模块
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from models import db
from models.role import Role, PERMISSION_MODULES, get_all_permissions, get_default_permissions, get_operator_default_permissions
from models.user import User
from services.log_service import LogService
from utils.decorators import admin_required

roles_bp = Blueprint('roles', __name__, url_prefix='/roles')


@roles_bp.route('/')
@admin_required
def list():
    """角色列表"""
    roles = Role.query.order_by(Role.is_system.desc(), Role.created_at.asc()).all()
    return render_template('roles/list.html', roles=roles, permission_modules=PERMISSION_MODULES)


@roles_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create():
    """创建角色"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        is_active = request.form.get('is_active') == 'on'
        permissions = request.form.getlist('permissions')

        # 验证
        if not name:
            flash('角色名称不能为空', 'danger')
            return render_template('roles/form.html',
                                   permission_modules=PERMISSION_MODULES,
                                   selected_permissions=permissions)

        # 检查名称唯一性
        existing = Role.query.filter_by(name=name).first()
        if existing:
            flash('角色名称已存在', 'danger')
            return render_template('roles/form.html',
                                   permission_modules=PERMISSION_MODULES,
                                   selected_permissions=permissions)

        # 创建角色
        role = Role(
            name=name,
            description=description,
            is_active=is_active,
            is_system=False
        )
        role.set_permissions_list(permissions)
        db.session.add(role)
        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='create',
            module='role',
            description=f'创建角色: {name}'
        )

        flash('角色创建成功', 'success')
        return redirect(url_for('roles.list'))

    return render_template('roles/form.html',
                           permission_modules=PERMISSION_MODULES,
                           selected_permissions=[])


@roles_bp.route('/edit/<int:role_id>', methods=['GET', 'POST'])
@admin_required
def edit(role_id):
    """编辑角色"""
    role = Role.query.get_or_404(role_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        is_active = request.form.get('is_active') == 'on'
        permissions = request.form.getlist('permissions')

        # 验证
        if not name:
            flash('角色名称不能为空', 'danger')
            return render_template('roles/form.html',
                                   role=role,
                                   permission_modules=PERMISSION_MODULES,
                                   selected_permissions=permissions)

        # 检查名称唯一性（排除自身）
        existing = Role.query.filter(Role.name == name, Role.id != role_id).first()
        if existing:
            flash('角色名称已存在', 'danger')
            return render_template('roles/form.html',
                                   role=role,
                                   permission_modules=PERMISSION_MODULES,
                                   selected_permissions=permissions)

        # 更新角色
        role.name = name
        role.description = description
        role.is_active = is_active
        role.set_permissions_list(permissions)
        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='role',
            description=f'编辑角色: {name}'
        )

        flash('角色更新成功', 'success')
        return redirect(url_for('roles.list'))

    selected_permissions = role.get_permissions_list()
    return render_template('roles/form.html',
                           role=role,
                           permission_modules=PERMISSION_MODULES,
                           selected_permissions=selected_permissions)


@roles_bp.route('/delete/<int:role_id>', methods=['POST'])
@admin_required
def delete(role_id):
    """删除角色"""
    role = Role.query.get_or_404(role_id)

    if role.is_system:
        flash('系统内置角色不能删除', 'danger')
        return redirect(url_for('roles.list'))

    # 检查是否有用户使用该角色
    user_count = User.query.filter_by(role_id=role_id).count()
    if user_count > 0:
        flash(f'该角色下有 {user_count} 个用户，请先更换这些用户的角色', 'danger')
        return redirect(url_for('roles.list'))

    role_name = role.name
    db.session.delete(role)
    db.session.commit()

    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='delete',
        module='role',
        description=f'删除角色: {role_name}'
    )

    flash('角色删除成功', 'success')
    return redirect(url_for('roles.list'))


@roles_bp.route('/toggle/<int:role_id>', methods=['POST'])
@admin_required
def toggle(role_id):
    """启用/禁用角色"""
    role = Role.query.get_or_404(role_id)

    if role.is_system:
        return jsonify({'success': False, 'message': '系统内置角色不能禁用'})

    role.is_active = not role.is_active
    db.session.commit()

    status = '启用' if role.is_active else '禁用'
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='update',
        module='role',
        description=f'{status}角色: {role.name}'
    )

    return jsonify({'success': True, 'message': f'角色已{status}', 'is_active': role.is_active})


@roles_bp.route('/init-default', methods=['POST'])
@admin_required
def init_default():
    """初始化默认角色（管理员+操作员）"""
    # 创建管理员角色
    admin_role = Role.query.filter_by(name='管理员').first()
    if not admin_role:
        admin_role = Role(
            name='管理员',
            description='系统管理员，拥有所有权限',
            is_system=True,
            is_active=True
        )
        admin_role.set_permissions_list(get_default_permissions())
        db.session.add(admin_role)

    # 创建操作员角色
    operator_role = Role.query.filter_by(name='操作员').first()
    if not operator_role:
        operator_role = Role(
            name='操作员',
            description='普通操作员，拥有除系统管理外的权限',
            is_system=True,
            is_active=True
        )
        operator_role.set_permissions_list(get_operator_default_permissions())
        db.session.add(operator_role)

    db.session.commit()

    # 将现有admin用户关联管理员角色
    if admin_role:
        admin_users = User.query.filter_by(role='admin').all()
        for u in admin_users:
            if not u.role_id:
                u.role_id = admin_role.id

    # 将现有普通用户关联操作员角色
    if operator_role:
        normal_users = User.query.filter_by(role='user').all()
        for u in normal_users:
            if not u.role_id:
                u.role_id = operator_role.id

    db.session.commit()

    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='create',
        module='role',
        description='初始化默认角色（管理员+操作员）'
    )

    flash('默认角色初始化成功', 'success')
    return redirect(url_for('roles.list'))
