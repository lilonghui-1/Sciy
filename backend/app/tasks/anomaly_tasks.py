# -*- coding: utf-8 -*-
"""
Celery 异常检测任务

提供定时触发的异常检测和告警通知 Celery 任务：
- run_anomaly_detection: 定时任务，运行告警引擎检测所有产品异常并触发通知
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import async_session_factory
from app.models.alert_event import AlertEvent
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.services.alert_engine import AlertEngine
from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.anomaly_tasks.run_anomaly_detection",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    track_started=True,
)
def run_anomaly_detection(self, check_type: str = "all") -> dict:
    """
    异常检测定时任务

    运行 AlertEngine 检查所有产品的告警规则，
    对触发的告警事件创建通知记录。

    流程：
    1. 运行 AlertEngine.check_all_products() 检测异常
    2. 对每个触发的告警事件创建站内通知
    3. 根据规则配置的通知渠道，创建对应的通知记录

    Args:
        check_type: 检查类型，默认 "all"
            - "all": 全量检查
            - "stockout": 仅检查缺货相关
            - "overstock": 仅检查积压相关

    Returns:
        任务执行摘要
    """
    logger.info("开始执行异常检测任务: check_type=%s", check_type)

    import asyncio

    async def _execute() -> dict:
        async with async_session_factory() as session:
            try:
                # 运行告警引擎
                engine = AlertEngine(session)
                events = await engine.check_all_products()

                if not events:
                    logger.info("未检测到异常，任务完成")
                    return {
                        "status": "completed",
                        "events_found": 0,
                        "notifications_created": 0,
                    }

                # 为每个告警事件创建通知
                notifications_created = 0
                notification_failures = 0

                for event in events:
                    try:
                        notif_count = await _create_notifications(session, event)
                        notifications_created += notif_count
                    except Exception as e:
                        logger.error(
                            "为事件 %d 创建通知失败: %s",
                            event.id, e,
                            exc_info=True,
                        )
                        notification_failures += 1

                await session.commit()

                summary = {
                    "status": "completed",
                    "check_type": check_type,
                    "events_found": len(events),
                    "notifications_created": notifications_created,
                    "notification_failures": notification_failures,
                    "event_ids": [evt.id for evt in events],
                }

                logger.info("异常检测任务完成: %s", summary)
                return summary

            except Exception as e:
                await session.rollback()
                logger.error("异常检测任务执行失败: %s", e, exc_info=True)
                raise

    try:
        result = asyncio.run(_execute())
        return result
    except Exception as exc:
        logger.error("异常检测任务异常: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


async def _create_notifications(
    session: AsyncSession,
    event: AlertEvent,
) -> int:
    """
    为告警事件创建通知记录

    根据告警事件关联的规则配置，创建对应渠道的通知记录。
    默认至少创建一条站内通知。

    Args:
        session: 数据库会话
        event: 告警事件

    Returns:
        创建的通知数量
    """
    # 获取关联的规则信息以确定通知渠道
    from app.models.alert_rule import AlertRule

    rule_stmt = select(AlertRule).where(AlertRule.id == event.rule_id)
    rule_result = await session.execute(rule_stmt)
    rule = rule_result.scalar_one_or_none()

    # 确定通知渠道
    channels = ["in_app"]  # 默认站内通知
    recipients: list[str] = []

    if rule is not None:
        rule_channels = rule.notify_channels
        if isinstance(rule_channels, list):
            channels = rule_channels
        elif isinstance(rule_channels, str):
            channels = [rule_channels]

        # 获取通知接收人
        notify_recipients = rule.notify_recipients
        if isinstance(notify_recipients, list) and notify_recipients:
            # 获取接收人的邮箱/手机号
            user_stmt = select(User).where(User.id.in_(notify_recipients))
            user_result = await session.execute(user_stmt)
            users = user_result.scalars().all()
            for user in users:
                if user.email:
                    recipients.append(user.email)

    created_count = 0

    for channel in channels:
        try:
            if channel == "in_app":
                # 站内通知 - recipient 为 "all" 表示广播
                notification = NotificationLog(
                    alert_event_id=event.id,
                    channel="in_app",
                    recipient="all",
                    subject=event.title,
                    body=event.message,
                    status="pending",
                )
                session.add(notification)
                created_count += 1

            elif channel == "email" and recipients:
                for recipient_email in recipients:
                    notification = NotificationLog(
                        alert_event_id=event.id,
                        channel="email",
                        recipient=recipient_email,
                        subject=f"[库存告警] {event.title}",
                        body=event.message,
                        status="pending",
                    )
                    session.add(notification)
                    created_count += 1

            elif channel == "webhook":
                from app.core.config import get_settings
                settings = get_settings()
                if settings.webhook_url:
                    notification = NotificationLog(
                        alert_event_id=event.id,
                        channel="webhook",
                        recipient=settings.webhook_url,
                        subject=event.title,
                        body=event.message,
                        status="pending",
                    )
                    session.add(notification)
                    created_count += 1

            elif channel == "sms" and recipients:
                for recipient_phone in recipients:
                    notification = NotificationLog(
                        alert_event_id=event.id,
                        channel="sms",
                        recipient=recipient_phone,
                        subject=event.title,
                        body=event.message,
                        status="pending",
                    )
                    session.add(notification)
                    created_count += 1

            else:
                logger.debug(
                    "跳过通知渠道 '%s'（无接收人或未实现）", channel,
                )

        except Exception as e:
            logger.error(
                "创建 %s 通知失败: event_id=%d, error=%s",
                channel, event.id, e,
            )

    logger.info(
        "事件 %d 创建了 %d 条通知记录", event.id, created_count,
    )
    return created_count
