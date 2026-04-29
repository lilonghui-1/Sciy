# -*- coding: utf-8 -*-
"""
库存分析数据模式

定义库存分析相关的请求/响应模式。
"""

from typing import Optional
from decimal import Decimal

from pydantic import BaseModel, Field


class AgingTierItem(BaseModel):
    """库龄分层项"""

    tier: str = Field(description="分层标识: normal/attention/slow_moving")
    tier_label: str = Field(description="分层标签")
    quantity: int = Field(description="库存数量")
    value: Decimal = Field(description="库存金额")
    percentage: float = Field(description="占比(%)")


class AgingAnalysisResponse(BaseModel):
    """库龄分析响应"""

    tiers: list[AgingTierItem]
    total_quantity: int
    total_value: Decimal
    product_id: Optional[int] = None
    warehouse_id: Optional[int] = None


class TurnoverAnalysisResponse(BaseModel):
    """周转分析响应"""

    product_id: int
    warehouse_id: int
    turnover_days: float = Field(description="周转天数")
    avg_inventory: float = Field(description="平均库存")
    avg_daily_outbound: float = Field(description="日均出库量")
    total_outbound_period: int = Field(description="期间总出库量")
    period_days: int = Field(description="统计周期(天)")
    annual_turnover_rate: float = Field(description="年化周转率")


class ABCClassificationItem(BaseModel):
    """ABC分类项"""

    product_id: int
    warehouse_id: int
    total_value: float
    cumulative_percentage: float = Field(description="累计金额占比(%)")
    abc_class: str = Field(description="ABC分类: A/B/C")


class InventoryHealthResponse(BaseModel):
    """库存健康指数响应"""

    health_index: float = Field(description="健康指数(0-1)")
    total_value: float
    slow_moving_value: float
    slow_moving_ratio: float
    attention_value: float
    attention_ratio: float
    normal_ratio: float
    warehouse_id: Optional[int] = None


class SlowMovingItem(BaseModel):
    """呆滞物料项"""

    product_id: int
    warehouse_id: int
    quantity: int
    value: float
    age_days: int
    aging_tier: str


class OverstockItem(BaseModel):
    """超储物料项"""

    product_id: int
    warehouse_id: int
    quantity: int
    value: float
    product_type: str
    days_of_stock: float
    threshold: int
