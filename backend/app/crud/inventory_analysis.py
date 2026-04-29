from __future__ import annotations

# -*- coding: utf-8 -*-
"""
库存分析 CRUD 操作

提供库存分析相关的数据库查询操作。
"""

import logging
from typing import Optional

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_snapshot import InventorySnapshot
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product

logger = logging.getLogger(__name__)


class InventoryAnalysisCRUD:
    """库存分析 CRUD 操作类"""

    async def get_product_type_summary(
        self,
        db: AsyncSession,
        warehouse_id: Optional[int] = None,
    ) -> list[dict]:
        """
        按产品类型统计库存汇总

        Returns:
            按产品类型分组的库存统计列表
        """
        subq = (
            select(
                InventorySnapshot.product_id,
                InventorySnapshot.warehouse_id,
                func.max(InventorySnapshot.timestamp).label("max_ts"),
            )
            .group_by(InventorySnapshot.product_id, InventorySnapshot.warehouse_id)
            .subquery()
        )

        stmt = (
            select(
                Product.product_type,
                func.count(func.distinct(InventorySnapshot.product_id)).label("product_count"),
                func.sum(InventorySnapshot.quantity_on_hand).label("total_quantity"),
                func.sum(InventorySnapshot.total_value).label("total_value"),
            )
            .join(
                subq,
                and_(
                    InventorySnapshot.product_id == subq.c.product_id,
                    InventorySnapshot.warehouse_id == subq.c.warehouse_id,
                    InventorySnapshot.timestamp == subq.c.max_ts,
                ),
            )
            .join(Product, InventorySnapshot.product_id == Product.id)
        )
        if warehouse_id is not None:
            stmt = stmt.where(InventorySnapshot.warehouse_id == warehouse_id)
        stmt = stmt.group_by(Product.product_type)

        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "product_type": r.product_type,
                "product_count": r.product_count,
                "total_quantity": int(r.total_quantity or 0),
                "total_value": float(r.total_value or 0),
            }
            for r in rows
        ]


# 创建全局库存分析 CRUD 实例
inventory_analysis_crud = InventoryAnalysisCRUD()
