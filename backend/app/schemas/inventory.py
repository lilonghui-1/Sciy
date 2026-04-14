# -*- coding: utf-8 -*-
"""
库存数据模式

定义库存相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class InventorySnapshotResponse(BaseModel):
    """库存快照响应"""

    id: int
    product_id: int
    warehouse_id: int
    quantity_on_hand: int
    quantity_reserved: int
    quantity_available: int
    unit_cost: Decimal
    total_value: Decimal
    source: str
    extra_data: Optional[dict] = None
    timestamp: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InventoryTransactionCreate(BaseModel):
    """创建库存事务请求"""

    product_id: int = Field(..., description="产品ID")
    warehouse_id: int = Field(..., description="仓库ID")
    transaction_type: str = Field(..., description="事务类型: inbound/outbound/adjustment/transfer")
    quantity_change: int = Field(..., description="变动数量（正数入库，负数出库）")
    reference_no: Optional[str] = Field(default=None, max_length=50, description="关联单号")
    reason: Optional[str] = Field(default=None, description="变动原因")
    operator_id: Optional[int] = Field(default=None, description="操作人ID")
    extra_data: Optional[dict] = Field(default=None, description="扩展数据（JSON）")


class InventoryTransactionResponse(BaseModel):
    """库存事务响应"""

    id: int
    product_id: int
    warehouse_id: int
    transaction_type: str
    quantity_change: int
    quantity_before: int
    quantity_after: int
    reference_no: Optional[str] = None
    reason: Optional[str] = None
    operator_id: Optional[int] = None
    extra_data: Optional[dict] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InventoryOverviewResponse(BaseModel):
    """库存概览响应"""

    total_products: int = Field(description="产品总数")
    total_warehouses: int = Field(description="仓库总数")
    total_value: Decimal = Field(description="库存总价值")
    low_stock_count: int = Field(description="低库存产品数")
    out_of_stock_count: int = Field(description="缺货产品数")
    over_stock_count: int = Field(description="超库存产品数")
    total_transactions_today: int = Field(description="今日事务数")
    inbound_today: int = Field(description="今日入库数")
    outbound_today: int = Field(description="今日出库数")
