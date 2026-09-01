"""
WSGI 入口文件 - 用于 gunicorn/uwsgi 部署
启动命令: gunicorn -w 4 -b 127.0.0.1:5001 wsgi:application
"""
from app import create_app

application = create_app()

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=5001)
