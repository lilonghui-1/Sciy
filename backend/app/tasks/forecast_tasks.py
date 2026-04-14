# -*- coding: utf-8 -*-
"""
Celery 需求预测任务

提供定时和按需触发的需求预测 Celery 任务：
- run_daily_forecast: 定时任务，对所有活跃产品执行预测并保存结果
- run_batch_forecast_task: 按需任务，对指定产品列表执行批量预测
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import async_session_factory
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.demand_forecast import DemandForecast
from app.services.forecast_service import ForecastService
from app.services.safety_stock_service import SafetyStockService
from app.tasks import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.forecast_tasks.run_daily_forecast",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    track_started=True,
)
def run_daily_forecast(self, forecast_days: int = 14) -> dict:
    """
    每日需求预测定时任务

    获取所有活跃产品和仓库，执行需求预测，
    将预测结果保存到 demand_forecasts 表。

    流程：
    1. 查询所有活跃产品和仓库
    2. 对每个产品-仓库组合执行预测
    3. 清理旧的预测记录
    4. 保存新的预测结果
    5. 计算并更新安全库存建议

    Args:
        forecast_days: 预测天数，默认14天

    Returns:
        任务执行摘要
    """
    logger.info("开始执行每日预测任务: forecast_days=%d", forecast_days)

    import asyncio

    async def _execute() -> dict:
        async with async_session_factory() as session:
            try:
                # 获取所有活跃产品
                product_stmt = select(Product.id).where(Product.is_active == True)  # noqa: E712
                product_result = await session.execute(product_stmt)
                product_ids = [row[0] for row in product_result.all()]

                # 获取所有活跃仓库
                warehouse_stmt = select(Warehouse.id).where(Warehouse.is_active == True)  # noqa: E712
                warehouse_result = await session.execute(warehouse_stmt)
                warehouse_ids = [row[0] for row in warehouse_result.all()]

                if not product_ids:
                    logger.warning("无活跃产品，跳过预测")
                    return {"status": "skipped", "reason": "no_active_products"}

                if not warehouse_ids:
                    logger.warning("无活跃仓库，跳过预测")
                    return {"status": "skipped", "reason": "no_active_warehouses"}

                forecast_service = ForecastService(session)
                safety_stock_service = SafetyStockService(session)

                total_forecasts = 0
                success_count = 0
                fail_count = 0
                skipped_count = 0

                for product_id in product_ids:
                    for warehouse_id in warehouse_ids:
                        try:
                            # 执行预测
                            results = await forecast_service.run_forecast(
                                product_id=product_id,
                                warehouse_id=warehouse_id,
                                forecast_days=forecast_days,
                            )

                            if not results:
                                skipped_count += 1
                                continue

                            # 计算安全库存建议
                            safety_stock_result = await safety_stock_service.calculate(
                                product_id=product_id,
                                warehouse_id=warehouse_id,
                            )

                            # 保存预测结果到数据库
                            for r in results:
                                forecast_record = DemandForecast(
                                    product_id=product_id,
                                    warehouse_id=warehouse_id,
                                    forecast_date=datetime.strptime(
                                        r["forecast_date"], "%Y-%m-%d",
                                    ).replace(tzinfo=timezone.utc),
                                    predicted_demand=r["predicted_demand"],
                                    predicted_demand_lower=r["lower_bound"],
                                    predicted_demand_upper=r["upper_bound"],
                                    model_name=r["model_name"],
                                    model_params=r["model_params"],
                                    safety_stock=safety_stock_result.get("safety_stock"),
                                    reorder_point=safety_stock_result.get("reorder_point"),
                                )
                                session.add(forecast_record)

                            total_forecasts += len(results)
                            success_count += 1

                        except Exception as e:
                            logger.error(
                                "预测失败: 产品=%d, 仓库=%d, 错误=%s",
                                product_id, warehouse_id, e,
                                exc_info=True,
                            )
                            fail_count += 1

                await session.commit()

                summary = {
                    "status": "completed",
                    "products": len(product_ids),
                    "warehouses": len(warehouse_ids),
                    "success": success_count,
                    "failed": fail_count,
                    "skipped": skipped_count,
                    "total_forecasts": total_forecasts,
                    "forecast_days": forecast_days,
                }

                logger.info("每日预测任务完成: %s", summary)
                return summary

            except Exception as e:
                await session.rollback()
                logger.error("每日预测任务执行失败: %s", e, exc_info=True)
                raise

    try:
        result = asyncio.run(_execute())
        return result
    except Exception as exc:
        logger.error("每日预测任务异常: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.forecast_tasks.run_batch_forecast_task",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
    track_started=True,
)
def run_batch_forecast_task(
    self,
    product_ids: list[int],
    warehouse_id: int,
    forecast_days: int = 14,
) -> dict:
    """
    按需批量预测任务

    对指定的产品列表执行需求预测并保存结果。

    Args:
        product_ids: 产品ID列表
        warehouse_id: 仓库ID
        forecast_days: 预测天数，默认14天

    Returns:
        任务执行摘要
    """
    logger.info(
        "开始批量预测任务: 产品数=%d, 仓库=%d, 天数=%d",
        len(product_ids), warehouse_id, forecast_days,
    )

    import asyncio

    async def _execute() -> dict:
        async with async_session_factory() as session:
            try:
                forecast_service = ForecastService(session)
                safety_stock_service = SafetyStockService(session)

                results = await forecast_service.run_batch_forecast(
                    product_ids=product_ids,
                    warehouse_id=warehouse_id,
                    forecast_days=forecast_days,
                )

                # 按产品分组保存
                saved_count = 0
                for r in results:
                    pid = r["product_id"]
                    wid = r["warehouse_id"]

                    # 计算安全库存
                    safety_stock_result = await safety_stock_service.calculate(
                        product_id=pid,
                        warehouse_id=wid,
                    )

                    forecast_record = DemandForecast(
                        product_id=pid,
                        warehouse_id=wid,
                        forecast_date=datetime.strptime(
                            r["forecast_date"], "%Y-%m-%d",
                        ).replace(tzinfo=timezone.utc),
                        predicted_demand=r["predicted_demand"],
                        predicted_demand_lower=r["lower_bound"],
                        predicted_demand_upper=r["upper_bound"],
                        model_name=r["model_name"],
                        model_params=r["model_params"],
                        safety_stock=safety_stock_result.get("safety_stock"),
                        reorder_point=safety_stock_result.get("reorder_point"),
                    )
                    session.add(forecast_record)
                    saved_count += 1

                await session.commit()

                summary = {
                    "status": "completed",
                    "products_requested": len(product_ids),
                    "forecasts_saved": saved_count,
                    "warehouse_id": warehouse_id,
                    "forecast_days": forecast_days,
                }

                logger.info("批量预测任务完成: %s", summary)
                return summary

            except Exception as e:
                await session.rollback()
                logger.error("批量预测任务失败: %s", e, exc_info=True)
                raise

    try:
        result = asyncio.run(_execute())
        return result
    except Exception as exc:
        logger.error("批量预测任务异常: %s", exc, exc_info=True)
        raise self.retry(exc=exc)
