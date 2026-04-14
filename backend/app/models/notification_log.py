from __future__ import annotations

# -*- coding: utf-8 -*-
"""
通知日志模型

记录所有告警通知的发送状态和历史，支持多种通知渠道。
"""

from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationLog(Base):
    """
    通知日志模型

    记录每条通知的发送过程和结果，支持重试机制。
    通知渠道：email（邮件）、sms（短信）、webhook（Webhook）、
    in_app（站内通知）、websocket（实时推送）。
    """

    __tablename__ = "notification_logs"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="日志ID",
    )

    # ==================== 关联信息 ====================
    alert_event_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="关联告警事件ID（可选）",
    )

    # ==================== 通知内容 ====================
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="通知渠道: email/sms/webhook/in_app/websocket",
    )
    recipient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="接收人",
    )
    subject: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="通知主题",
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="通知内容",
    )

    # ==================== 发送状态 ====================
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="状态: pending/sent/failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="重试次数",
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="发送时间",
    )

    # ==================== 时间戳 ====================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(id={self.id}, channel='{self.channel}', "
            f"recipient='{self.recipient}', status='{self.status}')>"
        )
