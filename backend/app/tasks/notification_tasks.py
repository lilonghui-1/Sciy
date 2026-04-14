# -*- coding: utf-8 -*-
"""
通知 Celery 异步任务

提供告警通知的异步任务处理：
- send_notification_task: 单条告警事件通知任务
- send_batch_notifications_task: 批量告警事件通知任务

所有任务支持指数退避重试机制，确保在网络波动等临时故障场景下
最终能够成功发送通知。
"""

import asyncio
import logging

from sqlalchemy import select

from app.db.engine import async_session_factory
from app.models.alert_event import AlertEvent
from app.services.notification_service import NotificationService
from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.notification_tasks.send_notification_task",
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    acks_late=True,
    track_started=True,
)
def send_notification_task(self, alert_event_id: int) -> dict:
    """
    单条告警事件通知发送任务。

    根据告警事件ID查询事件详情，然后调用 NotificationService
    通过各配置渠道发送通知。失败时使用指数退避策略重试。

    重试延迟策略: 60s, 120s, 240s, 480s, 960s（指数退避）

    Args:
        alert_event_id: 告警事件ID

    Returns:
        任务执行结果摘要
    """
    logger.info("开始处理通知任务: alert_event_id=%d", alert_event_id)

    async def _execute() -> dict:
        async with async_session_factory() as session:
            try:
                # 查询告警事件
                stmt = select(AlertEvent).where(AlertEvent.id == alert_event_id)
                result = await session.execute(stmt)
                event = result.scalar_one_or_none()

                if event is None:
                    logger.error(
                        "告警事件不存在: alert_event_id=%d", alert_event_id
                    )
                    return {
                        "status": "error",
                        "error": "event_not_found",
                        "alert_event_id": alert_event_id,
                    }

                # 调用通知服务发送通知
                notification_service = NotificationService(session)
                send_result = await notification_service.send_alert(event)

                await session.commit()

                logger.info(
                    "通知任务完成: alert_event_id=%d, result=%s",
                    alert_event_id,
                    str(send_result.get("status", "unknown")),
                )

                return {
                    "status": send_result.get("status", "unknown"),
                    "alert_event_id": alert_event_id,
                    "results": send_result.get("results", {}),
                }

            except Exception as e:
                await session.rollback()
                logger.error(
                    "通知任务执行失败: alert_event_id=%d, 错误=%s",
                    alert_event_id,
                    str(e),
                    exc_info=True,
                )
                raise

    try:
        result = asyncio.run(_execute())
        return result
    except Exception as exc:
        # 指数退避重试: countdown = default_retry_delay * 2^(retry_count)
        retry_count = self.request.retries
        countdown = 60 * (2 ** retry_count)
        max_countdown = 960  # 最大延迟 16 分钟

        if countdown > max_countdown:
            countdown = max_countdown

        logger.warning(
            "通知任务将重试: alert_event_id=%d, retry=%d/%d, countdown=%ds, 错误=%s",
            alert_event_id,
            retry_count + 1,
            self.max_retries,
            countdown,
            str(exc),
        )

        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(
    name="app.tasks.notification_tasks.send_batch_notifications_task",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
    track_started=True,
)
def send_batch_notifications_task(
    self, alert_event_ids: list[int]
) -> dict:
    """
    批量告警事件通知发送任务。

    根据告警事件ID列表批量查询事件详情，然后调用 NotificationService
    的 send_batch 方法批量发送通知。失败时使用指数退避策略重试。

    重试延迟策略: 120s, 240s, 480s（指数退避）

    Args:
        alert_event_ids: 告警事件ID列表

    Returns:
        批量任务执行结果摘要
    """
    if not alert_event_ids:
        logger.warning("批量通知任务收到空的 alert_event_ids 列表")
        return {"status": "skipped", "reason": "no_event_ids"}

    logger.info(
        "开始处理批量通知任务: 事件数=%d, IDs=%s",
        len(alert_event_ids),
        alert_event_ids,
    )

    async def _execute() -> dict:
        async with async_session_factory() as session:
            try:
                # 批量查询告警事件
                stmt = select(AlertEvent).where(
                    AlertEvent.id.in_(alert_event_ids)
                )
                result = await session.execute(stmt)
                events = list(result.scalars().all())

                if not events:
                    logger.warning(
                        "批量通知任务: 未找到任何告警事件, IDs=%s",
                        alert_event_ids,
                    )
                    return {
                        "status": "skipped",
                        "reason": "no_events_found",
                        "requested_ids": alert_event_ids,
                    }

                # 检查是否有未找到的事件
                found_ids = {e.id for e in events}
                missing_ids = set(alert_event_ids) - found_ids
                if missing_ids:
                    logger.warning(
                        "批量通知任务: 部分事件未找到, missing_ids=%s",
                        list(missing_ids),
                    )

                # 调用通知服务批量发送
                notification_service = NotificationService(session)
                batch_result = await notification_service.send_batch(events)

                await session.commit()

                summary = {
                    "status": batch_result.get("status", "unknown"),
                    "requested": len(alert_event_ids),
                    "found": len(events),
                    "missing": len(missing_ids),
                    "success": batch_result.get("success", 0),
                    "failed": batch_result.get("failed", 0),
                    "skipped": batch_result.get("skipped", 0),
                }

                logger.info(
                    "批量通知任务完成: %s",
                    str(summary),
                )

                return summary

            except Exception as e:
                await session.rollback()
                logger.error(
                    "批量通知任务执行失败: 错误=%s",
                    str(e),
                    exc_info=True,
                )
                raise

    try:
        result = asyncio.run(_execute())
        return result
    except Exception as exc:
        # 指数退避重试
        retry_count = self.request.retries
        countdown = 120 * (2 ** retry_count)
        max_countdown = 480  # 最大延迟 8 分钟

        if countdown > max_countdown:
            countdown = max_countdown

        logger.warning(
            "批量通知任务将重试: retry=%d/%d, countdown=%ds, 错误=%s",
            retry_count + 1,
            self.max_retries,
            countdown,
            str(exc),
        )

        raise self.retry(exc=exc, countdown=countdown)
