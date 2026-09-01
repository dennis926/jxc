"""清理临时表"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import text
from app import create_app
from models.database import db

app = create_app()
with app.app_context():
    conn = db.engine.connect()
    conn.execute(text('DROP TABLE IF EXISTS stock_transactions_new'))
    conn.commit()
    print('Cleanup done')