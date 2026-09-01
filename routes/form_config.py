"""
表单配置路由模块
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from models import db
from models.form_config import FormConfig, FormFieldConfig
from services.log_service import LogService
from utils.decorators import admin_required

form_config_bp = Blueprint('form_config', __name__, url_prefix='/form-config')

# 各表单类型对应的可用字段定义（字段代码 → {名称, 类型}）
# 字段代码和类型必须与数据库模型一致，用户只能自定义表头名称
FORM_AVAILABLE_FIELDS = {
    'stock_in_form': {
        'transaction_no': {'name': '单号', 'type': 'text'},
        'product_name': {'name': '商品', 'type': 'select'},
        'warehouse_name': {'name': '仓库', 'type': 'select'},
        'quantity': {'name': '数量', 'type': 'number'},
        'unit_cost': {'name': '单位成本', 'type': 'number'},
        'batch_no': {'name': '批次号', 'type': 'text'},
        'production_date': {'name': '生产日期', 'type': 'date'},
        'expire_date': {'name': '有效期', 'type': 'date'},
        'reference_no': {'name': '采购单号', 'type': 'text'},
        'remark': {'name': '备注', 'type': 'textarea'},
        'operator': {'name': '操作人', 'type': 'text'},
        'created_at': {'name': '入库时间', 'type': 'date'},
    },
    'stock_out_form': {
        'transaction_no': {'name': '单号', 'type': 'text'},
        'product_name': {'name': '商品', 'type': 'select'},
        'warehouse_name': {'name': '仓库', 'type': 'select'},
        'customer_name': {'name': '收货方', 'type': 'select'},
        'quantity': {'name': '数量', 'type': 'number'},
        'unit_cost': {'name': '单位成本', 'type': 'number'},
        'batch_no': {'name': '批次号', 'type': 'select'},
        'reference_no': {'name': '关联单号', 'type': 'text'},
        'remark': {'name': '备注', 'type': 'textarea'},
        'operator': {'name': '操作人', 'type': 'text'},
        'created_at': {'name': '出库时间', 'type': 'date'},
    },
    'delivery_note_form': {
        'transaction_no': {'name': '出库单号', 'type': 'text'},
        'product_name': {'name': '品名', 'type': 'text'},
        'model': {'name': '剂型', 'type': 'text'},
        'specification': {'name': '规格', 'type': 'text'},
        'manufacturer': {'name': '生产厂家', 'type': 'text'},
        'unit': {'name': '单位', 'type': 'text'},
        'quantity': {'name': '数量', 'type': 'number'},
        'unit_price': {'name': '单价', 'type': 'number'},
        'amount': {'name': '金额', 'type': 'number'},
        'batch_no': {'name': '生产批号', 'type': 'text'},
        'production_date': {'name': '生产日期', 'type': 'date'},
        'expiry_date': {'name': '有效期', 'type': 'date'},
        'approval_no': {'name': '批准文号', 'type': 'text'},
        'warehouse_name': {'name': '发货仓库', 'type': 'text'},
        'created_at': {'name': '发货日期', 'type': 'date'},
    }
}


@form_config_bp.route('/', methods=['GET'])
@admin_required
def index():
    """表单配置列表页面"""
    forms = FormConfig.query.order_by(FormConfig.created_at.desc()).all()
    return render_template('form_config/index.html', forms=forms)


@form_config_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create():
    """创建表单配置"""
    if request.method == 'POST':
        form_code = request.form.get('form_code', '').strip()
        form_name = request.form.get('form_name', '').strip()
        description = request.form.get('description', '').strip()

        if not form_code or not form_name:
            flash('表单代码和表单名称不能为空', 'danger')
            return redirect(url_for('form_config.create'))

        if FormConfig.query.filter_by(form_code=form_code).first():
            flash('表单代码已存在，请使用其他代码', 'danger')
            return redirect(url_for('form_config.create'))

        form_config = FormConfig(
            form_code=form_code,
            form_name=form_name,
            description=description,
            is_active=True,
            created_by=session.get('user_id')
        )
        db.session.add(form_config)
        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='create',
            module='form_config',
            description=f'创建表单配置：{form_name}'
        )

        flash('表单创建成功', 'success')
        return redirect(url_for('form_config.edit', id=form_config.id))

    return render_template('form_config/create.html')


@form_config_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit(id):
    """编辑表单配置"""
    form_config = FormConfig.query.get_or_404(id)

    if request.method == 'POST':
        form_config.form_name = request.form.get('form_name', '').strip()
        form_config.description = request.form.get('description', '').strip()
        form_config.company_name = request.form.get('company_name', '').strip()
        form_config.is_active = request.form.get('is_active') == 'on'

        db.session.commit()

        LogService.log_operation(
            user_id=session.get('user_id'),
            username=session.get('username'),
            operation_type='update',
            module='form_config',
            description=f'更新表单配置: {form_config.form_name}'
        )

        flash('表单更新成功', 'success')

    # 获取字段配置，按排序显示
    fields = FormFieldConfig.query.filter_by(
        form_config_id=id
    ).order_by(FormFieldConfig.sort_order, FormFieldConfig.id).all()
    
    # 预先在后端准备好JSON字符串，避免模板中复杂操作
    import json
    fields_json_str = json.dumps([field.to_dict() for field in fields], ensure_ascii=False)
    
    # 获取该表单类型可用的字段定义
    available_fields = FORM_AVAILABLE_FIELDS.get(form_config.form_code, {})
    # 计算未添加的字段（可用字段中排除已添加的）
    added_codes = [f.field_code for f in fields]
    remaining_fields = {code: info for code, info in available_fields.items() if code not in added_codes}
    all_fields_added = len(remaining_fields) == 0 and len(available_fields) > 0
    
    available_fields_json = json.dumps(available_fields, ensure_ascii=False)

    return render_template('form_config/edit.html', form=form_config, fields=fields, 
                           fields_json_str=fields_json_str,
                           available_fields_json=available_fields_json,
                           all_fields_added=all_fields_added)


@form_config_bp.route('/delete/<int:id>', methods=['POST'])
@admin_required
def delete(id):
    """删除表单配置"""
    form_config = FormConfig.query.get_or_404(id)
    form_name = form_config.form_name

    db.session.delete(form_config)
    db.session.commit()

    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='delete',
        module='form_config',
        description=f'删除表单配置：{form_name}'
    )

    flash('表单删除成功', 'success')
    return redirect(url_for('form_config.index'))


@form_config_bp.route('/<int:form_id>/fields/add', methods=['POST'])
@admin_required
def add_field(form_id):
    """添加字段配置"""
    form_config = FormConfig.query.get_or_404(form_id)

    field_code = request.form.get('field_code', '').strip()
    field_name = request.form.get('field_name', '').strip()
    field_type = request.form.get('field_type', 'text')
    is_required = request.form.get('is_required') == 'on'
    default_value = request.form.get('default_value', '')
    options = request.form.get('options', '')

    if not field_code or not field_name:
        return jsonify({'success': False, 'message': '字段代码和字段名称不能为空'}), 400

    if FormFieldConfig.query.filter_by(form_config_id=form_id, field_code=field_code).first():
        return jsonify({'success': False, 'message': '字段代码已存在'}), 400

    # 获取最大排序值
    max_sort = db.session.query(db.func.max(FormFieldConfig.sort_order)).filter_by(
        form_config_id=form_id
    ).scalar() or 0

    field = FormFieldConfig(
        form_config_id=form_id,
        field_code=field_code,
        field_name=field_name,
        field_type=field_type,
        is_visible=True,
        is_required=is_required,
        sort_order=max_sort + 1,
        default_value=default_value,
        options=options
    )
    db.session.add(field)
    db.session.commit()

    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='create',
        module='form_config',
        description=f'为表单 {form_config.form_name} 添加字段：{field_name}'
    )

    return jsonify({'success': True, 'field': field.to_dict()})


@form_config_bp.route('/<int:form_id>/fields/<int:field_id>/update', methods=['POST'])
@admin_required
def update_field(form_id, field_id):
    """更新字段配置"""
    field = FormFieldConfig.query.get_or_404(field_id)

    field.field_name = request.form.get('field_name', field.field_name).strip()
    field.field_type = request.form.get('field_type', field.field_type)
    field.is_visible = request.form.get('is_visible') == 'on'
    field.is_required = request.form.get('is_required') == 'on'
    field.sort_order = int(request.form.get('sort_order', field.sort_order))
    field.default_value = request.form.get('default_value', field.default_value)
    field.options = request.form.get('options', field.options)

    db.session.commit()

    form_config = FormConfig.query.get(form_id)
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='update',
        module='form_config',
        description=f'更新表单 {form_config.form_name} 的字段：{field.field_name}'
    )

    return jsonify({'success': True, 'field': field.to_dict()})


@form_config_bp.route('/<int:form_id>/fields/<int:field_id>/delete', methods=['POST'])
@admin_required
def delete_field(form_id, field_id):
    """删除字段配置"""
    field = FormFieldConfig.query.get_or_404(field_id)
    field_name = field.field_name

    db.session.delete(field)
    db.session.commit()

    form_config = FormConfig.query.get(form_id)
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='delete',
        module='form_config',
        description=f'删除表单 {form_config.form_name} 的字段：{field_name}'
    )

    return jsonify({'success': True})


@form_config_bp.route('/<int:form_id>/fields/reorder', methods=['POST'])
@admin_required
def reorder_fields(form_id):
    """重新排序字段"""
    field_ids = request.json.get('field_ids', [])

    for index, field_id in enumerate(field_ids):
        field = FormFieldConfig.query.get(field_id)
        if field:
            field.sort_order = index

    db.session.commit()

    form_config = FormConfig.query.get(form_id)
    LogService.log_operation(
        user_id=session.get('user_id'),
        username=session.get('username'),
        operation_type='update',
        module='form_config',
        description=f'重新排序表单 {form_config.form_name} 的字段'
    )

    return jsonify({'success': True})
