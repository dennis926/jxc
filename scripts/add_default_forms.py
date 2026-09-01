#!/usr/bin/env python3
"""
为现有数据库添加默认表单配置（入库单和出库单）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db
from models.form_config import FormConfig, FormFieldConfig

app = create_app()

def add_default_forms():
    """添加默认表单配置"""
    print('=' * 60)
    print('添加默认表单配置...')
    print('=' * 60)
    
    with app.app_context():
        # 入库单
        if not FormConfig.query.filter_by(form_code='stock_in_form').first():
            stock_in_form = FormConfig(
                form_code='stock_in_form',
                form_name='入库单',
                description='商品入库表单配置',
                is_active=True
            )
            db.session.add(stock_in_form)
            db.session.flush()
            
            # 入库单字段
            stock_in_fields = [
                {'code': 'transaction_no', 'name': '单号', 'type': 'text', 'required': True, 'order': 1, 'visible': True},
                {'code': 'product', 'name': '商品', 'type': 'select', 'required': True, 'order': 2, 'visible': True},
                {'code': 'warehouse', 'name': '仓库', 'type': 'select', 'required': True, 'order': 3, 'visible': True},
                {'code': 'quantity', 'name': '数量', 'type': 'number', 'required': True, 'order': 4, 'visible': True},
                {'code': 'unit_cost', 'name': '单位成本', 'type': 'number', 'required': True, 'order': 5, 'visible': True},
                {'code': 'batch_no', 'name': '批次号', 'type': 'text', 'required': False, 'order': 6, 'visible': True},
                {'code': 'production_date', 'name': '生产日期', 'type': 'date', 'required': False, 'order': 7, 'visible': True},
                {'code': 'expire_date', 'name': '有效期', 'type': 'date', 'required': False, 'order': 8, 'visible': True},
                {'code': 'remark', 'name': '备注', 'type': 'textarea', 'required': False, 'order': 9, 'visible': True}
            ]
            
            for field in stock_in_fields:
                f = FormFieldConfig(
                    form_config_id=stock_in_form.id,
                    field_code=field['code'],
                    field_name=field['name'],
                    field_type=field['type'],
                    is_required=field['required'],
                    sort_order=field['order'],
                    is_visible=field['visible']
                )
                db.session.add(f)
            
            print('✅ 入库单表单配置已创建')
        
        # 出库单
        if not FormConfig.query.filter_by(form_code='stock_out_form').first():
            stock_out_form = FormConfig(
                form_code='stock_out_form',
                form_name='出库单',
                description='商品出库表单配置',
                is_active=True
            )
            db.session.add(stock_out_form)
            db.session.flush()
            
            # 出库单字段
            stock_out_fields = [
                {'code': 'transaction_no', 'name': '单号', 'type': 'text', 'required': True, 'order': 1, 'visible': True},
                {'code': 'product', 'name': '商品', 'type': 'select', 'required': True, 'order': 2, 'visible': True},
                {'code': 'warehouse', 'name': '仓库', 'type': 'select', 'required': True, 'order': 3, 'visible': True},
                {'code': 'customer', 'name': '收货方', 'type': 'select', 'required': False, 'order': 4, 'visible': True},
                {'code': 'quantity', 'name': '数量', 'type': 'number', 'required': True, 'order': 5, 'visible': True},
                {'code': 'unit_cost', 'name': '单位成本', 'type': 'number', 'required': False, 'order': 6, 'visible': True},
                {'code': 'batch_no', 'name': '批次号', 'type': 'select', 'required': False, 'order': 7, 'visible': True},
                {'code': 'remark', 'name': '备注', 'type': 'textarea', 'required': False, 'order': 8, 'visible': True}
            ]
            
            for field in stock_out_fields:
                f = FormFieldConfig(
                    form_config_id=stock_out_form.id,
                    field_code=field['code'],
                    field_name=field['name'],
                    field_type=field['type'],
                    is_required=field['required'],
                    sort_order=field['order'],
                    is_visible=field['visible']
                )
                db.session.add(f)
            
            print('✅ 出库单表单配置已创建')
        
        # 随货同行单
        if not FormConfig.query.filter_by(form_code='delivery_note_form').first():
            delivery_note_form = FormConfig(
                form_code='delivery_note_form',
                form_name='随货同行单',
                description='随货同行单表单配置',
                is_active=True
            )
            db.session.add(delivery_note_form)
            db.session.flush()
            
            # 随货同行单字段
            delivery_note_fields = [
                {'code': 'transaction_no', 'name': '出库单号', 'type': 'text', 'required': True, 'order': 1, 'visible': True},
                {'code': 'product_name', 'name': '品名', 'type': 'text', 'required': True, 'order': 2, 'visible': True},
                {'code': 'model', 'name': '剂型', 'type': 'text', 'required': False, 'order': 3, 'visible': True},
                {'code': 'specification', 'name': '规格', 'type': 'text', 'required': True, 'order': 4, 'visible': True},
                {'code': 'manufacturer', 'name': '生产厂家', 'type': 'text', 'required': True, 'order': 5, 'visible': True},
                {'code': 'unit', 'name': '单位', 'type': 'text', 'required': True, 'order': 6, 'visible': True},
                {'code': 'quantity', 'name': '数量', 'type': 'number', 'required': True, 'order': 7, 'visible': True},
                {'code': 'unit_price', 'name': '单价', 'type': 'number', 'required': True, 'order': 8, 'visible': True},
                {'code': 'amount', 'name': '金额', 'type': 'number', 'required': True, 'order': 9, 'visible': True},
                {'code': 'batch_no', 'name': '生产批号', 'type': 'text', 'required': True, 'order': 10, 'visible': True},
                {'code': 'production_date', 'name': '生产日期', 'type': 'date', 'required': True, 'order': 11, 'visible': True},
                {'code': 'expiry_date', 'name': '有效期', 'type': 'date', 'required': True, 'order': 12, 'visible': True},
                {'code': 'approval_no', 'name': '批准文号', 'type': 'text', 'required': True, 'order': 13, 'visible': True},
                {'code': 'warehouse_name', 'name': '发货仓库', 'type': 'text', 'required': True, 'order': 14, 'visible': True},
                {'code': 'created_at', 'name': '发货日期', 'type': 'date', 'required': True, 'order': 15, 'visible': True}
            ]
            
            for field in delivery_note_fields:
                f = FormFieldConfig(
                    form_config_id=delivery_note_form.id,
                    field_code=field['code'],
                    field_name=field['name'],
                    field_type=field['type'],
                    is_required=field['required'],
                    sort_order=field['order'],
                    is_visible=field['visible']
                )
                db.session.add(f)
            
            print('✅ 随货同行单表单配置已创建')
        
        db.session.commit()
    
    print('=' * 60)
    print('默认表单配置添加完成！')
    print('=' * 60)

if __name__ == '__main__':
    add_default_forms()
