# -*- coding: utf-8 -*-
"""
库存分析路由

提供库龄分析、周转分析、ABC分类、库存健康指数等API端点。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.schemas.inventory_analysis import (
    AgingAnalysisResponse,
    TurnoverAnalysisResponse,
    ABCClassificationItem,
    InventoryHealthResponse,
    SlowMovingItem,
    OverstockItem,
)
from app.services.inventory_analysis_service import InventoryAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory/analysis", tags=["库存分析"])


@router.get("/aging", response_model=AgingAnalysisResponse, summary="库龄分析")
async def get_aging_analysis(
    product_id: Optional[int] = Query(default=None, description="产品ID"),
    warehouse_id: Optional[int] = Query(default=None, description="仓库ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AgingAnalysisResponse:
    """
    按库龄分层统计库存数量和金额

    库龄分层规则：
    - normal: 0-30天（正常周转）
    - attention: 31-90天（需关注）
    - slow_moving: 90天以上（呆滞/慢周转）
    """
    service = InventoryAnalysisService(db)
    result = await service.analyze_aging(
        product_id=product_id,
        warehouse_id=warehouse_id,
    )
    return AgingAnalysisResponse(**result)


@router.get("/turnover", response_model=TurnoverAnalysisResponse, summary="周转分析")
async def get_turnover_analysis(
    product_id: int = Query(..., description="产品ID"),
    warehouse_id: int = Query(..., description="仓库ID"),
    days: int = Query(default=90, ge=1, le=365, description="统计周期(天)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> TurnoverAnalysisResponse:
    """
    计算指定产品的周转天数和年化周转率

    周转天数 = 平均库存 / 日均出库量
    年化周转率 = 365 / 周转天数
    """
    service = InventoryAnalysisService(db)
    result = await service.calculate_turnover_days(
        product_id=product_id,
        warehouse_id=warehouse_id,
        days=days,
    )
    return TurnoverAnalysisResponse(**result)


@router.get("/abc-classification", response_model=list[ABCClassificationItem], summary="ABC分类")
async def get_abc_classification(
    warehouse_id: Optional[int] = Query(default=None, description="仓库ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ABCClassificationItem]:
    """
    基于库存金额的ABC分类

    - A类: 累计金额占比 0-80%（重点管理）
    - B类: 累计金额占比 80-95%（一般管理）
    - C类: 累计金额占比 95-100%（简化管理）
    """
    service = InventoryAnalysisService(db)
    items = await service.abc_classification(warehouse_id=warehouse_id)
    return [ABCClassificationItem(**item) for item in items]


@router.get("/health", response_model=InventoryHealthResponse, summary="库存健康指数")
async def get_inventory_health(
    warehouse_id: Optional[int] = Query(default=None, description="仓库ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> InventoryHealthResponse:
    """
    综合评估库存健康指数

    健康指数 = 1 - (呆滞金额占比 × 0.7 + 关注金额占比 × 0.3)
    范围: 0-1，越高越健康，建议 > 0.85
    """
    service = InventoryAnalysisService(db)
    result = await service.get_inventory_health_index(warehouse_id=warehouse_id)
    return InventoryHealthResponse(**result)


@router.get("/slow-moving", response_model=list[SlowMovingItem], summary="呆滞物料")
async def get_slow_moving_products(
    warehouse_id: Optional[int] = Query(default=None, description="仓库ID"),
    days_threshold: int = Query(default=90, ge=1, description="库龄阈值(天)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[SlowMovingItem]:
    """
    识别呆滞物料（库龄超过阈值）

    默认识别库龄超过90天的物料。
    """
    service = InventoryAnalysisService(db)
    items = await service.identify_slow_moving(
        warehouse_id=warehouse_id,
        days_threshold=days_threshold,
    )
    return [SlowMovingItem(**item) for item in items]


@router.get("/overstock", response_model=list[OverstockItem], summary="超储物料")
async def get_overstock_products(
    warehouse_id: Optional[int] = Query(default=None, description="仓库ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[OverstockItem]:
    """
    识别超储物料（库存可维持天数超过阈值）

    按产品类型使用不同阈值：
    - 原材料: > 60天
    - 产成品: > 90天
    """
    service = InventoryAnalysisService(db)
    items = await service.identify_overstock(warehouse_id=warehouse_id)
    return [OverstockItem(**item) for item in items]
