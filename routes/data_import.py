"""
数据导入路由模块
"""

from flask import Blueprint, render_template, request, send_file, flash, redirect, url_for, session
from services.import_service import ImportService
from services.log_service import LogService
from utils.decorators import login_required, admin_required

data_import_bp = Blueprint('data_import', __name__, url_prefix='/data-import')


@data_import_bp.route('/')
@admin_required
def index():
    """导入管理页面"""
    template_types = [
        {'type': 'products', 'name': '商品数据'},
        {'type': 'warehouses', 'name': '仓库数据'},
        {'type': 'suppliers', 'name': '供应商数据'},
        {'type': 'inventory', 'name': '库存数据'},
        {'type': 'purchase_orders', 'name': '采购单数据'},
        {'type': 'transactions', 'name': '出入库记录'},
    ]
    return render_template('data_import/index.html', template_types=template_types)


@data_import_bp.route('/template/<template_type>')
@admin_required
def download_template(template_type):
    """下载导入模板"""
    try:
        output = ImportService.get_template(template_type)
        template_info = ImportService.TEMPLATES.get(template_type, {})
        filename = f"{template_info.get('name', template_type)}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('data_import.index'))


@data_import_bp.route('/preview', methods=['POST'])
@admin_required
def preview():
    """预览导入数据"""
    template_type = request.form.get('template_type')
    file = request.files.get('file')

    if not file:
        return {'error': '请选择要上传的文件'}, 400

    if not template_type:
        return {'error': '请选择导入类型'}, 400

    # 检查文件格式
    if not file.filename.endswith(('.xlsx', '.xls')):
        return {'error': '请上传Excel文件（.xlsx或.xls格式）'}, 400

    try:
        headers, data, error = ImportService.preview_data(file.stream, template_type)

        if error:
            return {'error': error}, 400

        return {
            'success': True,
            'headers': headers,
            'data': data,
            'total_rows': len(data)
        }
    except Exception as e:
        return {'error': f'预览失败: {str(e)}'}, 500


@data_import_bp.route('/upload', methods=['POST'])
@admin_required
def upload():
    """上传并导入数据"""
    template_type = request.form.get('template_type')
    file = request.files.get('file')

    if not file:
        return {'error': '请选择要上传的文件'}, 400

    if not template_type:
        return {'error': '请选择导入类型'}, 400

    # 检查文件格式
    if not file.filename.endswith(('.xlsx', '.xls')):
        return {'error': '请上传Excel文件（.xlsx或.xls格式）'}, 400

    operator = session.get('username', 'system')

    try:
        # 根据类型调用不同的导入方法
        import_methods = {
            'products': ImportService.import_products,
            'warehouses': ImportService.import_warehouses,
            'suppliers': ImportService.import_suppliers,
            'inventory': ImportService.import_inventory,
            'purchase_orders': ImportService.import_purchase_orders,
            'transactions': ImportService.import_transactions,
        }

        import_method = import_methods.get(template_type)
        if not import_method:
            return {'error': '不支持的导入类型'}, 400

        success_count, error_count, errors = import_method(file.stream, operator)

        # 记录操作日志
        module_map = {
            'products': '商品',
            'warehouses': '仓库',
            'suppliers': '供应商',
            'inventory': '库存',
            'purchase_orders': '采购',
            'transactions': '出入库',
        }

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='import',
            module=module_map.get(template_type, template_type),
            description=f'导入{ImportService.TEMPLATES[template_type]["name"]}，成功{success_count}条，失败{error_count}条'
        )

        return {
            'success': True,
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors[:10]  # 只返回前10条错误
        }

    except Exception as e:
        return {'error': f'导入失败: {str(e)}'}, 500
