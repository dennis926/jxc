"""
装饰器模块 - 包含各种视图装饰器
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify


def login_required(f):
    """
    登录验证装饰器
    用于保护需要登录才能访问的路由
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # 检查是否是 AJAX/JSON 请求
            # 1. 检查 X-Requested-With 头
            # 2. 检查 Accept 头是否包含 application/json
            # 3. 检查 URL 是否以 /api/ 开头
            # 4. 检查请求路径是否包含 'api'
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                'application/json' in request.headers.get('Accept', '') or
                request.path.startswith('/api/') or
                '/api/' in request.path
            )
            if is_ajax:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    管理员权限验证装饰器
    用于保护只有管理员才能访问的路由
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('您没有权限访问此页面', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function


def permission_required(*permissions):
    """
    细粒度权限验证装饰器
    检查当前用户是否拥有指定的权限（任一即可）

    Args:
        *permissions: 一个或多个权限标识，满足任一即通过

    使用示例:
        @permission_required('product.create')
        def create_product():
            ...

        @permission_required('product.edit', 'product.delete')
        def manage_product():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('请先登录', 'warning')
                return redirect(url_for('auth.login'))

            # 管理员始终拥有所有权限
            if session.get('role') == 'admin':
                return f(*args, **kwargs)

            # 检查权限列表
            user_permissions = session.get('permissions', [])
            for perm in permissions:
                if perm in user_permissions:
                    return f(*args, **kwargs)

            flash('您没有权限执行此操作', 'danger')
            return redirect(url_for('dashboard.index'))
        return decorated_function
    return decorator


def log_operation(operation_type, module, description_template=None):
    """
    操作日志装饰器
    自动记录关键操作到日志
    
    Args:
        operation_type: 操作类型 (login/logout/create/update/delete/import/export等)
        module: 模块名 (商品/仓库/库存/采购等)
        description_template: 操作描述模板，支持使用 {kwargs} 格式化
        
    使用示例:
        @log_operation('create', '商品', '创建商品: {name}')
        def create_product(name):
            ...
            
        @log_operation('update', '库存', '更新库存: 商品ID={product_id}')
        def update_stock(product_id, quantity):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 执行原函数
            result = f(*args, **kwargs)
            
            # 记录操作日志
            try:
                from services.log_service import LogService
                
                # 构建描述
                description = description_template
                if description_template:
                    try:
                        # 尝试使用 kwargs 格式化描述
                        description = description_template.format(**kwargs)
                    except (KeyError, ValueError):
                        # 如果格式化失败，使用原始模板
                        pass
                else:
                    # 如果没有提供模板，使用函数名作为描述
                    description = f'执行操作: {f.__name__}'
                
                # 获取用户信息
                user_id = session.get('user_id')
                username = session.get('username')
                
                # 尝试从返回值获取关联信息
                reference_type = None
                reference_no = None
                reference_id = None
                
                if isinstance(result, dict):
                    reference_type = result.get('reference_type')
                    reference_no = result.get('reference_no')
                    reference_id = result.get('reference_id')
                
                # 记录日志
                LogService.log_operation(
                    user_id=user_id,
                    username=username,
                    operation_type=operation_type,
                    module=module,
                    description=description,
                    reference_type=reference_type,
                    reference_no=reference_no,
                    reference_id=reference_id
                )
            except Exception as e:
                # 日志记录失败不应影响主功能
                print(f'[警告] 记录操作日志失败: {str(e)}')
            
            return result
        return decorated_function
    return decorator


def log_operation_async(operation_type, module, get_description=None, get_reference=None):
    """
    异步操作日志装饰器（支持从请求上下文获取信息）
    
    Args:
        operation_type: 操作类型
        module: 模块名
        get_description: 获取描述的函数，接收 (result, kwargs) 参数
        get_reference: 获取关联信息的函数，接收 (result, kwargs) 参数
        
    使用示例:
        @log_operation_async(
            'create', 
            '商品',
            get_description=lambda r, kw: f'创建商品: {r.get("name", "")}',
            get_reference=lambda r, kw: ('product', r.get('sku'), r.get('id'))
        )
        def create_product():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 执行原函数
            result = f(*args, **kwargs)
            
            # 记录操作日志
            try:
                from services.log_service import LogService
                
                # 获取描述
                if get_description:
                    description = get_description(result, kwargs)
                else:
                    description = f'执行操作: {f.__name__}'
                
                # 获取关联信息
                reference_type = None
                reference_no = None
                reference_id = None
                
                if get_reference:
                    ref_info = get_reference(result, kwargs)
                    if ref_info and len(ref_info) >= 3:
                        reference_type, reference_no, reference_id = ref_info[0], ref_info[1], ref_info[2]
                
                # 获取用户信息
                user_id = session.get('user_id')
                username = session.get('username')
                
                # 记录日志
                LogService.log_operation(
                    user_id=user_id,
                    username=username,
                    operation_type=operation_type,
                    module=module,
                    description=description,
                    reference_type=reference_type,
                    reference_no=reference_no,
                    reference_id=reference_id
                )
            except Exception as e:
                print(f'[警告] 记录操作日志失败: {str(e)}')
            
            return result
        return decorated_function
    return decorator
