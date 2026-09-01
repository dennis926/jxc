"""
API 限流配置模块
防止暴力破解、DDoS 攻击等
"""

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 创建限流器实例
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per day", "200 per hour", "60 per minute"],  # 默认限制放宽
    storage_uri="memory://",  # 使用内存存储，生产环境建议使用 Redis
)

# 预定义的限流策略
RATE_LIMITS = {
    # 登录接口：严格限制，防止暴力破解
    'login': '5 per minute',

    # API 接口：中等限制
    'api': '60 per minute',

    # 导出接口：宽松限制
    'export': '20 per minute',

    # 公共接口：基本限制
    'public': '120 per minute',
}
