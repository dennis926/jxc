"""
进销存管理系统 - Flask 主应用入口
启动方式: python app.py
访问地址: http://127.0.0.1:5001
"""

import os
import secrets
import time

# ===== 强制中国时区（Asia/Shanghai）=====
# 无论部署到哪个时区的服务器，进程内 datetime.now() 一律按北京时间计算，
# 数据库写入与统计口径（今天 / 本月起止等）保持一致，避免再次出现“美国时间”。
# 注意：依赖系统时区数据（/usr/share/zoneinfo/Asia/Shanghai，主流 Linux 均自带）。
# 若目标服务器缺失该文件，请在 systemd 单元或容器环境中显式设置 TZ=Asia/Shanghai。
os.environ['TZ'] = 'Asia/Shanghai'
try:
    time.tzset()
except AttributeError:
    pass  # Windows 无 tzset，可改用 zoneinfo / pytz

from flask import Flask, redirect, url_for, request, session, render_template, jsonify
from config import Config


def create_app():
    """创建并配置Flask应用"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # 使用配置中的 SECRET_KEY（已持久化）
    app.secret_key = Config.SECRET_KEY

    # 初始化 Jinja2 自定义过滤器
    _init_jinja_filters(app)

    # 强制禁用所有缓存
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.cache = None
    
    # 清除所有临时文件和缓存
    import shutil
    cache_dir = os.path.join(os.path.dirname(__file__), '.cache')
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
        except:
            pass

    # 初始化 CSRF 保护
    _init_csrf(app)

    # 初始化 API 限流
    from utils.rate_limit import limiter
    limiter.init_app(app)

    # 配置日志和性能监控
    from services.app_logging import setup_logging, PerformanceMonitor
    setup_logging(app)
    
    # 注册性能监控中间件
    app.before_request(PerformanceMonitor.before_request)
    app.after_request(PerformanceMonitor.after_request)
    app.teardown_request(PerformanceMonitor.teardown_request)

    # 禁用所有缓存，确保浏览器始终加载最新版本
    @app.after_request
    def add_no_cache_headers(response):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    # 初始化数据库
    from models.database import init_db
    init_db(app)

    # 注册蓝图（路由）
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.products import products_bp
    from routes.warehouses import warehouses_bp
    from routes.suppliers import suppliers_bp
    from routes.inventory import inventory_bp
    from routes.stock_transactions import stock_transactions_bp
    from routes.purchase_orders import purchase_orders_bp
    from routes.platform_orders import platform_orders_bp
    from routes.customers import customers_bp
    from routes.users import users_bp
    from routes.backup import backup_bp
    from routes.data_import import data_import_bp
    from routes.operation_logs import operation_logs_bp
    from routes.system_config import system_config_bp
    from routes.roles import roles_bp
    from routes.finance import finance_bp
    from routes.batches import batches_bp
    from routes.form_config import form_config_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(warehouses_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(stock_transactions_bp)
    app.register_blueprint(purchase_orders_bp)
    app.register_blueprint(platform_orders_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(data_import_bp)
    app.register_blueprint(operation_logs_bp)
    app.register_blueprint(system_config_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(batches_bp)
    app.register_blueprint(form_config_bp)

    # 初始化默认角色
    _init_default_roles(app)

    # 初始化内置邮件模板
    _init_email_templates(app)

    # 初始化调度器服务
    # 多 worker 部署时（gunicorn -w 2），每个 worker 都会执行 create_app()。
    # 若各 worker 都注册定时任务，同一时刻备份会被执行多次，
    # 备份历史中会出现同一时间点的重复记录。
    # 通过 RUN_SCHEDULER=0 可关闭指定进程的调度器（见 deploy/jxc.service 说明）。
    from services.scheduler_service import SchedulerService

    # 绑定 app 实例，供定时任务在后台线程中构建应用上下文，
    # 避免任务内部重复调用 create_app() 造成递归初始化
    SchedulerService.bind_app(app)

    if SchedulerService.should_run_scheduler():
        SchedulerService.get_scheduler()

        # 从数据库加载已保存的自动备份配置
        with app.app_context():
            from models.email_config import EmailConfig
            email_config = EmailConfig.query.filter_by(is_active=True).first()
            if email_config and email_config.enable_auto_backup:
                SchedulerService.add_backup_job(email_config.backup_hour, email_config.backup_minute)
                app.logger.info(f"已加载自动备份任务: 每日 {email_config.backup_hour:02d}:{email_config.backup_minute:02d}")
            else:
                app.logger.info("未配置自动备份任务")
    else:
        app.logger.info("当前进程已禁用调度器（RUN_SCHEDULER=0）")

    # 根路径重定向到仪表盘
    @app.route('/')
    def root():
        return redirect(url_for('dashboard.index'))

    # 全局before_request处理 - 排除登录相关路由
    @app.before_request
    def require_login():
        # 定义不需要登录就能访问的路由
        exempt_endpoints = {'auth.login', 'auth.logout', 'static'}

        # 检查当前请求是否在豁免列表中
        if request.endpoint in exempt_endpoints:
            return None

        # 检查是否已登录
        if 'user_id' not in session:
            # API请求返回401，页面请求重定向到登录页
            if request.is_json:
                return jsonify({'error': '未登录'}), 401
            return redirect(url_for('auth.login', next=request.url))

    # 注册自定义错误页面
    register_error_handlers(app)

    # 注册系统配置上下文处理器
    _init_system_config_context(app)
    _init_page_title_context(app)

    return app


def _init_system_config_context(app):
    """初始化系统配置上下文处理器，自动注入配置到所有模板"""
    @app.context_processor
    def inject_system_config():
        """将系统配置注入到所有模板"""
        try:
            from models.system_config import SystemConfig
            
            configs = {}
            for config in SystemConfig.query.all():
                configs[config.config_key] = config.config_value
            
            default_configs = SystemConfig.get_default_configs()
            for key, default_value, config_type, description in default_configs:
                if key not in configs:
                    configs[key] = default_value
            
            return {
                'site_name': configs.get('site_name', '进销存管理系统'),
                'site_logo': configs.get('site_logo', ''),
                'copyright': configs.get('copyright', 'Copyright © 2024 进销存管理系统'),
                'contact_email': configs.get('contact_email', ''),
                'contact_phone': configs.get('contact_phone', ''),
                'contact_address': configs.get('contact_address', ''),
                'system_configs': configs,
                'cache_version': int(time.time())
            }
        except Exception as e:
            return {
                'site_name': '进销存管理系统',
                'site_logo': '',
                'copyright': 'Copyright © 2024 进销存管理系统',
                'contact_email': '',
                'contact_phone': '',
                'contact_address': '',
                'system_configs': {},
                'cache_version': int(time.time())
            }


# 端点前缀 -> 顶栏页面标题映射
# base.html 的 page_title 块默认写死"仪表盘"，而全项目仅 2 个模板覆盖了它，
# 导致几乎所有页面顶栏都显示"仪表盘"。这里按 blueprint/endpoint 自动推导标题，
# 无需逐个模板改造；模板若显式覆盖 page_title 块，仍以模板为准。
PAGE_TITLES = {
    # 概览
    'dashboard.index': '仪表盘',
    'dashboard.reports': '数据报表',

    # 商品
    'products.list': '商品管理',
    'products.create': '新增商品',
    'products.edit': '编辑商品',
    'products': '商品管理',

    # 仓库
    'warehouses.list': '仓库管理',
    'warehouses.create': '新增仓库',
    'warehouses.edit': '编辑仓库',
    'warehouses': '仓库管理',

    # 供应商
    'suppliers.list': '供应商管理',
    'suppliers.create': '新增供应商',
    'suppliers.edit': '编辑供应商',
    'suppliers': '供应商管理',

    # 客户
    'customers.list': '客户列表',
    'customers.add': '添加客户',
    'customers.edit': '编辑客户',
    'customers': '客户列表',

    # 表单配置
    'form_config.index': '表单管理',
    'form_config.create': '新建表单',
    'form_config.edit': '编辑表单',
    'form_config': '表单管理',

    # 批次
    'batches.list': '批次管理',
    'batches.add': '添加批次',
    'batches.edit': '编辑批次',
    'batches.codes': '批次码明细',
    'batches.select_codes': '选择出库码段',
    'batches': '批次管理',

    # 库存
    'inventory.list': '库存查询',
    'inventory.stock_in': '入库操作',
    'inventory.stock_out': '出库操作',
    'inventory.transfer': '调拨操作',
    'inventory.adjust': '库存盘点',
    'inventory': '库存管理',

    # 采购
    'purchase_orders.list': '采购管理',
    'purchase_orders.create': '新建采购单',
    'purchase_orders.edit': '编辑采购单',
    'purchase_orders.receive': '采购入库确认',
    'purchase_orders': '采购管理',

    # 出入库记录
    'stock_transactions.list': '出入库记录',
    'stock_transactions.edit': '编辑出入库记录',
    'stock_transactions.delete': '删除出入库记录',
    'stock_transactions': '出入库记录',

    'platform_orders': '平台订单',

    # 财务
    'finance.accounts': '账户管理',
    'finance.add_account': '添加账户',
    'finance.edit_account': '编辑账户',
    'finance.transactions': '收支记录',
    'finance.add_transaction': '添加收支记录',
    'finance.receivables': '应收款管理',
    'finance.collect_receivable': '收款',
    'finance.payables': '应付款管理',
    'finance.pay_amount': '付款',
    'finance.reconciliation': '对账结算',
    'finance.profit_report': '利润表',
    'finance.balance_report': '资产负债表',
    'finance.receivable_detail': '应收款明细表',
    'finance.payable_detail': '应付款明细表',
    'finance': '财务管理',

    # 用户与权限
    'users.list': '用户管理',
    'users.create': '新增用户',
    'users.edit': '编辑用户',
    'users.profile': '个人资料',
    'users.change_password': '修改密码',
    'users': '用户管理',
    'roles.list': '角色管理',
    'roles.create': '新建角色',
    'roles.edit': '编辑角色',
    'roles': '角色管理',

    # 系统
    'operation_logs.list': '操作日志',
    'operation_logs.detail': '日志详情',
    'operation_logs': '操作日志',
    'system_config.index': '系统配置',
    'system_config.platform_api': '平台API配置',
    'system_config': '系统配置',
    'backup.index': '数据备份管理',
    'backup.config': '邮箱配置',
    'backup.files': '备份文件',
    'backup.restore': '恢复数据',
    'backup.templates': '邮件模板管理',
    'backup.edit_template': '编辑邮件模板',
    'backup': '数据备份',
    'data_import': '数据导入',
    'auth': '登录',
}


def _resolve_page_title(endpoint):
    """按端点推导顶栏标题：先精确匹配 blueprint.view，再退回 blueprint 名"""
    if not endpoint:
        return '仪表盘'
    if endpoint in PAGE_TITLES:
        return PAGE_TITLES[endpoint]
    blueprint = endpoint.split('.')[0]
    return PAGE_TITLES.get(blueprint, '仪表盘')


def _init_page_title_context(app):
    """注入 auto_page_title，供 base.html 顶栏使用"""
    @app.context_processor
    def inject_page_title():
        try:
            return {'auto_page_title': _resolve_page_title(request.endpoint)}
        except Exception:
            return {'auto_page_title': '仪表盘'}


def _init_default_roles(app):
    """初始化默认角色（管理员+操作员），仅在角色表为空时执行"""
    with app.app_context():
        from models.role import Role, get_default_permissions, get_operator_default_permissions
        from models.user import User

        # 仅在角色表为空时初始化
        if Role.query.first() is not None:
            return

        # 创建管理员角色
        admin_role = Role(
            name='管理员',
            description='系统管理员，拥有所有权限',
            is_system=True,
            is_active=True
        )
        admin_role.set_permissions_list(get_default_permissions())

        # 创建操作员角色
        operator_role = Role(
            name='操作员',
            description='普通操作员，拥有除系统管理外的权限',
            is_system=True,
            is_active=True
        )
        operator_role.set_permissions_list(get_operator_default_permissions())

        from models import db
        db.session.add(admin_role)
        db.session.add(operator_role)
        db.session.commit()

        # 将现有用户关联到对应角色
        admin_users = User.query.filter_by(role='admin').all()
        for u in admin_users:
            u.role_id = admin_role.id

        normal_users = User.query.filter_by(role='user').all()
        for u in normal_users:
            u.role_id = operator_role.id

        db.session.commit()


def _init_email_templates(app):
    """初始化内置邮件模板（仅在表为空时执行）"""
    with app.app_context():
        from models.email_template import EmailTemplate
        from models import db
        try:
            EmailTemplate.init_builtin_templates()
            app.logger.info('已初始化内置邮件模板')
        except Exception as e:
            app.logger.error(f'初始化内置邮件模板失败: {e}')


def _init_jinja_filters(app):
    """初始化 Jinja2 自定义过滤器"""
    @app.template_filter('abs')
    def abs_filter(value):
        """绝对值过滤器"""
        try:
            return abs(value)
        except:
            return value


def _init_csrf(app):
    """初始化 CSRF 保护（手动实现，不依赖 Flask-WTF）"""
    @app.before_request
    def csrf_protect():
        if request.method not in ('POST', 'PUT', 'DELETE'):
            return None

        if request.is_json:
            return None

        form_token = request.form.get('csrf_token', '')
        header_token = request.headers.get('X-CSRFToken', '')
        request_token = form_token or header_token
        
        session_token = session.get('_csrf_token', None)

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if not session_token or not request_token or request_token != session_token:
            from flask import flash, abort
            if is_ajax:
                return jsonify({'error': '安全验证失败，请刷新页面后重试'}), 403
            flash('安全验证失败，请刷新页面后重试', 'danger')
            return abort(403)

    @app.context_processor
    def inject_csrf_token():
        def generate_csrf_token():
            if '_csrf_token' not in session:
                session['_csrf_token'] = secrets.token_hex(16)
            return session['_csrf_token']
        return dict(csrf_token=generate_csrf_token)


def register_error_handlers(app):
    """注册自定义错误页面"""
    @app.errorhandler(400)
    def bad_request(e):
        if request.is_json:
            return jsonify({'error': '请求无效'}), 400
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden(e):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if request.is_json or is_ajax:
            return jsonify({'error': '没有权限访问'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        if request.is_json:
            return jsonify({'error': '页面不存在'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(e):
        import traceback as tb
        error_traceback = tb.format_exc()
        app.logger.error(f"500 Error on {request.method} {request.url}: {str(e)}\n{error_traceback}")
        if request.is_json:
            return jsonify({'error': '服务器内部错误', 'detail': str(e)}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def too_many_requests(e):
        """限流错误页面

        从 Flask-Limiter 的异常对象中解析真实的冷却秒数，传给页面做倒计时，
        避免页面写死秒数导致倒计时结束后立即再次触发限流。
        """
        retry_after = _parse_retry_after(e)

        if request.is_json:
            resp = jsonify({
                'error': '请求过于频繁，请稍后再试',
                'retry_after': retry_after
            })
            resp.status_code = 429
            resp.headers['Retry-After'] = str(retry_after)
            return resp

        resp = app.make_response((
            render_template('errors/429.html', retry_after=retry_after), 429
        ))
        resp.headers['Retry-After'] = str(retry_after)
        return resp


def _parse_retry_after(e, default=60):
    """从限流异常中推断需要等待的秒数

    Flask-Limiter 抛出的 429 异常里，限流信息可能出现在以下位置：
    1. e.retry_after            —— 部分版本直接提供
    2. e.description            —— 形如 "5 per 1 minute" 的字符串
    3. 响应头 Retry-After       —— 由 limiter 自动附加

    任何一项解析失败都回退到 default，保证页面始终能正常渲染。
    """
    import re

    # 1) 直接取属性
    value = getattr(e, 'retry_after', None)
    if isinstance(value, (int, float)) and value > 0:
        return int(value)

    # 2) 解析 description 中的时间窗口，如 "5 per 1 minute" / "60 per minute"
    desc = str(getattr(e, 'description', '') or '')
    unit_seconds = {
        'second': 1, 'minute': 60, 'hour': 3600, 'day': 86400,
    }
    match = re.search(
        r'per\s+(\d+)?\s*(second|minute|hour|day)', desc, re.IGNORECASE
    )
    if match:
        count = int(match.group(1) or 1)
        seconds = count * unit_seconds[match.group(2).lower()]
        # 冷却时间上限设为 5 分钟，避免出现"请等待 24 小时"这种无意义的倒计时
        return max(1, min(seconds, 300))

    return default


if __name__ == '__main__':
    app = create_app()
    print('=' * 50)
    print('  HONS进销存管理系统启动成功')
    print('  内网访问地址: http://127.0.0.1:5001')
    print('  按 Ctrl+C 停止服务')
    print('=' * 50)
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5001)
