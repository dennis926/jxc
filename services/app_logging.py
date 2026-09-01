"""
应用日志服务模块
提供结构化日志记录、性能监控等功能
"""

import logging
import logging.handlers
import os
import time
from datetime import datetime
from flask import request, g, has_request_context
from functools import wraps


# 日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 日志文件路径
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)


def setup_logging(app):
    """配置应用日志"""
    # 设置日志级别
    log_level = logging.DEBUG if app.debug else logging.INFO
    
    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
    
    # 文件处理器 - 按天轮转
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, 'app.log'),
        when='midnight',
        interval=1,
        backupCount=30,  # 保留30天
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # 错误日志单独记录
    error_handler = logging.handlers.TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, 'error.log'),
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # 配置应用日志
    app.logger.handlers.clear()
    app.logger.setLevel(log_level)
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.addHandler(console_handler)
    
    return app.logger


class PerformanceMonitor:
    """性能监控中间件"""
    
    @staticmethod
    def before_request():
        """请求开始前记录时间"""
        g.start_time = time.time()
        g.request_id = f"{int(time.time() * 1000)}-{id(request)}"
    
    @staticmethod
    def after_request(response):
        """请求结束后计算耗时"""
        if hasattr(g, 'start_time'):
            elapsed = time.time() - g.start_time
            elapsed_ms = round(elapsed * 1000, 2)
            
            # 记录慢请求（超过1秒）
            if elapsed > 1:
                logging.warning(
                    f"慢请求: {request.method} {request.path} - "
                    f"耗时: {elapsed_ms}ms - "
                    f"状态码: {response.status_code}"
                )
            
            # 添加响应头显示请求耗时
            response.headers['X-Response-Time'] = f"{elapsed_ms}ms"
        
        return response
    
    @staticmethod
    def teardown_request(exception=None):
        """请求异常处理"""
        if exception:
            logging.error(
                f"请求异常: {request.method} {request.path} - "
                f"异常: {str(exception)}"
            )


def log_performance(func):
    """函数性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = round((time.time() - start) * 1000, 2)
            logging.debug(f"{func.__name__} 执行耗时: {elapsed}ms")
            return result
        except Exception as e:
            elapsed = round((time.time() - start) * 1000, 2)
            logging.error(f"{func.__name__} 执行失败 (耗时: {elapsed}ms): {str(e)}")
            raise
    return wrapper


class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name):
        self.logger = logging.getLogger(name)
    
    def _get_base_info(self):
        """获取基础信息"""
        info = {
            'timestamp': datetime.now().isoformat(),
        }
        if has_request_context():
            info.update({
                'path': request.path,
                'method': request.method,
                'ip': request.remote_addr,
            })
        return info
    
    def info(self, message, **kwargs):
        info = self._get_base_info()
        info.update(kwargs)
        self.logger.info(f"{message} | {info}")
    
    def warning(self, message, **kwargs):
        info = self._get_base_info()
        info.update(kwargs)
        self.logger.warning(f"{message} | {info}")
    
    def error(self, message, **kwargs):
        info = self._get_base_info()
        info.update(kwargs)
        self.logger.error(f"{message} | {info}")
    
    def debug(self, message, **kwargs):
        info = self._get_base_info()
        info.update(kwargs)
        self.logger.debug(f"{message} | {info}")


# 创建全局日志实例
app_logger = StructuredLogger('aijxc')
