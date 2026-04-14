from __future__ import annotations

# -*- coding: utf-8 -*-
"""
产品模型

管理产品/商品的基本信息，包括SKU、定价、供应商关联等。
"""

from datetime import datetime

from sqlalchemy import String, Boolean, Numeric, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Product(TimestampMixin, Base):
    """
    产品模型

    存储产品的基本信息、定价和供应商关联。
    包含安全库存和补货提前期等库存管理参数。
    """

    __tablename__ = "products"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="产品ID",
    )

    # ==================== 标识信息 ====================
    sku: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="SKU编码",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="产品名称",
    )
    barcode: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
        comment="条形码",
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="产品分类",
    )
    erp_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="ERP系统编码",
    )

    # ==================== 计量与定价 ====================
    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="个",
        comment="计量单位",
    )
    unit_cost: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="单位成本",
    )
    selling_price: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="销售单价",
    )

    # ==================== 供应商关联 ====================
    supplier_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("suppliers.id"),
        nullable=False,
        index=True,
        comment="供应商ID",
    )

    # ==================== 库存管理参数 ====================
    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="补货提前期（天）",
    )
    safety_stock_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=14,
        comment="安全库存天数",
    )

    # ==================== 状态 ====================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )

    # ==================== 关系 ====================
    supplier: Mapped["Supplier"] = relationship(  # noqa: F821
        "Supplier",
        back_populates="products",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}')>"
