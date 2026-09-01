"""
操作日志路由模块
"""

from datetime import datetime
from flask import Blueprint, render_template, request, send_file, session
from models.operation_log import OperationLog
from services.log_service import LogService
from utils.excel_export import ExcelExport
from utils.decorators import admin_required

operation_logs_bp = Blueprint('operation_logs', __name__, url_prefix='/operation-logs')


@operation_logs_bp.route('/')
@admin_required
def list():
    """操作日志列表"""
    # 获取筛选参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    user_id = request.args.get('user_id', type=int)
    username = request.args.get('username', '')
    operation_type = request.args.get('operation_type', '')
    module = request.args.get('module', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    reference_no = request.args.get('reference_no', '')

    # 查询日志
    pagination = LogService.get_logs(
        page=page,
        per_page=per_page,
        user_id=user_id,
        username=username,
        operation_type=operation_type if operation_type else None,
        module=module if module else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        reference_no=reference_no if reference_no else None
    )

    # 获取操作类型和模块列表（用于筛选下拉框）
    operation_types = OperationLog.get_operation_types()
    modules = OperationLog.get_modules()

    return render_template(
        'operation_logs/list.html',
        pagination=pagination,
        operation_types=operation_types,
        modules=modules,
        # 保留筛选条件
        filters={
            'user_id': user_id,
            'username': username,
            'operation_type': operation_type,
            'module': module,
            'start_date': start_date,
            'end_date': end_date,
            'reference_no': reference_no,
        }
    )


@operation_logs_bp.route('/<int:log_id>')
@admin_required
def detail(log_id):
    """获取单个操作日志详情"""
    from flask import jsonify
    
    log = OperationLog.query.get_or_404(log_id)
    
    return jsonify({
        'id': log.id,
        'user_id': log.user_id,
        'username': log.username,
        'operation_type': log.operation_type,
        'module': log.module,
        'description': log.description,
        'reference_type': log.reference_type,
        'reference_no': log.reference_no,
        'reference_id': log.reference_id,
        'before_data': log.before_data,
        'after_data': log.after_data,
        'ip_address': log.ip_address,
        'user_agent': log.user_agent,
        'request_url': log.request_url,
        'request_method': log.request_method,
        'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else None
    })


@operation_logs_bp.route('/<int:log_id>/rollback', methods=['POST'])
@admin_required
def rollback(log_id):
    """撤销操作"""
    from flask import jsonify
    from services.rollback_service import rollback_service
    
    try:
        success, message = rollback_service.rollback(log_id)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@operation_logs_bp.route('/export')
@admin_required
def export():
    """导出操作日志"""
    # 获取筛选参数
    user_id = request.args.get('user_id', type=int)
    username = request.args.get('username', '')
    operation_type = request.args.get('operation_type', '')
    module = request.args.get('module', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    reference_no = request.args.get('reference_no', '')

    # 查询日志（不分页，获取所有符合条件的记录）
    query = OperationLog.query

    if user_id:
        query = query.filter(OperationLog.user_id == user_id)

    if username:
        query = query.filter(OperationLog.username.like(f'%{username}%'))

    if operation_type:
        query = query.filter(OperationLog.operation_type == operation_type)

    if module:
        query = query.filter(OperationLog.module == module)

    if start_date:
        query = query.filter(OperationLog.created_at >= start_date)

    if end_date:
        from datetime import timedelta
        end_datetime = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(OperationLog.created_at < end_datetime + timedelta(days=1))

    if reference_no:
        query = query.filter(OperationLog.reference_no.like(f'%{reference_no}%'))

    # 按创建时间倒序排列
    logs = query.order_by(OperationLog.created_at.desc()).limit(10000).all()

    # 准备导出数据
    headers = ['序号', '操作时间', '用户', '操作类型', '模块', '操作描述', '关联单号', 'IP地址', '请求URL']

    # 操作类型映射
    type_map = dict(OperationLog.get_operation_types())

    data = []
    for i, log in enumerate(logs, 1):
        data.append([
            i,
            log.created_at.strftime('%Y-%m-%d %H:%M:%S') if log.created_at else '',
            log.username or '',
            type_map.get(log.operation_type, log.operation_type or ''),
            log.module or '',
            log.description or '',
            log.reference_no or '',
            log.ip_address or '',
            log.request_url or ''
        ])

    # 创建Excel文件
    output = ExcelExport.create_excel(
        headers=headers,
        data=data,
        sheet_name='操作日志'
    )

    # 记录导出操作
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='export',
        module='系统',
        description=f'导出操作日志，共{len(logs)}条记录'
    )

    filename = f'操作日志_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
