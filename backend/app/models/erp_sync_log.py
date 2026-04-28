from __future__ import annotations

# -*- coding: utf-8 -*-
"""
ERP同步日志模型

记录与ERP系统之间的数据同步操作，包括全量同步和增量同步。
"""

from datetime import datetime

from sqlalchemy import String, Integer, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ErpSyncLog(Base):
    """
    ERP同步日志模型

    记录每次与ERP系统数据同步的详细信息，包括同步类型、方向、
    处理结果和错误信息，便于问题排查和数据审计。
    """

    __tablename__ = "erp_sync_logs"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="日志ID",
    )

    # ==================== 同步配置 ====================
    sync_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="同步类型: full/incremental",
    )
    direction: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="pull",
        comment="同步方向: pull/push",
    )
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="同步实体类型（如 product/inventory/order）",
    )

    # ==================== 同步状态 ====================
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running",
        comment="状态: running/success/failed",
    )
    records_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="已处理记录数",
    )
    records_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="失败记录数",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息",
    )

    # ==================== 请求与响应 ====================
    request_params: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="请求参数（JSON）",
    )
    response_summary: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="响应摘要（JSON）",
    )

    # ==================== 时间信息 ====================
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default="now()",
        comment="开始时间",
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="结束时间",
    )

    def __repr__(self) -> str:
        return (
            f"<ErpSyncLog(id={self.id}, type='{self.sync_type}', "
            f"direction='{self.direction}', status='{self.status}')>"
        )
