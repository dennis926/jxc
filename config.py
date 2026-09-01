import os
import secrets

# 获取项目根目录
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 密钥文件路径
SECRET_KEY_FILE = os.path.join(BASE_DIR, '.secret_key')


def get_secret_key():
    """获取或生成持久化的 SECRET_KEY"""
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, 'r') as f:
            key = f.read().strip()
            if key:
                return key
    # 生成新的密钥并保存
    key = secrets.token_hex(32)
    try:
        with open(SECRET_KEY_FILE, 'w') as f:
            f.write(key)
    except IOError:
        pass  # 如果无法写入文件，使用临时密钥
    return key


class Config:
    """应用配置类"""

    # 安全密钥（持久化存储，重启不会变化）
    SECRET_KEY = get_secret_key()

    # 数据库配置（固定使用 SQLite，适合宝塔一键部署）
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'inventory.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SQLite 连接池配置
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,      # 连接前检查可用性
        'pool_recycle': 1800,       # 30分钟回收连接
        'connect_args': {
            'check_same_thread': False,  # 允许多线程访问
            'timeout': 30               # 连接超时30秒
        }
    }

    # Session 安全配置
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'  # 生产环境启用HTTPS-only Cookie
    PERMANENT_SESSION_LIFETIME = 86400  # 24小时

    # 分页配置
    PER_PAGE = 15

    # 缓存配置（2H2G 服务器优化：使用文件缓存替代内存缓存，降低内存占用）
    CACHE_TYPE = 'FileSystemCache'  # 文件缓存，适合低内存服务器
    CACHE_DEFAULT_TIMEOUT = 300  # 默认缓存5分钟
    CACHE_DIR = os.path.join(BASE_DIR, '.cache')  # 缓存目录

    # ===== 平台API配置（预留） =====

    # 淘宝API配置
    TAOBAO_APP_KEY = ''
    TAOBAO_APP_SECRET = ''
    TAOBAO_SESSION = ''
    TAOBAO_SANDBOX = False

    # 京东API配置
    JD_APP_KEY = ''
    JD_APP_SECRET = ''
    JD_ACCESS_TOKEN = ''
    JD_SANDBOX = False

    # 抖音API配置
    DOUYIN_APP_KEY = ''
    DOUYIN_APP_SECRET = ''
    DOUYIN_ACCESS_TOKEN = ''
    DOUYIN_SANDBOX = False

    # 拼多多API配置
    PDD_CLIENT_ID = ''
    PDD_CLIENT_SECRET = ''
    PDD_ACCESS_TOKEN = ''
    PDD_SANDBOX = False
