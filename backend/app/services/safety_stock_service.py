# -*- coding: utf-8 -*-
"""
安全库存计算服务

基于历史需求数据和补货提前期，动态计算安全库存和再订货点。
使用统计学方法（正态分布分位数）确保在指定服务水平下的库存充足率。

核心公式：
    安全库存 = Z_score * 需求标准差 * sqrt(提前期)
    再订货点 = 日均需求 * 提前期 + 安全库存
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from scipy import stats
from sqlalchemy import select, func, and_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product

logger = logging.getLogger(__name__)


class SafetyStockService:
    """
    动态安全库存计算服务

    根据历史出库数据和产品配置的补货参数，计算最优安全库存量和再订货点。
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化安全库存服务

        Args:
            db: 异步数据库会话
        """
        self.db = db

    async def calculate(
        self,
        product_id: int,
        warehouse_id: int,
        service_level: float = 0.95,
        lead_time_days: int | None = None,
    ) -> dict:
        """
        计算安全库存和再订货点

        流程：
        1. 获取历史每日出库需求数据（最近30天以上）
        2. 计算日均需求和需求标准差
        3. 根据服务水平计算 Z 分数
        4. 应用安全库存公式计算结果

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID
            service_level: 服务水平，默认0.95（95%）
            lead_time_days: 补货提前期天数，为 None 时从产品配置获取

        Returns:
            包含 safety_stock, reorder_point, avg_daily_demand, demand_std,
            z_score, service_level, lead_time_days, method 的字典
        """
        logger.info(
            "计算安全库存: 产品=%d, 仓库=%d, 服务水平=%.2f",
            product_id, warehouse_id, service_level,
        )

        # 获取产品类型，差异化计算
        product_stmt = select(Product.product_type, Product.production_cycle_days).where(Product.id == product_id)
        product_result = await self.db.execute(product_stmt)
        product_row = product_result.one_or_none()
        product_type = product_row[0] if product_row else "finished_good"
        production_cycle = product_row[1] if product_row else 7

        # 获取产品配置的补货提前期
        if lead_time_days is None:
            lead_time_days = await self._get_lead_time(product_id)
            if lead_time_days is None:
                lead_time_days = 7  # 默认7天

        # 原材料使用采购提前期，产成品使用生产周期
        if product_type == "raw_material":
            effective_lead_time = lead_time_days
        else:
            effective_lead_time = production_cycle

        # 获取历史需求数据（至少30天）
        days_lookback = max(30, lead_time_days * 2)
        since = datetime.now(timezone.utc) - timedelta(days=days_lookback)

        stmt = (
            select(
                cast(InventoryTransaction.created_at, Date).label("date"),
                func.sum(func.abs(InventoryTransaction.quantity_change)).label("demand"),
            )
            .where(
                and_(
                    InventoryTransaction.product_id == product_id,
                    InventoryTransaction.warehouse_id == warehouse_id,
                    InventoryTransaction.transaction_type == "outbound",
                    InventoryTransaction.created_at >= since,
                )
            )
            .group_by(cast(InventoryTransaction.created_at, Date))
            .order_by(cast(InventoryTransaction.created_at, Date))
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        # 数据不足检查
        if len(rows) < 7:
            logger.warning(
                "产品 %d 仓库 %d 历史数据不足（%d 天 < 7 天），无法计算安全库存",
                product_id, warehouse_id, len(rows),
            )
            return {
                "safety_stock": 0,
                "reorder_point": 0,
                "avg_daily_demand": 0,
                "demand_std": 0,
                "z_score": 0,
                "service_level": service_level,
                "lead_time_days": lead_time_days,
                "method": "insufficient_data",
            }

        # 提取每日需求值
        daily_demands = np.array([float(row.demand) for row in rows], dtype=float)

        # 计算统计指标
        avg_daily_demand = float(np.mean(daily_demands))
        demand_std = float(np.std(daily_demands, ddof=1)) if len(daily_demands) > 1 else 0.0

        # 计算 Z 分数（正态分布分位数）
        z_score = float(stats.norm.ppf(service_level))

        # 安全库存 = Z * sigma * sqrt(LT)
        safety_stock = z_score * demand_std * np.sqrt(effective_lead_time)

        # 再订货点 = 日均需求 * 提前期 + 安全库存
        reorder_point = avg_daily_demand * effective_lead_time + safety_stock

        result_dict = {
            "safety_stock": round(float(safety_stock), 2),
            "reorder_point": round(float(reorder_point), 2),
            "avg_daily_demand": round(avg_daily_demand, 2),
            "demand_std": round(demand_std, 2),
            "z_score": round(z_score, 4),
            "service_level": service_level,
            "lead_time_days": effective_lead_time,
            "method": "statistical",
        }

        result_dict["product_type"] = product_type
        result_dict["calculation_basis"] = "consumption" if product_type == "raw_material" else "sales"

        logger.info(
            "安全库存计算完成: 产品=%d, 仓库=%d, SS=%.2f, ROP=%.2f, 方法=%s",
            product_id, warehouse_id, result_dict["safety_stock"],
            result_dict["reorder_point"], result_dict["method"],
        )

        return result_dict

    async def _get_lead_time(self, product_id: int) -> int | None:
        """
        从产品配置中获取补货提前期

        Args:
            product_id: 产品ID

        Returns:
            补货提前期天数，产品不存在时返回 None
        """
        stmt = select(Product.lead_time_days).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        value = result.scalar_one_or_none()
        return int(value) if value is not None else None
