"""
系统配置路由模块
"""

import os
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app, jsonify
from werkzeug.utils import secure_filename
from models import db
from models.system_config import SystemConfig
from services.log_service import LogService
from utils.decorators import admin_required

system_config_bp = Blueprint('system_config', __name__, url_prefix='/system-config')


# 允许上传的文件类型
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    """检查文件类型是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@system_config_bp.route('/', methods=['GET', 'POST'])
@admin_required
def index():
    """系统配置页面"""
    if request.method == 'POST':
        # 保存配置 - 只更新表单中实际提交的字段
        config_keys = [
            'site_name', 'copyright', 'contact_email', 'contact_phone',
            'contact_address', 'items_per_page', 'enable_email_notify', 'low_stock_alert'
        ]

        for key in config_keys:
            # 只更新表单中存在的字段，避免覆盖未提交的配置
            if key in request.form:
                value = request.form.get(key, '')
                SystemConfig.set_value(
                    key=key,
                    value=value,
                    user_id=session.get('user_id')
                )

        # 记录操作日志
        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='系统',
            description='更新系统配置'
        )

        flash('配置保存成功', 'success')
        return redirect(url_for('system_config.index'))

    # GET请求 - 获取所有配置
    configs = {}
    for config in SystemConfig.query.all():
        configs[config.config_key] = {
            'value': config.config_value,
            'type': config.config_type,
            'description': config.description
        }

    # 确保所有默认配置都存在
    default_configs = SystemConfig.get_default_configs()
    for key, value, config_type, description in default_configs:
        if key not in configs:
            configs[key] = {
                'value': value,
                'type': config_type,
                'description': description
            }

    return render_template('system_config/index.html', configs=configs)


@system_config_bp.route('/upload-logo', methods=['POST'])
@admin_required
def upload_logo():
    """上传LOGO"""
    if 'logo' not in request.files:
        flash('请选择要上传的文件', 'danger')
        return redirect(url_for('system_config.index'))

    file = request.files['logo']

    if file.filename == '':
        flash('请选择要上传的文件', 'danger')
        return redirect(url_for('system_config.index'))

    if not allowed_file(file.filename):
        flash('不支持的文件类型，请上传PNG、JPG或GIF格式的图片', 'danger')
        return redirect(url_for('system_config.index'))

    try:
        # 确保上传目录存在
        upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)

        # 生成安全的文件名
        filename = secure_filename(f'logo_{datetime.now().strftime("%Y%m%d%H%M%S")}.{file.filename.rsplit(".", 1)[1].lower()}')
        file_path = os.path.join(upload_dir, filename)

        # 保存文件
        file.save(file_path)

        # 更新配置
        logo_url = f'/static/uploads/{filename}'
        SystemConfig.set_value(
            key='site_logo',
            value=logo_url,
            config_type='image',
            user_id=session.get('user_id')
        )

        # 记录操作日志
        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='系统',
            description='上传网站LOGO'
        )

        flash('LOGO上传成功', 'success')

    except Exception as e:
        flash(f'上传失败: {str(e)}', 'danger')

    return redirect(url_for('system_config.index'))


@system_config_bp.route('/reset', methods=['POST'])
@admin_required
def reset():
    """重置配置为默认值"""
    default_configs = SystemConfig.get_default_configs()

    for key, value, config_type, description in default_configs:
        SystemConfig.set_value(
            key=key,
            value=value,
            config_type=config_type,
            description=description,
            user_id=session.get('user_id')
        )

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='update',
        module='系统',
        description='重置系统配置为默认值'
    )

    flash('配置已重置为默认值', 'success')
    return redirect(url_for('system_config.index'))


# ==================== 平台API配置 ====================

# 各平台API配置项定义
PLATFORM_CONFIGS = {
    'taobao': {
        'name': '淘宝/天猫',
        'icon': 'fas fa-shopping-bag',
        'color': '#FF5000',
        'doc_url': 'https://open.taobao.com/doc.htm',
        'fields': [
            {'key': 'taobao_app_key', 'label': 'App Key', 'type': 'text', 'placeholder': '请输入淘宝App Key', 'desc': '在淘宝开放平台创建应用后获取'},
            {'key': 'taobao_app_secret', 'label': 'App Secret', 'type': 'password', 'placeholder': '请输入淘宝App Secret', 'desc': '应用密钥，请妥善保管'},
            {'key': 'taobao_session', 'label': 'Session', 'type': 'text', 'placeholder': '请输入授权Session', 'desc': 'OAuth授权后获取的Session Key'},
            {'key': 'taobao_sandbox', 'label': '沙箱环境', 'type': 'boolean', 'desc': '启用后使用沙箱环境进行测试'},
        ]
    },
    'jd': {
        'name': '京东',
        'icon': 'fas fa-store',
        'color': '#E2231A',
        'doc_url': 'https://open.jd.com/home/home/doc',
        'fields': [
            {'key': 'jd_app_key', 'label': 'App Key', 'type': 'text', 'placeholder': '请输入京东App Key', 'desc': '在京东开放平台创建应用后获取'},
            {'key': 'jd_app_secret', 'label': 'App Secret', 'type': 'password', 'placeholder': '请输入京东App Secret', 'desc': '应用密钥，请妥善保管'},
            {'key': 'jd_access_token', 'label': 'Access Token', 'type': 'text', 'placeholder': '请输入Access Token', 'desc': 'OAuth授权后获取的Token'},
            {'key': 'jd_sandbox', 'label': '沙箱环境', 'type': 'boolean', 'desc': '启用后使用沙箱环境进行测试'},
        ]
    },
    'douyin': {
        'name': '抖音/字节跳动',
        'icon': 'fab fa-tiktok',
        'color': '#010101',
        'doc_url': 'https://op.jinritemai.com/docs/guide-doc/93/748',
        'fields': [
            {'key': 'douyin_app_key', 'label': 'App Key', 'type': 'text', 'placeholder': '请输入抖音App Key', 'desc': '在抖音开放平台创建应用后获取'},
            {'key': 'douyin_app_secret', 'label': 'App Secret', 'type': 'password', 'placeholder': '请输入抖音App Secret', 'desc': '应用密钥，请妥善保管'},
            {'key': 'douyin_access_token', 'label': 'Access Token', 'type': 'text', 'placeholder': '请输入Access Token', 'desc': 'OAuth授权后获取的Token'},
            {'key': 'douyin_sandbox', 'label': '沙箱环境', 'type': 'boolean', 'desc': '启用后使用沙箱环境进行测试'},
        ]
    },
    'pdd': {
        'name': '拼多多',
        'icon': 'fas fa-shopping-cart',
        'color': '#E02E24',
        'doc_url': 'https://open.pinduoduo.com/application/document/browse',
        'fields': [
            {'key': 'pdd_client_id', 'label': 'Client ID', 'type': 'text', 'placeholder': '请输入拼多多Client ID', 'desc': '在拼多多开放平台创建应用后获取'},
            {'key': 'pdd_client_secret', 'label': 'Client Secret', 'type': 'password', 'placeholder': '请输入拼多多Client Secret', 'desc': '应用密钥，请妥善保管'},
            {'key': 'pdd_access_token', 'label': 'Access Token', 'type': 'text', 'placeholder': '请输入Access Token', 'desc': 'OAuth授权后获取的Token'},
            {'key': 'pdd_sandbox', 'label': '沙箱环境', 'type': 'boolean', 'desc': '启用后使用沙箱环境进行测试'},
        ]
    }
}


@system_config_bp.route('/platform-api')
@admin_required
def platform_api():
    """平台API配置页面"""
    # 读取所有已保存的平台配置
    configs = {}
    for config in SystemConfig.query.all():
        configs[config.config_key] = config.config_value

    return render_template('system_config/platform_api.html',
                           platforms=PLATFORM_CONFIGS,
                           configs=configs)


@system_config_bp.route('/platform-api/save', methods=['POST'])
@admin_required
def save_platform_api():
    """保存平台API配置"""
    platform_code = request.form.get('platform_code', '')
    platform_name = PLATFORM_CONFIGS.get(platform_code, {}).get('name', platform_code)

    if platform_code not in PLATFORM_CONFIGS:
        flash('无效的平台标识', 'danger')
        return redirect(url_for('system_config.platform_api'))

    # 保存该平台的所有配置项
    fields = PLATFORM_CONFIGS[platform_code]['fields']
    for field in fields:
        key = field['key']
        value = request.form.get(key, '')
        SystemConfig.set_value(
            key=key,
            value=value,
            config_type=field['type'],
            description=field.get('desc', ''),
            user_id=session.get('user_id')
        )

    # 记录操作日志
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='update',
        module='系统',
        description=f'更新{platform_name}API配置'
    )

    flash(f'{platform_name}API配置保存成功', 'success')
    return redirect(url_for('system_config.platform_api'))


@system_config_bp.route('/platform-api/test/<platform_code>', methods=['POST'])
@admin_required
def test_platform_api(platform_code):
    """测试平台API连接"""
    if platform_code not in PLATFORM_CONFIGS:
        return {'success': False, 'message': '无效的平台标识'}

    platform_name = PLATFORM_CONFIGS[platform_code]['name']
    configs = {}
    for field in PLATFORM_CONFIGS[platform_code]['fields']:
        configs[field['key'].replace(f'{platform_code}_', '')] = SystemConfig.get_value(field['key'], '')

    # 检查必填项
    required_fields = [f for f in PLATFORM_CONFIGS[platform_code]['fields'] if f['type'] != 'boolean']
    for field in required_fields:
        key = field['key']
        if not SystemConfig.get_value(key, ''):
            return {'success': False, 'message': f'{field["label"]} 未配置，请先填写'}

    # 尝试初始化平台API（实际连接测试需要各平台SDK支持）
    try:
        if platform_code == 'taobao':
            from services.platform.taobao import TaobaoAPI
            api = TaobaoAPI(configs)
            return {'success': True, 'message': f'{platform_name}API配置验证通过（接口调用功能尚在开发中）'}
        elif platform_code == 'jd':
            from services.platform.jd import JDAPI
            api = JDAPI(configs)
            return {'success': True, 'message': f'{platform_name}API配置验证通过（接口调用功能尚在开发中）'}
        elif platform_code == 'douyin':
            from services.platform.douyin import DouyinAPI
            api = DouyinAPI(configs)
            return {'success': True, 'message': f'{platform_name}API配置验证通过（接口调用功能尚在开发中）'}
        elif platform_code == 'pdd':
            from services.platform.pdd import PDDAPI
            api = PDDAPI(configs)
            return {'success': True, 'message': f'{platform_name}API配置验证通过（接口调用功能尚在开发中）'}
    except Exception as e:
        return {'success': False, 'message': f'初始化失败: {str(e)}'}

    return {'success': False, 'message': '未知平台'}
