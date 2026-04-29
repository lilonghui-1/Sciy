from __future__ import annotations

# -*- coding: utf-8 -*-
"""
库存分析服务

提供高级库存分析功能，包括库龄分析、周转天数计算、
ABC 分类、库存健康指数和呆滞/超储物料识别。
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_, case, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_snapshot import InventorySnapshot
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product

logger = logging.getLogger(__name__)


class InventoryAnalysisService:
    """库存分析服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_aging(
        self,
        product_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
    ) -> dict:
        """
        库龄分析 - 按库龄分层统计库存数量和金额

        Args:
            product_id: 产品 ID（可选）
            warehouse_id: 仓库 ID（可选）

        Returns:
            包含各分层统计和汇总信息的字典
        """
        # 基础查询条件
        conditions = []
        if product_id is not None:
            conditions.append(InventorySnapshot.product_id == product_id)
        if warehouse_id is not None:
            conditions.append(InventorySnapshot.warehouse_id == warehouse_id)

        # 获取每个产品-仓库的最新快照
        subq = (
            select(
                InventorySnapshot.product_id,
                InventorySnapshot.warehouse_id,
                func.max(InventorySnapshot.timestamp).label("max_ts"),
            )
            .group_by(InventorySnapshot.product_id, InventorySnapshot.warehouse_id)
            .subquery()
        )

        # 关联最新快照获取库龄分层统计
        stmt = (
            select(
                InventorySnapshot.aging_tier,
                func.count().label("item_count"),
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
        )
        for cond in conditions:
            stmt = stmt.where(cond)
        stmt = stmt.group_by(InventorySnapshot.aging_tier)

        result = await self.db.execute(stmt)
        rows = result.all()

        tiers = []
        total_value = Decimal("0")
        total_quantity = 0
        tier_labels = {
            "normal": "正常(0-30天)",
            "attention": "关注(31-90天)",
            "slow_moving": "呆滞(90天以上)",
        }

        for row in rows:
            value = Decimal(str(row.total_value or 0))
            qty = int(row.total_quantity or 0)
            total_value += value
            total_quantity += qty
            tiers.append({
                "tier": row.aging_tier,
                "tier_label": tier_labels.get(row.aging_tier, row.aging_tier),
                "quantity": qty,
                "value": value,
                "percentage": 0.0,  # 后面计算
            })

        # 计算百分比
        for tier in tiers:
            if total_value > 0:
                tier["percentage"] = float(tier["value"] / total_value * 100)

        return {
            "tiers": tiers,
            "total_quantity": total_quantity,
            "total_value": total_value,
            "product_id": product_id,
            "warehouse_id": warehouse_id,
        }

    async def calculate_turnover_days(
        self,
        product_id: int,
        warehouse_id: int,
        days: int = 90,
    ) -> dict:
        """
        计算周转天数 = 平均库存 / 日均出库量

        Args:
            product_id: 产品 ID
            warehouse_id: 仓库 ID
            days: 统计周期（天）

        Returns:
            包含周转天数和统计明细的字典
        """
        from_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 计算日均出库量
        outbound_stmt = (
            select(func.sum(func.abs(InventoryTransaction.quantity_change)))
            .where(
                and_(
                    InventoryTransaction.product_id == product_id,
                    InventoryTransaction.warehouse_id == warehouse_id,
                    InventoryTransaction.transaction_type == "outbound",
                    InventoryTransaction.created_at >= from_date,
                )
            )
        )
        result = await self.db.execute(outbound_stmt)
        total_outbound = result.scalar() or 0
        avg_daily_outbound = total_outbound / days if days > 0 else 0

        # 计算平均库存（使用快照）
        avg_stmt = (
            select(func.avg(InventorySnapshot.quantity_on_hand))
            .where(
                and_(
                    InventorySnapshot.product_id == product_id,
                    InventorySnapshot.warehouse_id == warehouse_id,
                    InventorySnapshot.timestamp >= from_date,
                )
            )
        )
        result = await self.db.execute(avg_stmt)
        avg_inventory = float(result.scalar() or 0)

        # 计算周转天数
        turnover_days = avg_inventory / avg_daily_outbound if avg_daily_outbound > 0 else float("inf")

        # 计算年化周转率
        annual_turnover_rate = 365 / turnover_days if turnover_days > 0 and turnover_days != float("inf") else 0

        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "turnover_days": round(turnover_days, 1),
            "avg_inventory": round(avg_inventory, 2),
            "avg_daily_outbound": round(avg_daily_outbound, 2),
            "total_outbound_period": total_outbound,
            "period_days": days,
            "annual_turnover_rate": round(annual_turnover_rate, 2),
        }

    async def abc_classification(
        self,
        warehouse_id: Optional[int] = None,
    ) -> list[dict]:
        """
        ABC 分类 - 基于库存金额占比

        A 类: 累计金额占比 0-80%
        B 类: 累计金额占比 80-95%
        C 类: 累计金额占比 95-100%

        Args:
            warehouse_id: 仓库 ID（可选）

        Returns:
            ABC 分类结果列表
        """
        # 获取每个产品-仓库的最新快照
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
                InventorySnapshot.product_id,
                InventorySnapshot.warehouse_id,
                InventorySnapshot.quantity_on_hand,
                InventorySnapshot.total_value,
            )
            .join(
                subq,
                and_(
                    InventorySnapshot.product_id == subq.c.product_id,
                    InventorySnapshot.warehouse_id == subq.c.warehouse_id,
                    InventorySnapshot.timestamp == subq.c.max_ts,
                ),
            )
        )
        if warehouse_id is not None:
            stmt = stmt.where(InventorySnapshot.warehouse_id == warehouse_id)
        stmt = stmt.order_by(desc(InventorySnapshot.total_value))

        result = await self.db.execute(stmt)
        rows = result.all()

        total_value = sum(float(r.total_value or 0) for r in rows)
        if total_value == 0:
            return []

        items = []
        cumulative = 0.0
        for row in rows:
            value = float(row.total_value or 0)
            cumulative += value
            pct = cumulative / total_value * 100

            if pct <= 80:
                abc_class = "A"
            elif pct <= 95:
                abc_class = "B"
            else:
                abc_class = "C"

            items.append({
                "product_id": row.product_id,
                "warehouse_id": row.warehouse_id,
                "total_value": value,
                "cumulative_percentage": round(pct, 2),
                "abc_class": abc_class,
            })

        return items

    async def get_inventory_health_index(
        self,
        warehouse_id: Optional[int] = None,
    ) -> dict:
        """
        库存健康指数

        综合: 呆滞率 + 库龄健康度

        Returns:
            包含健康指数和各维度得分的字典
        """
        # 获取所有最新快照
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
                InventorySnapshot.total_value,
                InventorySnapshot.aging_tier,
            )
            .join(
                subq,
                and_(
                    InventorySnapshot.product_id == subq.c.product_id,
                    InventorySnapshot.warehouse_id == subq.c.warehouse_id,
                    InventorySnapshot.timestamp == subq.c.max_ts,
                ),
            )
        )
        if warehouse_id is not None:
            stmt = stmt.where(InventorySnapshot.warehouse_id == warehouse_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        total_value = sum(float(r.total_value or 0) for r in rows)
        slow_moving_value = sum(
            float(r.total_value or 0) for r in rows if r.aging_tier == "slow_moving"
        )
        attention_value = sum(
            float(r.total_value or 0) for r in rows if r.aging_tier == "attention"
        )

        # 健康指数 = 1 - (呆滞金额占比 * 0.7 + 关注金额占比 * 0.3)
        slow_moving_ratio = slow_moving_value / total_value if total_value > 0 else 0
        attention_ratio = attention_value / total_value if total_value > 0 else 0
        health_index = max(0, 1 - (slow_moving_ratio * 0.7 + attention_ratio * 0.3))

        return {
            "health_index": round(health_index, 4),
            "total_value": total_value,
            "slow_moving_value": slow_moving_value,
            "slow_moving_ratio": round(slow_moving_ratio, 4),
            "attention_value": attention_value,
            "attention_ratio": round(attention_ratio, 4),
            "normal_ratio": round(1 - slow_moving_ratio - attention_ratio, 4),
            "warehouse_id": warehouse_id,
        }

    async def identify_slow_moving(
        self,
        warehouse_id: Optional[int] = None,
        days_threshold: int = 90,
    ) -> list[dict]:
        """
        识别呆滞物料 - 库龄超过阈值

        Args:
            warehouse_id: 仓库 ID
            days_threshold: 库龄阈值（天）

        Returns:
            呆滞物料列表
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
                InventorySnapshot.product_id,
                InventorySnapshot.warehouse_id,
                InventorySnapshot.quantity_on_hand,
                InventorySnapshot.total_value,
                InventorySnapshot.age_days,
                InventorySnapshot.aging_tier,
            )
            .join(
                subq,
                and_(
                    InventorySnapshot.product_id == subq.c.product_id,
                    InventorySnapshot.warehouse_id == subq.c.warehouse_id,
                    InventorySnapshot.timestamp == subq.c.max_ts,
                ),
            )
            .where(InventorySnapshot.age_days >= days_threshold)
        )
        if warehouse_id is not None:
            stmt = stmt.where(InventorySnapshot.warehouse_id == warehouse_id)
        stmt = stmt.order_by(desc(InventorySnapshot.age_days))

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "product_id": r.product_id,
                "warehouse_id": r.warehouse_id,
                "quantity": r.quantity_on_hand,
                "value": float(r.total_value or 0),
                "age_days": r.age_days,
                "aging_tier": r.aging_tier,
            }
            for r in rows
        ]

    async def identify_overstock(
        self,
        warehouse_id: Optional[int] = None,
    ) -> list[dict]:
        """
        识别超储物料 - 按产品类型使用不同阈值

        原材料: 库存可维持 > 60 天
        产成品: 库存可维持 > 90 天

        Returns:
            超储物料列表
        """
        # 获取所有最新快照
        subq = (
            select(
                InventorySnapshot.product_id,
                InventorySnapshot.warehouse_id,
                func.max(InventorySnapshot.timestamp).label("max_ts"),
            )
            .group_by(InventorySnapshot.product_id, InventorySnapshot.warehouse_id)
            .subquery()
        )

        from_date = datetime.now(timezone.utc) - timedelta(days=90)

        # 计算每个产品的日均出库量
        daily_outbound_subq = (
            select(
                InventoryTransaction.product_id,
                InventoryTransaction.warehouse_id,
                func.sum(func.abs(InventoryTransaction.quantity_change)).label("total_out"),
            )
            .where(
                and_(
                    InventoryTransaction.transaction_type == "outbound",
                    InventoryTransaction.created_at >= from_date,
                )
            )
            .group_by(InventoryTransaction.product_id, InventoryTransaction.warehouse_id)
            .subquery()
        )

        stmt = (
            select(
                InventorySnapshot.product_id,
                InventorySnapshot.warehouse_id,
                InventorySnapshot.quantity_on_hand,
                InventorySnapshot.total_value,
                Product.product_type,
                daily_outbound_subq.c.total_out,
            )
            .join(
                subq,
                and_(
                    InventorySnapshot.product_id == subq.c.product_id,
                    InventorySnapshot.warehouse_id == subq.c.warehouse_id,
                    InventorySnapshot.timestamp == subq.c.max_ts,
                ),
            )
            .outerjoin(
                daily_outbound_subq,
                and_(
                    InventorySnapshot.product_id == daily_outbound_subq.c.product_id,
                    InventorySnapshot.warehouse_id == daily_outbound_subq.c.warehouse_id,
                ),
            )
            .outerjoin(Product, InventorySnapshot.product_id == Product.id)
        )
        if warehouse_id is not None:
            stmt = stmt.where(InventorySnapshot.warehouse_id == warehouse_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        overstock_items = []
        for r in rows:
            daily_out = float(r.total_out or 0) / 90
            if daily_out <= 0:
                continue
            days_of_stock = r.quantity_on_hand / daily_out
            product_type = r.product_type or "finished_good"
            threshold = 60 if product_type == "raw_material" else 90

            if days_of_stock > threshold:
                overstock_items.append({
                    "product_id": r.product_id,
                    "warehouse_id": r.warehouse_id,
                    "quantity": r.quantity_on_hand,
                    "value": float(r.total_value or 0),
                    "product_type": product_type,
                    "days_of_stock": round(days_of_stock, 1),
                    "threshold": threshold,
                })

        return sorted(overstock_items, key=lambda x: x["days_of_stock"], reverse=True)
