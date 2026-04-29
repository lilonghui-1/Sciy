from __future__ import annotations

# -*- coding: utf-8 -*-
"""
需求预测模型

存储基于机器学习模型的库存需求预测结果。
"""

from datetime import datetime

from sqlalchemy import (
    String, Integer, Float, Numeric, DateTime, ForeignKey, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DemandForecast(Base):
    """
    需求预测模型

    存储每个产品在特定仓库和日期的预测需求数据，
    包括预测区间、模型信息和安全库存建议。
    """

    __tablename__ = "demand_forecasts"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="预测ID",
    )

    # ==================== 关联信息 ====================
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
        comment="仓库ID（可选，为空表示全局预测）",
    )

    # ==================== 预测时间 ====================
    forecast_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="预测目标日期",
    )

    # ==================== 预测结果 ====================
    predicted_demand: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="预测需求量",
    )
    predicted_demand_lower: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="预测需求下限",
    )
    predicted_demand_upper: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="预测需求上限",
    )

    # ==================== 模型信息 ====================
    model_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="模型名称",
    )
    model_params: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="模型参数（JSON）",
    )
    accuracy_mape: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="模型精度（MAPE）",
    )

    # ==================== 库存建议 ====================
    safety_stock: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="建议安全库存",
    )
    reorder_point: Mapped[float | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
        comment="建议再订货点",
    )

    product_type: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="产品类型: raw_material/finished_good",
    )
    calculation_basis: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="计算基础: consumption(耗用)/sales(销售)",
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
            f"<DemandForecast(id={self.id}, product_id={self.product_id}, "
            f"date={self.forecast_date}, demand={self.predicted_demand})>"
        )
