from models.database import db
from datetime import datetime

class BackupHistory(db.Model):
    __tablename__ = 'backup_history'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    file_size = db.Column(db.Integer)  # 文件大小（字节）
    backup_type = db.Column(db.String(20), default='manual')  # manual/auto
    status = db.Column(db.String(20), default='success')  # success/failed
    error_message = db.Column(db.Text)
    sent_to_email = db.Column(db.Boolean, default=False)
    email_status = db.Column(db.String(20))  # sent/failed
    created_at = db.Column(db.DateTime, default=datetime.now)
