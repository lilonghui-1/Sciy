from __future__ import annotations

# -*- coding: utf-8 -*-
"""
库存事务模型

记录所有库存变动操作，包括入库、出库、调整和调拨。
以时间维度存储和查询历史事务数据，支持达梦数据库 DM8。
"""

from datetime import datetime

from sqlalchemy import (
    String, Integer, Text, DateTime, ForeignKey, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventoryTransaction(Base):
    """
    库存事务模型

    记录每次库存变动的详细信息，包括变动前后数量、操作类型和操作人。
    """

    __tablename__ = "inventory_transactions"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="事务ID",
    )

    # ==================== 关联信息 ====================
    product_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
        index=True,
        comment="产品ID",
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("warehouses.id"),
        nullable=False,
        index=True,
        comment="仓库ID",
    )

    # ==================== 事务信息 ====================
    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="事务类型: inbound/outbound/adjustment/transfer",
    )
    quantity_change: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="变动数量（正数入库，负数出库）",
    )
    quantity_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="变动前数量",
    )
    quantity_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="变动后数量",
    )

    # ==================== 引用与原因 ====================
    reference_no: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="参考单号",
    )
    batch_no: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="批次号",
    )
    expiry_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="有效期",
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="变动原因",
    )

    # ==================== 操作人 ====================
    operator_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        comment="操作人ID",
    )

    # ==================== 扩展数据 ====================
    extra_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="扩展数据（JSON）",
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
            f"<InventoryTransaction(id={self.id}, "
            f"type='{self.transaction_type}', "
            f"product_id={self.product_id}, change={self.quantity_change})>"
        )
