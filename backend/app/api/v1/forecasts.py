# -*- coding: utf-8 -*-
"""
需求预测路由

处理需求预测的运行、查询和安全库存计算。
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import NotFoundException
from app.crud.forecast import forecast_crud
from app.crud.product import product_crud
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.forecast import (
    ForecastResponse,
    ForecastRunRequest,
    BatchForecastRequest,
    SafetyStockResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forecasts", tags=["需求预测"])


@router.post("/run", response_model=MessageResponse, summary="运行需求预测")
async def run_forecast(
    request: ForecastRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """
    为指定产品运行需求预测

    - 验证产品存在
    - 清除该产品的旧预测数据
    - 生成新的预测记录（当前阶段返回占位数据）

    注意：当前为占位实现，后续阶段将接入真实的预测模型。
    """
    product = await product_crud.get(db, id=request.product_id)
    if not product:
        raise NotFoundException(detail=f"产品 (ID: {request.product_id}) 不存在")

    # 清除旧预测数据
    deleted_count = await forecast_crud.delete_by_product(
        db,
        product_id=request.product_id,
        warehouse_id=request.warehouse_id,
    )

    # 生成占位预测数据
    today = datetime.now(timezone.utc).date()
    base_demand = Decimal("10.0")
    for day_offset in range(1, request.forecast_days + 1):
        forecast_date = today + timedelta(days=day_offset)
        # 简单线性增长 + 随机波动（占位逻辑）
        predicted = base_demand + Decimal(day_offset) * Decimal("0.5")
        lower = predicted * Decimal("0.7")
        upper = predicted * Decimal("1.3")

        await forecast_crud.create(db, obj_in={
            "product_id": request.product_id,
            "warehouse_id": request.warehouse_id,
            "forecast_date": datetime.combine(forecast_date, datetime.min.time()),
            "predicted_demand": predicted,
            "predicted_lower": lower,
            "predicted_upper": upper,
            "confidence": Decimal("0.95"),
            "model_name": request.model_name,
            "model_version": "v1",
            "safety_stock": Decimal("15.0"),
            "reorder_point": Decimal("25.0"),
            "notes": "占位预测数据 - 待接入真实模型",
        })

    logger.info(
        f"需求预测完成: 产品ID={request.product_id}, "
        f"仓库ID={request.warehouse_id}, 预测天数={request.forecast_days}",
    )

    return MessageResponse(
        message=f"已为产品 (ID: {request.product_id}) 生成 {request.forecast_days} 天的预测数据",
    )


@router.post("/run-batch", response_model=MessageResponse, summary="批量运行需求预测")
async def run_batch_forecast(
    request: BatchForecastRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """
    批量为多个产品运行需求预测

    注意：当前为占位实现，后续阶段将接入真实的预测模型。
    """
    success_count = 0
    failed_count = 0

    for product_id in request.product_ids:
        try:
            product = await product_crud.get(db, id=product_id)
            if not product:
                failed_count += 1
                continue

            # 清除旧预测
            await forecast_crud.delete_by_product(
                db,
                product_id=product_id,
                warehouse_id=request.warehouse_id,
            )

            # 生成占位预测数据
            today = datetime.now(timezone.utc).date()
            base_demand = Decimal("10.0")
            for day_offset in range(1, request.forecast_days + 1):
                forecast_date = today + timedelta(days=day_offset)
                predicted = base_demand + Decimal(day_offset) * Decimal("0.5")

                await forecast_crud.create(db, obj_in={
                    "product_id": product_id,
                    "warehouse_id": request.warehouse_id,
                    "forecast_date": datetime.combine(forecast_date, datetime.min.time()),
                    "predicted_demand": predicted,
                    "predicted_lower": predicted * Decimal("0.7"),
                    "predicted_upper": predicted * Decimal("1.3"),
                    "confidence": Decimal("0.95"),
                    "model_name": request.model_name,
                    "model_version": "v1",
                    "safety_stock": Decimal("15.0"),
                    "reorder_point": Decimal("25.0"),
                    "notes": "占位预测数据 - 批量生成",
                })

            success_count += 1
        except Exception as e:
            logger.error(f"产品 (ID: {product_id}) 预测失败: {e}")
            failed_count += 1

    logger.info(f"批量预测完成: 成功={success_count}, 失败={failed_count}")

    return MessageResponse(
        message=f"批量预测完成: 成功 {success_count} 个, 失败 {failed_count} 个",
    )


@router.get(
    "/{product_id}",
    response_model=list[ForecastResponse],
    summary="获取产品预测历史",
)
async def get_forecast_history(
    product_id: int,
    warehouse_id: int | None = Query(default=None, description="仓库ID筛选"),
    limit: int = Query(default=30, ge=1, le=365, description="返回记录数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[ForecastResponse]:
    """
    获取指定产品的需求预测历史记录

    返回最近的预测数据，按预测日期降序排列。
    """
    product = await product_crud.get(db, id=product_id)
    if not product:
        raise NotFoundException(detail=f"产品 (ID: {product_id}) 不存在")

    forecasts = await forecast_crud.get_by_product(
        db,
        product_id=product_id,
        warehouse_id=warehouse_id,
        limit=limit,
    )

    return [ForecastResponse.model_validate(f) for f in forecasts]


@router.get(
    "/{product_id}/safety-stock",
    response_model=SafetyStockResponse,
    summary="获取安全库存计算",
)
async def get_safety_stock(
    product_id: int,
    warehouse_id: int | None = Query(default=None, description="仓库ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SafetyStockResponse:
    """
    获取指定产品的安全库存计算结果

    基于历史需求数据计算安全库存和再订购点。

    注意：当前为占位实现，返回基于产品配置的估算值。
    """
    product = await product_crud.get(db, id=product_id)
    if not product:
        raise NotFoundException(detail=f"产品 (ID: {product_id}) 不存在")

    # 获取当前库存
    from app.crud.inventory import inventory_crud
    current_stock = 0
    if warehouse_id:
        snapshot = await inventory_crud.get_latest_snapshot(
            db, product_id=product_id, warehouse_id=warehouse_id,
        )
        if snapshot:
            current_stock = snapshot.quantity

    # 占位计算逻辑
    lead_time = product.lead_time_days
    avg_daily_demand = Decimal("5.0")  # 占位值
    demand_std_dev = Decimal("2.0")    # 占位值
    service_level = Decimal("0.95")

    # 安全库存 = Z * sigma * sqrt(lead_time)
    # Z=1.65 for 95% service level
    safety_stock = Decimal("1.65") * demand_std_dev * Decimal(lead_time ** 0.5)
    safety_stock = safety_stock.quantize(Decimal("0.01"))

    # 再订购点 = 平均日需求 * 提前期 + 安全库存
    reorder_point = avg_daily_demand * Decimal(lead_time) + safety_stock
    reorder_point = reorder_point.quantize(Decimal("0.01"))

    return SafetyStockResponse(
        product_id=product_id,
        warehouse_id=warehouse_id,
        current_stock=current_stock,
        safety_stock=safety_stock,
        reorder_point=reorder_point,
        avg_daily_demand=avg_daily_demand,
        demand_std_dev=demand_std_dev,
        lead_time_days=lead_time,
        service_level=service_level,
    )
