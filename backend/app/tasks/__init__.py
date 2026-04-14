"""
Celery 异步任务队列模块

提供 Celery 应用实例和定时任务调度配置。

定时任务包括：
- 库存需求预测（每 6 小时执行一次）
- 库存异常检测（每 30 分钟执行一次）
- ERP 数据同步（每 30 分钟执行一次）
"""

import logging
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ==================== Celery 应用工厂 ====================


def create_celery_app() -> Celery:
    """
    创建并配置 Celery 应用实例

    配置包括：
    - 消息代理（Redis）
    - 结果后端（Redis）
    - 任务序列化格式
    - 任务路由
    - 定时任务调度

    Returns:
        Celery: 配置完成的 Celery 应用实例
    """
    settings = get_settings()

    celery_app = Celery(
        "inventory_tasks",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=[
            "app.tasks.forecast_tasks",      # 需求预测任务
            "app.tasks.anomaly_tasks",       # 异常检测任务
            "app.tasks.erp_sync_tasks",      # ERP 同步任务
            "app.tasks.notification_tasks",  # 通知发送任务
        ],
    )

    # Celery 核心配置
    celery_app.conf.update(
        # 序列化配置 - 使用 JSON 确保跨语言兼容性
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,

        # 任务结果配置
        result_expires=timedelta(hours=24).total_seconds(),
        result_extended=True,

        # 任务执行配置
        task_track_started=True,
        task_acks_late=True,           # 任务执行完成后才确认
        task_reject_on_worker_lost=True,  # Worker 异常退出时拒绝任务
        worker_prefetch_multiplier=1,  # 每次只预取一个任务，避免阻塞

        # 重试配置
        task_default_retry_delay=60,   # 默认重试延迟 60 秒
        task_max_retries=3,            # 默认最大重试次数

        # 任务路由 - 不同类型的任务使用不同的队列
        task_routes={
            "app.tasks.forecast_tasks.*": {"queue": "forecast"},
            "app.tasks.anomaly_tasks.*": {"queue": "anomaly"},
            "app.tasks.erp_sync_tasks.*": {"queue": "erp_sync"},
            "app.tasks.notification_tasks.*": {"queue": "notifications"},
        },

        # 队列定义
        task_queues={
            "celery": {},
            "forecast": {},
            "anomaly": {},
            "erp_sync": {},
            "notifications": {},
        },

        # Beat 定时任务调度配置
        beat_schedule={
            # 库存需求预测 - 每 6 小时执行一次
            "run-inventory-forecast": {
                "task": "app.tasks.forecast_tasks.run_daily_forecast",
                "schedule": crontab(minute=0, hour="*/6"),  # 0:00, 6:00, 12:00, 18:00
                "options": {
                    "queue": "forecast",
                    "expires": timedelta(hours=2).total_seconds(),
                },
            },
            # 库存异常检测 - 每 30 分钟执行一次
            "run-anomaly-detection": {
                "task": "app.tasks.anomaly_tasks.run_anomaly_detection",
                "schedule": crontab(minute="*/30"),  # 每小时的第 0 和 30 分钟
                "options": {
                    "queue": "anomaly",
                    "expires": timedelta(minutes=25).total_seconds(),
                },
            },
            # ERP 数据同步 - 每 30 分钟执行一次
            "run-erp-sync": {
                "task": "app.tasks.erp_sync_tasks.run_erp_sync",
                "schedule": crontab(minute="*/30"),  # 每小时的第 0 和 30 分钟
                "kwargs": {
                    "sync_type": "incremental",
                },
                "options": {
                    "queue": "erp_sync",
                    "expires": timedelta(minutes=25).total_seconds(),
                },
            },
        },
    )

    return celery_app


# 创建全局 Celery 应用实例
celery_app = create_celery_app()
