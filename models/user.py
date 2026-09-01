"""
用户模型
"""

import re
from models.database import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


def validate_password_strength(password):
    """
    验证密码强度
    要求：
    - 至少8个字符
    - 包含大写字母
    - 包含小写字母
    - 包含数字
    - 包含特殊字符
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if len(password) < 8:
        return False, '密码长度至少8位'
    
    if not re.search(r'[A-Z]', password):
        return False, '密码必须包含大写字母'
    
    if not re.search(r'[a-z]', password):
        return False, '密码必须包含小写字母'
    
    if not re.search(r'\d', password):
        return False, '密码必须包含数字'
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, '密码必须包含特殊字符 (!@#$%^&* 等)'
    
    return True, None


class User(db.Model):
    """用户模型"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    real_name = db.Column(db.String(80))  # 真实姓名
    role = db.Column(db.String(20), default='user')  # admin/user (保留兼容)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)  # 关联角色表
    is_active = db.Column(db.Boolean, default=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    force_change_password = db.Column(db.Boolean, default=False)  # 强制修改密码标记
    password_changed_at = db.Column(db.DateTime, nullable=True)  # 密码修改时间
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def set_password(self, password):
        """设置密码（加密存储）"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """校验密码"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'
