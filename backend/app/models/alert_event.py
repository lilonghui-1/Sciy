from __future__ import annotations

# -*- coding: utf-8 -*-
"""
告警事件模型

记录由告警规则触发的具体告警事件，包含状态跟踪和处理信息。
"""

from datetime import datetime

from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlertEvent(Base):
    """
    告警事件模型

    记录每次告警规则触发的具体事件，支持状态流转：
    new（新告警）-> acknowledged（已确认）-> resolved（已解决）。
    """

    __tablename__ = "alert_events"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="事件ID",
    )

    # ==================== 关联信息 ====================
    rule_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("alert_rules.id"),
        nullable=False,
        index=True,
        comment="告警规则ID",
    )
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="规则名称（冗余存储，避免规则删除后丢失）",
    )
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
        index=True,
        comment="产品ID",
    )
    warehouse_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("warehouses.id"),
        nullable=True,
        comment="仓库ID（可选）",
    )

    # ==================== 告警内容 ====================
    severity: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="严重程度: low/medium/high/critical",
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="告警标题",
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="告警详情",
    )

    # ==================== 数值信息 ====================
    current_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="当前值",
    )
    threshold_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="阈值",
    )

    # ==================== 上下文数据 ====================
    context_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="上下文数据（JSON）",
    )

    # ==================== 状态跟踪 ====================
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
        comment="状态: new/acknowledged/resolved",
    )
    acknowledged_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        comment="确认人ID",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="解决时间",
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
            f"<AlertEvent(id={self.id}, title='{self.title}', "
            f"severity='{self.severity}', status='{self.status}')>"
        )
