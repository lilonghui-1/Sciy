from __future__ import annotations

# -*- coding: utf-8 -*-
"""
告警规则模型

定义库存告警的触发规则，支持多种告警类型和通知渠道。
"""

from datetime import datetime

from sqlalchemy import String, Boolean, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class AlertRule(TimestampMixin, Base):
    """
    告警规则模型

    定义库存告警的触发条件和通知配置。
    支持的告警类型：stockout（缺货）、overstock（积压）、
    delay（延迟）、turnover（周转率）、custom（自定义）。
    """

    __tablename__ = "alert_rules"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="规则ID",
    )

    # ==================== 基本信息 ====================
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="规则名称",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="规则描述",
    )

    # ==================== 规则配置 ====================
    rule_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="规则类型: stockout/overstock/delay/turnover/custom",
    )
    conditions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="触发条件（JSON）",
    )

    # ==================== 通知配置 ====================
    notify_channels: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: ["in_app"],
        comment="通知渠道（JSON数组）",
    )
    notify_recipients: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="通知接收人ID列表（JSON数组）",
    )

    # ==================== 规则状态 ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="medium",
        comment="优先级: low/medium/high/critical",
    )
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3600,
        comment="冷却时间（秒）",
    )

    # ==================== 创建人 ====================
    creator_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        comment="创建人ID",
    )

    # ==================== 关系 ====================
    creator: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="alert_rules",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<AlertRule(id={self.id}, name='{self.name}', "
            f"type='{self.rule_type}', priority='{self.priority}')>"
        )
