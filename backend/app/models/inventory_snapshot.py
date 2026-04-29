from __future__ import annotations

# -*- coding: utf-8 -*-
"""
库存快照模型

记录每个产品在每个仓库的库存状态快照。
以时间维度存储和查询历史库存数据，支持达梦数据库 DM8。
"""

from datetime import datetime

from sqlalchemy import (
    String, Integer, Numeric, DateTime, ForeignKey, Index, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InventorySnapshot(Base):
    """
    库存快照模型

    记录特定时间点的库存数量和金额信息。
    """

    __tablename__ = "inventory_snapshots"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="快照ID",
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

    # ==================== 库存数量 ====================
    quantity_on_hand: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="在手数量",
    )
    quantity_reserved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="预留数量",
    )
    quantity_available: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="可用数量",
    )

    # ==================== 金额信息 ====================
    unit_cost: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="单位成本",
    )
    total_value: Mapped[float] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        comment="库存总价值",
    )

    # ==================== 来源与扩展 ====================
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        comment="数据来源: manual/erp/import",
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
        comment="有效期",
    )
    age_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="库龄（天）",
    )
    aging_tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="normal",
        comment="库龄分层: normal(0-30天)/attention(31-90天)/slow_moving(90天以上)",
    )
    extra_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="扩展数据（JSON）",
    )

    # ==================== 时间戳 ====================
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        server_default="now()",
        comment="快照时间",
    )

    # ==================== 索引 ====================
    __table_args__ = (
        Index(
            "ix_inventory_snapshots_product_warehouse_timestamp",
            "product_id",
            "warehouse_id",
            "timestamp",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<InventorySnapshot(id={self.id}, "
            f"product_id={self.product_id}, warehouse_id={self.warehouse_id}, "
            f"qty={self.quantity_on_hand}, timestamp={self.timestamp})>"
        )
