#!/usr/bin/env python3
"""
初始化数据库脚本
- 清空现有数据
- 保留表结构
- 创建初始管理员
"""

import os
import sys

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app import create_app
from models import db
from models.user import User
from models.role import Role
from models.database import init_db
from models.form_config import FormConfig, FormFieldConfig
from models.warehouse import Warehouse
from models.product import Product


def init_empty_database():
    """初始化空数据库"""
    print('=' * 60)
    print('开始初始化数据库...')
    print('=' * 60)
    
    app = create_app()
    
    with app.app_context():
        # 初始化数据库（创建表）
        init_db(app)
        print('✅ 数据库表结构已创建')
        
        # 检查是否已有管理员
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            # 创建初始管理员
            admin = User(
                username='admin',
                real_name='系统管理员',
                role='admin',
                is_active=True,
                force_change_password=True
            )
            admin.set_password('Admin@2026!')
            db.session.add(admin)
            db.session.commit()
            
            print('✅ 初始管理员账号已创建')
            print('   用户名: admin')
            print('   密码: Admin@2026!')
            print('⚠️  首次登录请修改密码！')
        else:
            print('⚠️  管理员账号已存在')
        
        # 初始化默认角色（使用中文名）
        from models.role import get_default_permissions, get_operator_default_permissions
        if not Role.query.filter_by(name='管理员').first():
            admin_role = Role(
                name='管理员',
                description='系统管理员，拥有所有权限',
                is_system=True,
                is_active=True
            )
            admin_role.set_permissions_list(get_default_permissions())
            db.session.add(admin_role)
        
        if not Role.query.filter_by(name='操作员').first():
            operator_role = Role(
                name='操作员',
                description='普通操作员，拥有除系统管理外的权限',
                is_system=True,
                is_active=True
            )
            operator_role.set_permissions_list(get_operator_default_permissions())
            db.session.add(operator_role)
        
        db.session.commit()
        print('✅ 系统角色已初始化')
        
        # 初始化默认表单配置
        init_default_forms()
        
        # 初始化默认业务数据
        init_default_data()
        
    print('=' * 60)
    print('数据库初始化完成！')
    print('=' * 60)


def init_default_forms():
    """初始化默认表单配置（入库单和出库单）"""
    print('\n📋 初始化默认表单配置...')
    
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


def init_default_data():
    """初始化默认仓库和商品数据"""
    print('\n📦 初始化默认业务数据...')
    
    # 默认仓库
    warehouses_data = [
        {'name': '山东艺钧堂医疗科技有限公司', 'code': '01', 'address': '烟台市芝罘区港城西大街粤港湾', 'is_active': True},
        {'name': '新零售仓库', 'code': '02', 'address': '烟台市芝罘区港城西大街粤港湾', 'is_active': True},
    ]
    
    for wh in warehouses_data:
        if not Warehouse.query.filter_by(code=wh['code']).first():
            warehouse = Warehouse(
                name=wh['name'],
                code=wh['code'],
                address=wh['address'],
                is_active=wh['is_active']
            )
            db.session.add(warehouse)
    
    db.session.flush()
    print('✅ 默认仓库已创建')
    
    # 默认商品
    products_data = [
        {'sku': 'QA', 'name': '卿尔美牌膳食纤维特膳粉A版', 'barcode': '6977355161110', 'specification': '30盒/箱 30袋/盒 8克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '运动营养食品-补充能量类', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': 'LYJY017-25246', 'is_active': True, 'cost_price': 249, 'selling_price': 866, 'min_stock': 20},
        {'sku': 'QC', 'name': '卿尔美牌膳食纤维特膳粉C版', 'barcode': '6977355161127', 'specification': '30盒/箱 30袋/盒 12克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '运动营养食品-补充能量类', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': 'LYJY011-25220', 'is_active': True, 'cost_price': 177, 'selling_price': 586, 'min_stock': 30},
        {'sku': 'QE', 'name': '卿尔美牌膳食纤维特膳粉E版', 'barcode': '6977355161158', 'specification': '30盒/箱 20袋/盒 10克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '运动营养食品-补充能量类', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': 'LYJY008-25077', 'is_active': True, 'cost_price': 88, 'selling_price': 398, 'min_stock': 20},
        {'sku': 'JC', 'name': '金善加牌营养素特膳粉C版', 'barcode': '6977355161189', 'specification': '40盒/箱 30袋/盒 1.8克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '运动营养食品-耐力类', 'manufacturer': '东凯（山东)生物科技有限公司', 'approval_no': 'LYJY014-26026', 'is_active': True, 'cost_price': 111, 'selling_price': 398, 'min_stock': 40},
        {'sku': 'YSJ', 'name': '卿尔美牌益生元复合益生菌', 'barcode': '6977355169352', 'specification': '40盒/箱 10袋/盒 10克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '食用乳酸菌粉', 'manufacturer': '东凯（山东)生物科技有限公司', 'approval_no': 'QEM004-26024', 'is_active': True, 'cost_price': 48, 'selling_price': 198, 'min_stock': 120},
        {'sku': 'CQY', 'name': '长青元牌后生元药食同源发酵粉', 'barcode': '6977355167778', 'specification': '40盒/箱 10袋/盒 5克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '药食同源液态发酵冻干粉', 'manufacturer': '东凯（山东)生物科技有限公司', 'approval_no': 'LYJY005-26025', 'is_active': True, 'cost_price': 48, 'selling_price': 198, 'min_stock': 80},
        {'sku': 'QZQ', 'name': '卿尔美牌膳食纤维特膳粉增强版', 'barcode': '6977355169918', 'specification': '40盒/箱 10袋/盒 3.8克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '运动营养食品-耐力类', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': 'LYJY018-25242', 'is_active': True, 'cost_price': 40, 'selling_price': 178, 'min_stock': 40},
        {'sku': 'JZQ', 'name': '金善加牌营养素特膳粉增强版', 'barcode': '6977355169994', 'specification': '40盒/箱 10袋/盒 1.6克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '运动营养食品-耐力类', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': 'LYJY019-25243', 'is_active': True, 'cost_price': 40, 'selling_price': 178, 'min_stock': 40},
        {'sku': 'QZZ', 'name': '卿尔美牌膳食纤维固体饮料智臻版', 'barcode': '6973353361101', 'specification': '10盒/箱 30袋/盒 10克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '植物固体饮料', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': 'LYJY009-25040', 'is_active': True, 'cost_price': 499, 'selling_price': 2980, 'min_stock': 2},
        {'sku': 'XQ', 'name': '老版卿尔美增强版', 'barcode': '', 'specification': '60盒/箱 30袋/盒 3.8克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '植物固体饮料', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': '', 'is_active': True, 'cost_price': 0, 'selling_price': 0, 'min_stock': 0},
        {'sku': 'XJ', 'name': '老版卿亦美增强版', 'barcode': '', 'specification': '60盒/箱 30袋/盒 1克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '植物固体饮料', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': '', 'is_active': True, 'cost_price': 0, 'selling_price': 0, 'min_stock': 0},
        {'sku': 'QYMA', 'name': '卿亦美A版', 'barcode': '', 'specification': '60盒/箱 30袋/盒 3.8克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '植物固体饮料', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': '', 'is_active': True, 'cost_price': 0, 'selling_price': 0, 'min_stock': 0},
        {'sku': 'QYMC', 'name': '卿亦美C版', 'barcode': '', 'specification': '60盒/箱 20;30袋/盒 3.8克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '植物固体饮料', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': '', 'is_active': True, 'cost_price': 0, 'selling_price': 0, 'min_stock': 0},
        {'sku': '过期', 'name': '卿尔美C', 'barcode': '', 'specification': '30盒/箱 30袋/盒 12克/袋', 'category': '基层医疗', 'unit': '盒', 'dosage_form': '植物固体饮料', 'manufacturer': '青岛诺和诺康生物科技有限公司', 'approval_no': '', 'is_active': True, 'cost_price': 0, 'selling_price': 0, 'min_stock': 0},
    ]
    
    for p in products_data:
        if not Product.query.filter_by(sku=p['sku']).first():
            product = Product(
                sku=p['sku'],
                name=p['name'],
                barcode=p['barcode'] or None,
                specification=p['specification'],
                category=p['category'],
                unit=p['unit'],
                dosage_form=p['dosage_form'],
                manufacturer=p['manufacturer'],
                approval_no=p['approval_no'],
                is_active=p['is_active'],
                cost_price=p['cost_price'],
                selling_price=p['selling_price'],
                min_stock=p['min_stock']
            )
            db.session.add(product)
    
    db.session.commit()
    print('✅ 默认商品已创建')


if __name__ == '__main__':
    init_empty_database()
