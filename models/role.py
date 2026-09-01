"""
角色模型 - 支持细粒度权限控制
"""

import json
from models.database import db
from datetime import datetime


# ==================== 权限定义 ====================
# 每个模块定义多个操作权限，格式: (权限标识, 显示名称, 描述)
PERMISSION_MODULES = {
    'dashboard': {
        'name': '仪表盘',
        'icon': 'fas fa-tachometer-alt',
        'permissions': {
            'dashboard.view': {'name': '查看仪表盘', 'desc': '访问仪表盘页面'},
            'dashboard.reports': {'name': '查看数据报表', 'desc': '访问数据报表页面'},
        }
    },
    'product': {
        'name': '商品管理',
        'icon': 'fas fa-box',
        'permissions': {
            'product.view': {'name': '查看商品', 'desc': '查看商品列表'},
            'product.create': {'name': '新增商品', 'desc': '创建新商品'},
            'product.edit': {'name': '编辑商品', 'desc': '修改商品信息'},
            'product.delete': {'name': '删除商品', 'desc': '删除商品'},
            'product.export': {'name': '导出商品', 'desc': '导出商品数据'},
        }
    },
    'warehouse': {
        'name': '仓库管理',
        'icon': 'fas fa-warehouse',
        'permissions': {
            'warehouse.view': {'name': '查看仓库', 'desc': '查看仓库列表'},
            'warehouse.create': {'name': '新增仓库', 'desc': '创建新仓库'},
            'warehouse.edit': {'name': '编辑仓库', 'desc': '修改仓库信息'},
            'warehouse.delete': {'name': '删除仓库', 'desc': '删除仓库'},
        }
    },
    'supplier': {
        'name': '供应商管理',
        'icon': 'fas fa-truck',
        'permissions': {
            'supplier.view': {'name': '查看供应商', 'desc': '查看供应商列表'},
            'supplier.create': {'name': '新增供应商', 'desc': '创建新供应商'},
            'supplier.edit': {'name': '编辑供应商', 'desc': '修改供应商信息'},
            'supplier.delete': {'name': '删除供应商', 'desc': '删除供应商'},
        }
    },
    'inventory': {
        'name': '库存管理',
        'icon': 'fas fa-cubes',
        'permissions': {
            'inventory.view': {'name': '查看库存', 'desc': '查看库存列表'},
            'inventory.stock_in': {'name': '商品入库', 'desc': '执行入库操作'},
            'inventory.stock_out': {'name': '商品出库', 'desc': '执行出库操作'},
            'inventory.transfer': {'name': '库存调拨', 'desc': '执行调拨操作'},
            'inventory.adjust': {'name': '库存盘点', 'desc': '执行盘点调整'},
            'inventory.records': {'name': '出入库记录', 'desc': '查看出入库明细'},
        }
    },
    'purchase': {
        'name': '采购管理',
        'icon': 'fas fa-shopping-cart',
        'permissions': {
            'purchase.view': {'name': '查看采购单', 'desc': '查看采购订单列表'},
            'purchase.create': {'name': '创建采购单', 'desc': '创建新采购订单'},
            'purchase.edit': {'name': '编辑采购单', 'desc': '修改采购订单'},
            'purchase.delete': {'name': '删除采购单', 'desc': '删除采购订单'},
            'purchase.receive': {'name': '采购入库', 'desc': '确认采购入库'},
        }
    },
    'platform': {
        'name': '电商对接',
        'icon': 'fas fa-globe',
        'permissions': {
            'platform.orders': {'name': '查看平台订单', 'desc': '查看电商平台订单'},
            'platform.api_config': {'name': '平台API配置', 'desc': '配置平台API参数'},
        }
    },
    'system': {
        'name': '系统管理',
        'icon': 'fas fa-cog',
        'permissions': {
            'system.users': {'name': '用户管理', 'desc': '管理系统用户'},
            'system.roles': {'name': '角色管理', 'desc': '管理角色和权限'},
            'system.config': {'name': '系统配置', 'desc': '修改系统配置'},
            'system.backup': {'name': '数据备份', 'desc': '备份和恢复数据'},
            'system.logs': {'name': '操作日志', 'desc': '查看操作日志'},
            'system.import': {'name': '数据导入', 'desc': '导入数据'},
        }
    },
    'finance': {
        'name': '财务管理',
        'icon': 'fas fa-calculator',
        'permissions': {
            'finance.accounts': {'name': '账户管理', 'desc': '管理资金账户'},
            'finance.transactions': {'name': '收支记录', 'desc': '查看和管理收支记录'},
            'finance.receivables': {'name': '应收款管理', 'desc': '管理应收款项'},
            'finance.payables': {'name': '应付款管理', 'desc': '管理应付款项'},
            'finance.reports': {'name': '财务报表', 'desc': '查看财务报表'},
        }
    },
}


def get_all_permissions():
    """获取所有权限标识列表"""
    permissions = []
    for module_key, module in PERMISSION_MODULES.items():
        for perm_key in module['permissions']:
            permissions.append(perm_key)
    return permissions


def get_default_permissions():
    """获取管理员默认权限（全部权限）"""
    return get_all_permissions()


def get_operator_default_permissions():
    """获取操作员默认权限（移除电商对接、系统管理、财务管理）"""
    permissions = []
    for module_key, module in PERMISSION_MODULES.items():
        if module_key in ['platform', 'system', 'finance']:
            continue
        for perm_key in module['permissions']:
            permissions.append(perm_key)
    return permissions


class Role(db.Model):
    """角色模型"""
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 角色名称
    description = db.Column(db.String(200))  # 角色描述
    permissions = db.Column(db.Text, default='[]')  # 权限列表(JSON数组)
    is_system = db.Column(db.Boolean, default=False)  # 是否为系统内置角色（不可删除）
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联用户
    users = db.relationship('User', backref='user_role', lazy='dynamic')

    def get_permissions_list(self):
        """获取权限列表"""
        if not self.permissions:
            return []
        try:
            return json.loads(self.permissions)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_permissions_list(self, permissions_list):
        """设置权限列表"""
        self.permissions = json.dumps(permissions_list, ensure_ascii=False)

    def has_permission(self, permission_key):
        """检查是否拥有某个权限"""
        return permission_key in self.get_permissions_list()

    def __repr__(self):
        return f'<Role {self.name}>'
