from flask import current_app
from apscheduler.schedulers.background import BackgroundScheduler
from services.backup_service import BackupService
import atexit
import os

class SchedulerService:
    _scheduler = None
    # 注册任务时绑定的 Flask 应用实例，供后台线程构建应用上下文
    _app = None

    @classmethod
    def bind_app(cls, app):
        """绑定 Flask 应用实例，供定时任务在无请求上下文时使用"""
        cls._app = app

    @classmethod
    def _shutdown(cls):
        """进程退出时关闭调度器（容错，避免退出阶段抛异常）"""
        scheduler = cls._scheduler
        if scheduler is not None and scheduler.running:
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                pass

    @classmethod
    def get_scheduler(cls):
        if cls._scheduler is None:
            cls._scheduler = BackgroundScheduler()
            cls._scheduler.start()
            # 注册程序退出时关闭调度器
            atexit.register(cls._shutdown)
        return cls._scheduler

    @classmethod
    def should_run_scheduler(cls):
        """判断当前进程是否应当运行定时任务

        多 worker 部署（如 gunicorn -w 2）下，每个 worker 都会执行
        create_app()，若各自注册定时任务，同一时刻备份会被执行多次
        （表现为备份历史中同一时间点出现多条记录）。

        通过环境变量 RUN_SCHEDULER 显式控制：
        - 未设置：默认开启，保持单进程开发/部署的原有行为
        - 设为 0/false/no：关闭，用于 gunicorn 的非主 worker
        """
        flag = os.environ.get('RUN_SCHEDULER')
        if flag is None:
            return True
        return flag.strip().lower() not in ('0', 'false', 'no', 'off')

    @classmethod
    def add_backup_job(cls, hour=2, minute=0):
        """添加每日备份任务，默认凌晨2点"""
        if not cls.should_run_scheduler():
            print("[定时备份] 当前进程已禁用调度器（RUN_SCHEDULER=0），跳过注册")
            return False

        scheduler = cls.get_scheduler()
        # 移除现有的备份任务
        cls.remove_backup_job()
        # 添加新任务
        # coalesce=True：进程暂停/积压后只补跑一次，不重复执行
        # max_instances=1：同一任务不允许并发执行
        scheduler.add_job(
            func=cls._run_backup_with_context,
            trigger='cron',
            hour=hour,
            minute=minute,
            id='daily_backup',
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600
        )
        return True

    @classmethod
    def _run_backup_with_context(cls):
        """在 Flask 应用上下文中执行备份任务

        关键：**所有数据库查询（含去重检查）必须在应用上下文内执行**。
        原实现把 BackupHistory.query 写在了 app_context 之外，后台线程中
        必然抛 "Working outside of application context" 并直接跳到 except，
        导致每日定时备份长期静默失败（备份历史不增长、也发不出备份邮件）。
        这里把全部作业逻辑收进内部函数 _job()，只在已建立上下文后调用。
        """
        from flask import has_app_context

        def _job():
            # 去重保护：60 秒内若已有成功备份记录，说明属重复触发，跳过
            from models.backup_history import BackupHistory
            from datetime import datetime, timedelta

            now = datetime.now()
            recent = BackupHistory.query.filter(
                BackupHistory.created_at >= now - timedelta(seconds=60),
                BackupHistory.status == 'success'
            ).first()
            if recent:
                print(f"[定时备份] 跳过：{recent.created_at} 已有备份记录 ({recent.filename})")
                return
            result = BackupService.backup_and_send('auto')
            print(f"[定时备份] 执行结果: {result}")

        try:
            if has_app_context():
                _job()
                return

            app = cls._app
            if app is None:
                print("[定时备份] 跳过：未绑定 Flask 应用实例")
                return

            with app.app_context():
                _job()
        except Exception as e:
            print(f"[定时备份] 执行失败: {e}")
            import traceback
            traceback.print_exc()

    @classmethod
    def remove_backup_job(cls):
        """移除备份任务"""
        scheduler = cls.get_scheduler()
        try:
            scheduler.remove_job('daily_backup')
        except:
            pass
        return True

    @classmethod
    def get_jobs(cls):
        """获取所有任务"""
        scheduler = cls.get_scheduler()
        return scheduler.get_jobs()

