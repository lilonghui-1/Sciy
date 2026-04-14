# -*- coding: utf-8 -*-
"""
需求预测数据模式

定义预测相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ForecastResponse(BaseModel):
    """预测响应"""

    id: int
    product_id: int
    warehouse_id: Optional[int] = None
    forecast_date: Optional[datetime] = None
    predicted_demand: Decimal
    predicted_demand_lower: Optional[Decimal] = None
    predicted_demand_upper: Optional[Decimal] = None
    model_name: str
    model_params: Optional[dict] = None
    accuracy_mape: Optional[float] = None
    safety_stock: Optional[Decimal] = None
    reorder_point: Optional[Decimal] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ForecastRunRequest(BaseModel):
    """运行预测请求"""

    product_id: int = Field(..., description="产品ID")
    warehouse_id: Optional[int] = Field(default=None, description="仓库ID")
    forecast_days: int = Field(default=30, ge=1, le=365, description="预测天数")
    model_name: str = Field(default="baseline", description="模型名称")


class BatchForecastRequest(BaseModel):
    """批量预测请求"""

    product_ids: list[int] = Field(..., min_length=1, description="产品ID列表")
    warehouse_id: Optional[int] = Field(default=None, description="仓库ID")
    forecast_days: int = Field(default=30, ge=1, le=365, description="预测天数")
    model_name: str = Field(default="baseline", description="模型名称")


class SafetyStockResponse(BaseModel):
    """安全库存响应"""

    product_id: int
    warehouse_id: Optional[int] = None
    current_stock: int = Field(description="当前库存")
    safety_stock: Decimal = Field(description="建议安全库存")
    reorder_point: Decimal = Field(description="建议再订购点")
    avg_daily_demand: Decimal = Field(description="平均日需求量")
    demand_std_dev: Decimal = Field(description="需求标准差")
    lead_time_days: int = Field(description="补货提前期(天)")
    service_level: Decimal = Field(default=Decimal("0.95"), description="服务水平")
