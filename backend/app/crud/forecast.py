# -*- coding: utf-8 -*-
from __future__ import annotations

"""
需求预测 CRUD 操作

提供需求预测相关的数据库操作。
"""

import logging
from typing import Optional, Sequence

from sqlalchemy import select, and_, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.demand_forecast import DemandForecast

logger = logging.getLogger(__name__)


class ForecastCRUD(BaseCRUD[DemandForecast]):
    """需求预测 CRUD 操作类"""

    def __init__(self) -> None:
        super().__init__(DemandForecast)

    async def get_by_product(
        self,
        db: AsyncSession,
        *,
        product_id: int,
        warehouse_id: Optional[int] = None,
        limit: int = 30,
    ) -> Sequence[DemandForecast]:
        """
        获取指定产品的预测记录

        Args:
            db: 数据库会话
            product_id: 产品 ID
            warehouse_id: 仓库 ID（可选）
            limit: 返回记录数上限

        Returns:
            预测记录列表
        """
        conditions = [DemandForecast.product_id == product_id]
        if warehouse_id is not None:
            conditions.append(DemandForecast.warehouse_id == warehouse_id)

        stmt = (
            select(DemandForecast)
            .where(and_(*conditions))
            .order_by(desc(DemandForecast.forecast_date))
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def delete_by_product(
        self,
        db: AsyncSession,
        *,
        product_id: int,
        warehouse_id: Optional[int] = None,
    ) -> int:
        """
        删除指定产品的预测记录（在新预测生成前清理旧数据）

        Args:
            db: 数据库会话
            product_id: 产品 ID
            warehouse_id: 仓库 ID（可选，不传则删除该产品所有预测）

        Returns:
            删除的记录数
        """
        conditions = [DemandForecast.product_id == product_id]
        if warehouse_id is not None:
            conditions.append(DemandForecast.warehouse_id == warehouse_id)

        stmt = delete(DemandForecast).where(and_(*conditions))
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount


# 创建全局预测 CRUD 实例
forecast_crud = ForecastCRUD()
