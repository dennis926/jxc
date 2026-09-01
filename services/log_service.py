"""
操作日志服务模块
提供操作日志记录和查询功能
"""

from datetime import datetime
from flask import request, has_request_context, session
from models import db
from models.operation_log import OperationLog
import json


class LogService:
    """操作日志服务"""

    @staticmethod
    def log_operation(user_id, username, operation_type, module, description,
                      reference_type=None, reference_no=None, reference_id=None,
                      before_data=None, after_data=None):
        """
        记录操作日志
        
        Args:
            user_id: 用户ID
            username: 用户名
            operation_type: 操作类型 (login/logout/create/update/delete/import/export等)
            module: 模块名 (商品/仓库/库存/采购等)
            description: 操作描述
            reference_type: 关联类型 (order/po/transaction等)
            reference_no: 关联单号
            reference_id: 关联ID
            before_data: 操作前的数据 (字典或对象)
            after_data: 操作后的数据 (字典或对象)
        """
        # 处理数据序列化
        before_json = None
        after_json = None
        
        if before_data:
            try:
                if hasattr(before_data, 'to_dict'):
                    before_json = json.dumps(before_data.to_dict(), ensure_ascii=False)
                elif isinstance(before_data, dict):
                    before_json = json.dumps(before_data, ensure_ascii=False)
                else:
                    before_json = str(before_data)
            except:
                before_json = str(before_data)
        
        if after_data:
            try:
                if hasattr(after_data, 'to_dict'):
                    after_json = json.dumps(after_data.to_dict(), ensure_ascii=False)
                elif isinstance(after_data, dict):
                    after_json = json.dumps(after_data, ensure_ascii=False)
                else:
                    after_json = str(after_data)
            except:
                after_json = str(after_data)

        log = OperationLog(
            user_id=user_id,
            username=username,
            operation_type=operation_type,
            module=module,
            description=description,
            reference_type=reference_type,
            reference_no=reference_no,
            reference_id=reference_id,
            before_data=before_json,
            after_data=after_json
        )

        # 从request获取额外信息
        if has_request_context():
            log.ip_address = LogService.get_client_ip()
            log.user_agent = request.user_agent.string[:200] if request.user_agent else None
            log.request_url = request.url[:500] if request.url else None
            log.request_method = request.method

        try:
            # 添加到session并提交，确保日志实时写入数据库
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            # 如果提交失败，打印错误但不回滚（避免影响主业务操作）
            print(f"[LOG ERROR] 添加日志失败: {e}")
            pass

        return log

    @staticmethod
    def log_from_session(operation_type, module, description,
                         reference_type=None, reference_no=None, reference_id=None,
                         before_data=None, after_data=None):
        """
        从当前session记录操作日志
        
        Args:
            operation_type: 操作类型
            module: 模块名
            description: 操作描述
            reference_type: 关联类型
            reference_no: 关联单号
            reference_id: 关联ID
            before_data: 操作前的数据
            after_data: 操作后的数据
        """
        user_id = session.get('user_id')
        username = session.get('username')
        
        if not user_id or not username:
            return None
            
        return LogService.log_operation(
            user_id=user_id,
            username=username,
            operation_type=operation_type,
            module=module,
            description=description,
            reference_type=reference_type,
            reference_no=reference_no,
            reference_id=reference_id,
            before_data=before_data,
            after_data=after_data
        )

    @staticmethod
    def get_client_ip():
        """获取客户端IP地址"""
        if not has_request_context():
            return None

        # 尝试获取真实IP（考虑代理）
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request.headers.get('X-Real-IP'):
            return request.headers.get('X-Real-IP')
        else:
            return request.remote_addr

    @staticmethod
    def get_logs(page=1, per_page=20, user_id=None, username=None, operation_type=None,
                 module=None, start_date=None, end_date=None, reference_no=None):
        """
        查询操作日志
        
        Args:
            page: 页码
            per_page: 每页数量
            user_id: 用户ID筛选
            username: 用户名筛选
            operation_type: 操作类型筛选
            module: 模块筛选
            start_date: 开始日期
            end_date: 结束日期
            reference_no: 关联单号搜索
            
        Returns:
            分页对象
        """
        query = OperationLog.query

        if user_id:
            query = query.filter(OperationLog.user_id == user_id)

        if username:
            query = query.filter(OperationLog.username.like(f'%{username}%'))

        if operation_type:
            query = query.filter(OperationLog.operation_type == operation_type)

        if module:
            query = query.filter(OperationLog.module == module)

        if start_date:
            query = query.filter(OperationLog.created_at >= start_date)

        if end_date:
            # 结束日期包含当天，所以加一天
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
            from datetime import timedelta
            query = query.filter(OperationLog.created_at < end_datetime + timedelta(days=1))

        if reference_no:
            query = query.filter(OperationLog.reference_no.like(f'%{reference_no}%'))

        # 按创建时间倒序排列
        query = query.order_by(OperationLog.created_at.desc())

        return query.paginate(page=page, per_page=per_page, error_out=False)

    @staticmethod
    def get_user_recent_logs(user_id, limit=10):
        """获取用户最近的操作日志"""
        return OperationLog.query.filter_by(user_id=user_id)\
            .order_by(OperationLog.created_at.desc())\
            .limit(limit).all()

    @staticmethod
    def get_module_stats(start_date=None, end_date=None):
        """获取模块操作统计"""
        query = db.session.query(
            OperationLog.module,
            db.func.count(OperationLog.id).label('count')
        )

        if start_date:
            query = query.filter(OperationLog.created_at >= start_date)

        if end_date:
            from datetime import timedelta
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d') if isinstance(end_date, str) else end_date
            query = query.filter(OperationLog.created_at < end_datetime + timedelta(days=1))

        query = query.group_by(OperationLog.module)
        return query.all()

    @staticmethod
    def delete_old_logs(days=90):
        """删除指定天数之前的日志"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted = OperationLog.query.filter(OperationLog.created_at < cutoff_date).delete()
        db.session.commit()
        return deleted
