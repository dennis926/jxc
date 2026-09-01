from models import db
from datetime import datetime


class FormConfig(db.Model):
    """表单配置模型"""
    __tablename__ = 'form_config'

    id = db.Column(db.Integer, primary_key=True)
    form_code = db.Column(db.String(50), unique=True, nullable=False, comment='表单代码，唯一标识')
    form_name = db.Column(db.String(100), nullable=False, comment='表单名称')
    description = db.Column(db.Text, comment='描述')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    company_name = db.Column(db.String(200), comment='公司名称（用于随货同行单等打印）')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    created_by = db.Column(db.Integer, comment='创建人ID')

    # 关联字段配置
    fields = db.relationship('FormFieldConfig', backref='form_config', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<FormConfig {self.form_code}>'

    def to_dict(self):
        return {
            'id': self.id,
            'form_code': self.form_code,
            'form_name': self.form_name,
            'description': self.description,
            'is_active': self.is_active,
            'company_name': self.company_name,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }


class FormFieldConfig(db.Model):
    """表单字段配置模型"""
    __tablename__ = 'form_field_config'

    id = db.Column(db.Integer, primary_key=True)
    form_config_id = db.Column(db.Integer, db.ForeignKey('form_config.id'), nullable=False, comment='表单配置ID')
    field_code = db.Column(db.String(50), nullable=False, comment='字段代码')
    field_name = db.Column(db.String(100), nullable=False, comment='字段名称（表头）')
    field_type = db.Column(db.String(50), default='text', comment='字段类型：text, number, date, select等')
    is_visible = db.Column(db.Boolean, default=True, comment='是否显示')
    is_required = db.Column(db.Boolean, default=False, comment='是否必填')
    sort_order = db.Column(db.Integer, default=0, comment='排序')
    default_value = db.Column(db.String(255), comment='默认值')
    options = db.Column(db.Text, comment='选项（JSON格式，用于select类型）')
    created_at = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    __table_args__ = (
        db.UniqueConstraint('form_config_id', 'field_code', name='unique_form_field'),
    )

    def __repr__(self):
        return f'<FormFieldConfig {self.form_config_id}.{self.field_code}>'

    def to_dict(self):
        return {
            'id': self.id,
            'form_config_id': self.form_config_id,
            'field_code': self.field_code,
            'field_name': self.field_name,
            'field_type': self.field_type,
            'is_visible': self.is_visible,
            'is_required': self.is_required,
            'sort_order': self.sort_order,
            'default_value': self.default_value,
            'options': self.options
        }
