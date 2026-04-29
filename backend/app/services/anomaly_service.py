# -*- coding: utf-8 -*-
"""
异常检测服务

提供多种异常检测方法，用于识别库存管理中的异常情况：
- Z-Score 异常检测：基于标准差的方法
- IQR 异常检测：基于四分位距的方法
- 缺货风险检测：基于库存水平和需求速率
- 积压检测：基于库存周转天数
- 周转率异常检测：基于库存周转率
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import select, func, and_, desc, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_snapshot import InventorySnapshot
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.services.safety_stock_service import SafetyStockService

logger = logging.getLogger(__name__)


class AnomalyService:
    """
    异常检测服务

    提供统计方法和业务规则相结合的异常检测能力，
    支持对单个产品和全量产品的异常扫描。
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化异常检测服务

        Args:
            db: 异步数据库会话
        """
        self.db = db

    # ==================== 统计异常检测 ====================

    def detect_zscore(
        self,
        values: np.ndarray,
        threshold: float = 2.0,
    ) -> list[int]:
        """
        Z-Score 异常检测

        计算每个数据点的 Z-Score（标准分数），超过阈值的标记为异常。
        Z-Score = (x - mean) / std

        Args:
            values: 数值数组
            threshold: 异常阈值，默认2.0（约95%置信度）

        Returns:
            异常数据点的索引列表
        """
        if len(values) < 2:
            return []

        mean_val = np.mean(values)
        std_val = np.std(values, ddof=1)

        if std_val < 1e-10:
            # 标准差为零，所有值相同，无异常
            return []

        z_scores = np.abs((values - mean_val) / std_val)
        anomaly_indices = np.where(z_scores > threshold)[0].tolist()

        logger.debug(
            "Z-Score 检测: 数据点=%d, 阈值=%.1f, 异常数=%d",
            len(values), threshold, len(anomaly_indices),
        )
        return anomaly_indices

    def detect_iqr(
        self,
        values: np.ndarray,
        factor: float = 1.5,
    ) -> list[int]:
        """
        IQR（四分位距）异常检测

        基于四分位距识别异常值：
        - 下界 = Q1 - factor * IQR
        - 上界 = Q3 + factor * IQR
        超出边界的值标记为异常。

        Args:
            values: 数值数组
            factor: IQR 倍数因子，默认1.5（标准 Tukey 方法）

        Returns:
            异常数据点的索引列表
        """
        if len(values) < 4:
            return []

        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1

        if iqr < 1e-10:
            return []

        lower_bound = q1 - factor * iqr
        upper_bound = q3 + factor * iqr

        anomaly_indices = np.where(
            (values < lower_bound) | (values > upper_bound)
        )[0].tolist()

        logger.debug(
            "IQR 检测: 数据点=%d, factor=%.1f, Q1=%.2f, Q3=%.2f, IQR=%.2f, 异常数=%d",
            len(values), factor, q1, q3, iqr, len(anomaly_indices),
        )
        return anomaly_indices

    # ==================== 业务异常检测 ====================

    async def detect_stockout_risk(
        self,
        product_id: int,
        warehouse_id: int,
    ) -> dict | None:
        """
        检测缺货风险

        综合评估当前库存水平与需求速率，判断是否存在缺货风险。

        判定规则（按严重程度递减）：
        1. 当前库存 <= 0 -> 缺货（critical）
        2. 当前库存 < 安全库存 -> 低库存（high）
        3. 库存可维持天数 < 补货提前期 -> 缺货风险（medium）

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID

        Returns:
            异常信息字典，无异常时返回 None
        """
        logger.debug("检测缺货风险: 产品=%d, 仓库=%d", product_id, warehouse_id)

        # 获取最新库存快照
        snapshot = await self._get_latest_snapshot(product_id, warehouse_id)
        if snapshot is None:
            logger.debug("未找到库存快照: 产品=%d, 仓库=%d", product_id, warehouse_id)
            return None

        qty = float(snapshot.quantity_on_hand)

        # 获取产品配置
        product = await self._get_product(product_id)
        if product is None:
            return None

        safety_stock_days = product.safety_stock_days
        lead_time_days = product.lead_time_days

        # 计算日均需求（最近30天）
        avg_daily_demand = await self._get_avg_daily_demand(
            product_id, warehouse_id, days=30,
        )

        if avg_daily_demand <= 0:
            # 无出库记录，无法评估缺货风险
            return None

        # 计算库存可维持天数
        days_of_stock = qty / avg_daily_demand

        # 计算安全库存量
        safety_stock_qty = avg_daily_demand * safety_stock_days

        # 规则1：当前库存为零或负数
        if qty <= 0:
            return {
                "type": "stockout",
                "severity": "critical",
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "current_quantity": qty,
                "avg_daily_demand": round(avg_daily_demand, 2),
                "days_of_stock": 0,
                "message": f"产品已缺货，当前库存为 {qty}",
            }

        # 规则2：当前库存低于安全库存
        if qty < safety_stock_qty:
            return {
                "type": "low_stock",
                "severity": "high",
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "current_quantity": qty,
                "safety_stock": round(safety_stock_qty, 2),
                "avg_daily_demand": round(avg_daily_demand, 2),
                "days_of_stock": round(days_of_stock, 1),
                "message": (
                    f"库存低于安全库存，当前 {qty}，"
                    f"安全库存 {safety_stock_qty:.0f}，"
                    f"仅可维持 {days_of_stock:.1f} 天"
                ),
            }

        # 规则3：库存可维持天数小于补货提前期
        if days_of_stock < lead_time_days:
            return {
                "type": "stockout_risk",
                "severity": "medium",
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "current_quantity": qty,
                "lead_time_days": lead_time_days,
                "days_of_stock": round(days_of_stock, 1),
                "avg_daily_demand": round(avg_daily_demand, 2),
                "message": (
                    f"库存可维持 {days_of_stock:.1f} 天，"
                    f"小于补货提前期 {lead_time_days} 天，存在缺货风险"
                ),
            }

        return None

    async def detect_overstock(
        self,
        product_id: int,
        warehouse_id: int,
        max_days: int = 90,
    ) -> dict | None:
        """
        检测库存积压

        如果当前库存可维持天数超过阈值，判定为积压。

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID
            max_days: 最大可接受库存天数，默认90天

        Returns:
            异常信息字典，无异常时返回 None
        """
        logger.debug("检测库存积压: 产品=%d, 仓库=%d", product_id, warehouse_id)

        # 按产品类型使用不同的超储阈值
        from app.models.product import Product
        product_stmt = select(Product.product_type).where(Product.id == product_id)
        product_result = await self.db.execute(product_stmt)
        product_type = product_result.scalar_one_or_none() or "finished_good"
        
        # 原材料超储阈值60天，产成品超储阈值90天
        max_days = 60 if product_type == "raw_material" else 90

        snapshot = await self._get_latest_snapshot(product_id, warehouse_id)
        if snapshot is None:
            return None

        qty = float(snapshot.quantity_on_hand)

        if qty <= 0:
            return None

        avg_daily_demand = await self._get_avg_daily_demand(
            product_id, warehouse_id, days=30,
        )

        if avg_daily_demand <= 0:
            # 有库存但无出库记录，视为严重积压
            return {
                "type": "overstock",
                "severity": "high",
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "current_quantity": qty,
                "days_of_stock": float("inf"),
                "avg_daily_demand": 0,
                "message": (
                    f"库存 {qty} 但近30天无出库记录，"
                    f"可能为死库存"
                ),
            }

        days_of_stock = qty / avg_daily_demand

        if days_of_stock > max_days:
            return {
                "type": "overstock",
                "severity": "medium",
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "current_quantity": qty,
                "days_of_stock": round(days_of_stock, 1),
                "max_days": max_days,
                "avg_daily_demand": round(avg_daily_demand, 2),
                "message": (
                    f"库存可维持 {days_of_stock:.1f} 天，"
                    f"超过阈值 {max_days} 天，存在积压风险"
                ),
            }

        return None

    async def detect_turnover_anomaly(
        self,
        product_id: int,
        warehouse_id: int,
    ) -> dict | None:
        """
        检测周转率异常（慢动销产品）

        计算库存周转率 = 月均需求 / 平均库存。
        周转率 < 1.0 表示库存周转极慢，可能存在滞销风险。

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID

        Returns:
            异常信息字典，无异常时返回 None
        """
        logger.debug("检测周转率异常: 产品=%d, 仓库=%d", product_id, warehouse_id)

        # 获取最近30天的月均需求
        avg_daily_demand = await self._get_avg_daily_demand(
            product_id, warehouse_id, days=30,
        )
        avg_monthly_demand = avg_daily_demand * 30

        # 获取平均库存（使用最近快照）
        avg_inventory = await self._get_avg_inventory(
            product_id, warehouse_id, days=30,
        )

        if avg_inventory <= 0:
            return None

        turnover_rate = avg_monthly_demand / avg_inventory

        if turnover_rate < 1.0:
            return {
                "type": "slow_moving",
                "severity": "low",
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "turnover_rate": round(turnover_rate, 4),
                "avg_monthly_demand": round(avg_monthly_demand, 2),
                "avg_inventory": round(avg_inventory, 2),
                "message": (
                    f"周转率 {turnover_rate:.2f} < 1.0，"
                    f"月均需求 {avg_monthly_demand:.0f}，"
                    f"平均库存 {avg_inventory:.0f}，产品周转缓慢"
                ),
            }

        return None

    async def detect_aging_anomaly(
        self, product_id: int, warehouse_id: int
    ) -> dict | None:
        """
        检测库龄异常 - 识别呆滞物料
        
        原材料呆滞: 建议退回供应商或报废
        产成品滞销: 建议促销或降价
        """
        from app.models.inventory_snapshot import InventorySnapshot
        from app.models.product import Product
        
        # 获取产品类型
        product_stmt = select(Product.product_type).where(Product.id == product_id)
        product_result = await self.db.execute(product_stmt)
        product_type = product_result.scalar_one_or_none() or "finished_good"
        
        # 获取最新快照
        stmt = (
            select(InventorySnapshot)
            .where(
                and_(
                    InventorySnapshot.product_id == product_id,
                    InventorySnapshot.warehouse_id == warehouse_id,
                )
            )
            .order_by(desc(InventorySnapshot.timestamp))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        snapshot = result.scalar_one_or_none()
        
        if not snapshot or snapshot.aging_tier != "slow_moving":
            return None
        
        if product_type == "raw_material":
            suggestion = "原材料呆滞，建议：1.评估退回供应商可能性 2.调整采购计划减少进货 3.与生产部门确认近期用料需求"
        else:
            suggestion = "产成品滞销，建议：1.评估降价促销方案 2.调拨到需求量大的区域 3.与销售部门确认后续订单计划"
        
        return {
            "type": "aging_anomaly",
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "severity": "high",
            "age_days": snapshot.age_days,
            "product_type": product_type,
            "message": f"{'原材料' if product_type == 'raw_material' else '产成品'}(ID:{product_id}) 库龄已达 {snapshot.age_days} 天，属于呆滞物料。{suggestion}",
        }

    async def scan_all_products(self) -> list[dict]:
        """
        扫描所有活跃产品的异常情况

        对每个活跃产品执行缺货风险、积压和周转率异常检测，
        汇总所有检测结果。

        Returns:
            异常检测结果列表
        """
        logger.info("开始全量产品异常扫描")

        # 获取所有活跃产品
        stmt = select(Product.id).where(Product.is_active == True)  # noqa: E712
        result = await self.db.execute(stmt)
        product_ids = [row[0] for row in result.all()]

        logger.info("共 %d 个活跃产品需要扫描", len(product_ids))

        # 获取所有活跃仓库
        from app.models.warehouse import Warehouse
        wh_stmt = select(Warehouse.id).where(Warehouse.is_active == True)  # noqa: E712
        wh_result = await self.db.execute(wh_stmt)
        warehouse_ids = [row[0] for row in wh_result.all()]

        all_anomalies = []

        for product_id in product_ids:
            for warehouse_id in warehouse_ids:
                try:
                    # 检查是否有库存记录
                    snapshot = await self._get_latest_snapshot(product_id, warehouse_id)
                    if snapshot is None:
                        continue

                    # 执行各类异常检测
                    checks = [
                        self.detect_stockout_risk(product_id, warehouse_id),
                        self.detect_overstock(product_id, warehouse_id),
                        self.detect_turnover_anomaly(product_id, warehouse_id),
                    ]

                    for check_coro in checks:
                        anomaly = await check_coro
                        if anomaly is not None:
                            all_anomalies.append(anomaly)

                    # 库龄异常检测
                    aging_anomaly = await self.detect_aging_anomaly(product_id, warehouse_id)
                    if aging_anomaly:
                        all_anomalies.append(aging_anomaly)

                except Exception as e:
                    logger.error(
                        "扫描产品 %d 仓库 %d 时出错: %s",
                        product_id, warehouse_id, e,
                        exc_info=True,
                    )

        logger.info("异常扫描完成: 共发现 %d 个异常", len(all_anomalies))
        return all_anomalies

    # ==================== 辅助方法 ====================

    async def _get_latest_snapshot(
        self,
        product_id: int,
        warehouse_id: int,
    ) -> InventorySnapshot | None:
        """获取最新的库存快照"""
        stmt = (
            select(InventorySnapshot)
            .where(
                and_(
                    InventorySnapshot.product_id == product_id,
                    InventorySnapshot.warehouse_id == warehouse_id,
                )
            )
            .order_by(desc(InventorySnapshot.timestamp))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_product(self, product_id: int) -> Product | None:
        """获取产品信息"""
        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_avg_daily_demand(
        self,
        product_id: int,
        warehouse_id: int,
        days: int = 30,
    ) -> float:
        """
        计算指定时间范围内的日均出库需求

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID
            days: 回溯天数

        Returns:
            日均需求量
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = (
            select(
                func.sum(func.abs(InventoryTransaction.quantity_change)),
            )
            .where(
                and_(
                    InventoryTransaction.product_id == product_id,
                    InventoryTransaction.warehouse_id == warehouse_id,
                    InventoryTransaction.transaction_type == "outbound",
                    InventoryTransaction.created_at >= since,
                )
            )
        )

        result = await self.db.execute(stmt)
        total_demand = result.scalar() or 0

        return float(total_demand) / days

    async def _get_avg_inventory(
        self,
        product_id: int,
        warehouse_id: int,
        days: int = 30,
    ) -> float:
        """
        计算指定时间范围内的平均库存水平

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID
            days: 回溯天数

        Returns:
            平均库存量
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = (
            select(
                func.avg(InventorySnapshot.quantity_on_hand),
            )
            .where(
                and_(
                    InventorySnapshot.product_id == product_id,
                    InventorySnapshot.warehouse_id == warehouse_id,
                    InventorySnapshot.timestamp >= since,
                )
            )
        )

        result = await self.db.execute(stmt)
        avg_inv = result.scalar()
        return float(avg_inv) if avg_inv is not None else 0.0
