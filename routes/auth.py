"""
认证路由模块 - 处理用户登录和登出
"""

import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db
from models.user import User
from services.log_service import LogService
from utils.rate_limit import limiter, RATE_LIMITS

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 登录失败锁定配置
MAX_LOGIN_ATTEMPTS = 5       # 最大登录失败次数
LOCK_DURATION = 15 * 60      # 锁定时长：15分钟（单位：秒）


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(RATE_LIMITS['login'])  # 登录接口限流：5次/分钟
def login():
    """登录页面和登录处理"""
    # 如果用户已登录，重定向到仪表盘
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        # 检查是否被锁定
        lock_until = session.get('login_lock_until')
        if lock_until:
            remaining = lock_until - time.time()
            if remaining > 0:
                minutes = int(remaining // 60) + 1
                flash(f'登录失败次数过多，账户已锁定，请在 {minutes} 分钟后重试', 'danger')
                return render_template('auth/login.html')
            else:
                # 锁定已过期，清除锁定状态
                session.pop('login_lock_until', None)
                session.pop('login_fail_count', None)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # 验证输入
        if not username or not password:
            flash('请输入用户名和密码', 'warning')
            return render_template('auth/login.html')

        # 查询用户
        user = User.query.filter_by(username=username, is_active=True).first()

        # 验证密码
        if user and user.check_password(password):
            # 登录成功，清除失败计数和锁定状态
            session.pop('login_fail_count', None)
            session.pop('login_lock_until', None)

            # 登录成功，设置session
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['real_name'] = user.real_name or user.username

            # 加载角色权限到session
            user_permissions = []
            if user.role_id and user.user_role:
                user_permissions = user.user_role.get_permissions_list()
            elif user.role == 'admin':
                # 兼容旧数据：无角色关联的管理员拥有全部权限
                from models.role import get_all_permissions
                user_permissions = get_all_permissions()
            session['permissions'] = user_permissions

            LogService.log_operation(user_id=user.id, username=user.username, operation_type='login', module='认证', description=f'用户登录: {user.username}')
            db.session.commit()
            
            # 检查是否需要强制修改密码
            if user.force_change_password:
                flash('为了账户安全，请立即修改密码', 'warning')
                return redirect(url_for('users.change_password'))
            
            flash(f'欢迎回来，{user.real_name or user.username}！', 'success')

            # 如果有next参数，重定向到指定页面（仅允许同源URL）
            next_page = request.args.get('next')
            if next_page:
                from urllib.parse import urlparse, urljoin
                ref_url = urlparse(request.host_url)
                next_url = urlparse(urljoin(request.host_url, next_page))
                if next_url.scheme in ('http', 'https') and next_url.netloc == ref_url.netloc:
                    return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            # 登录失败，累加失败次数
            fail_count = session.get('login_fail_count', 0) + 1
            session['login_fail_count'] = fail_count

            remaining_attempts = MAX_LOGIN_ATTEMPTS - fail_count
            if remaining_attempts > 0:
                flash(f'用户名或密码错误，还剩 {remaining_attempts} 次尝试机会', 'danger')
            else:
                # 达到最大失败次数，锁定账户
                session['login_lock_until'] = time.time() + LOCK_DURATION
                minutes = LOCK_DURATION // 60
                flash(f'登录失败次数过多，账户已锁定 {minutes} 分钟，请稍后再试', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """登出处理"""
    # 记录日志（在清除session之前）
    LogService.log_operation(user_id=session.get('user_id'), username=session.get('username'), operation_type='logout', module='认证', description=f'用户退出: {session.get("username")}')
    db.session.commit()
    # 清除session
    session.clear()
    flash('您已成功退出登录', 'info')
    return redirect(url_for('auth.login'))
