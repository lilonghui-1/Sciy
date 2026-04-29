# -*- coding: utf-8 -*-
"""
告警规则引擎

可配置的告警规则评估引擎，支持：
- 多种比较运算符（==, !=, >, >=, <, <=, between, in, not_in）
- 递归条件组合（AND/OR 逻辑）
- 冷却期去重（避免短时间内重复告警）
- 基于上下文的动态评估

告警规则 conditions JSON 结构示例：
{
    "logic": "AND",           // AND 或 OR
    "conditions": [
        {"field": "quantity_on_hand", "operator": "<", "value": 10},
        {"field": "days_of_stock", "operator": "<", "value": 7}
    ]
}

也支持嵌套：
{
    "logic": "OR",
    "conditions": [
        {"field": "quantity_on_hand", "operator": "<=", "value": 0},
        {
            "logic": "AND",
            "conditions": [
                {"field": "days_of_stock", "operator": "<", "value": 3},
                {"field": "turnover_rate", "operator": ">", "value": 5}
            ]
        }
    ]
}
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert_rule import AlertRule
from app.models.alert_event import AlertEvent
from app.models.inventory_snapshot import InventorySnapshot
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.warehouse import Warehouse

logger = logging.getLogger(__name__)


# ==================== 运算符映射 ====================

OPERATORS: dict[str, Any] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "between": lambda a, b: b[0] <= a <= b[1] if isinstance(b, (list, tuple)) and len(b) == 2 else False,
    "in": lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False,
    "not_in": lambda a, b: a not in b if isinstance(b, (list, tuple, set)) else False,
}


class AlertEngine:
    """
    告警规则引擎

    负责评估告警规则条件、管理冷却期、创建告警事件。
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化告警引擎

        Args:
            db: 异步数据库会话
        """
        self.db = db

    # ==================== 条件评估 ====================

    def _evaluate_condition(self, condition: dict, context: dict) -> bool:
        """
        评估单个条件

        从上下文中获取字段值，使用指定的运算符与阈值进行比较。

        Args:
            condition: 条件字典，包含 field, operator, value
            context: 评估上下文字典

        Returns:
            条件是否满足
        """
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        if field is None or operator is None:
            logger.warning("条件缺少 field 或 operator: %s", condition)
            return False

        # 从上下文中获取字段值
        actual_value = context.get(field)

        if actual_value is None:
            logger.debug("上下文中未找到字段 '%s'，条件不满足", field)
            return False

        # 获取运算符函数
        op_func = OPERATORS.get(operator)
        if op_func is None:
            logger.warning("未知运算符 '%s'", operator)
            return False

        try:
            result = op_func(actual_value, value)
            logger.debug(
                "条件评估: %s %s %s = %s (实际值=%s)",
                field, operator, value, result, actual_value,
            )
            return result
        except (TypeError, ValueError) as e:
            logger.warning(
                "条件评估异常: field=%s, operator=%s, value=%s, error=%s",
                field, operator, value, e,
            )
            return False

    def _evaluate_conditions(self, conditions: dict | list, context: dict) -> bool:
        """
        递归评估条件组

        支持两种结构：
        1. 带有 logic 字段的字典（AND/OR 组合）
        2. 条件字典列表（默认 AND 逻辑）

        Args:
            conditions: 条件组（字典或列表）
            context: 评估上下文

        Returns:
            条件组是否满足
        """
        # 如果是列表，视为 AND 逻辑
        if isinstance(conditions, list):
            return all(self._evaluate_condition(cond, context) for cond in conditions)

        # 如果是字典，检查是否有 logic 字段（嵌套条件组）
        if isinstance(conditions, dict):
            logic = conditions.get("logic", "AND").upper()
            sub_conditions = conditions.get("conditions", [])

            if not sub_conditions:
                return True

            if logic == "OR":
                return any(
                    self._evaluate_conditions(cond, context)
                    for cond in sub_conditions
                )
            else:
                # 默认 AND
                return all(
                    self._evaluate_conditions(cond, context)
                    for cond in sub_conditions
                )

        logger.warning("无法识别的条件结构: %s", type(conditions))
        return False

    # ==================== 上下文构建 ====================

    def _is_rule_applicable(self, rule, product, snapshot) -> bool:
        """
        检查规则是否适用于该产品
        
        根据规则的作用域字段（product_type, category_scope, aging_tier_scope）
        判断规则是否应该应用于当前产品。
        """
        # 获取产品类型
        product_type = getattr(product, 'product_type', None) or "finished_good"
        
        # 产品类型过滤
        rule_product_type = getattr(rule, 'product_type', None)
        if rule_product_type and product_type != rule_product_type:
            return False
        
        # 品类过滤
        rule_category_scope = getattr(rule, 'category_scope', None)
        if rule_category_scope:
            allowed_categories = [c.strip() for c in rule_category_scope.split(",")]
            product_category = getattr(product, 'category', None)
            if product_category not in allowed_categories:
                return False
        
        # 库龄分层过滤
        rule_aging_tier_scope = getattr(rule, 'aging_tier_scope', None)
        if rule_aging_tier_scope and snapshot:
            snapshot_aging_tier = getattr(snapshot, 'aging_tier', None)
            if snapshot_aging_tier != rule_aging_tier_scope:
                return False
        
        return True

    async def _build_context(
        self,
        product_id: int,
        warehouse_id: int,
    ) -> dict:
        """
        构建告警评估上下文

        从数据库中获取产品和库存数据，计算派生指标，
        构建一个包含所有可用于条件评估的字段的字典。

        可用上下文字段：
        - quantity_on_hand: 在手数量
        - quantity_reserved: 预留数量
        - quantity_available: 可用数量
        - unit_cost: 单位成本
        - safety_stock_days: 安全库存天数
        - lead_time_days: 补货提前期天数
        - daily_demand_avg_7d: 近7天日均需求
        - daily_demand_avg_30d: 近30天日均需求
        - days_of_stock: 库存可维持天数
        - turnover_rate: 库存周转率

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID

        Returns:
            上下文字典
        """
        context: dict = {}

        # 获取最新库存快照
        snapshot_stmt = (
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
        snapshot_result = await self.db.execute(snapshot_stmt)
        snapshot = snapshot_result.scalar_one_or_none()

        if snapshot is not None:
            context["quantity_on_hand"] = int(snapshot.quantity_on_hand)
            context["quantity_reserved"] = int(snapshot.quantity_reserved)
            context["quantity_available"] = int(snapshot.quantity_available)
            context["unit_cost"] = float(snapshot.unit_cost)
        else:
            context["quantity_on_hand"] = 0
            context["quantity_reserved"] = 0
            context["quantity_available"] = 0
            context["unit_cost"] = 0.0

        # 获取产品信息
        product_stmt = select(Product).where(Product.id == product_id)
        product_result = await self.db.execute(product_stmt)
        product = product_result.scalar_one_or_none()

        if product is not None:
            context["safety_stock_days"] = int(product.safety_stock_days)
            context["lead_time_days"] = int(product.lead_time_days)
            context["product_name"] = product.name
            context["product_sku"] = product.sku
            context["is_active"] = bool(product.is_active)
        else:
            context["safety_stock_days"] = 14
            context["lead_time_days"] = 7
            context["product_name"] = ""
            context["product_sku"] = ""
            context["is_active"] = False

        # 计算日均需求
        context["daily_demand_avg_7d"] = await self._calc_avg_daily_demand(
            product_id, warehouse_id, days=7,
        )
        context["daily_demand_avg_30d"] = await self._calc_avg_daily_demand(
            product_id, warehouse_id, days=30,
        )

        # 计算库存可维持天数
        qty = context["quantity_on_hand"]
        avg_demand = context["daily_demand_avg_30d"]
        if avg_demand > 0:
            context["days_of_stock"] = round(qty / avg_demand, 2)
        else:
            context["days_of_stock"] = float("inf") if qty > 0 else 0.0

        # 计算周转率（近30天）
        avg_monthly_demand = context["daily_demand_avg_30d"] * 30
        avg_inventory = await self._calc_avg_inventory(product_id, warehouse_id, days=30)
        if avg_inventory > 0:
            context["turnover_rate"] = round(avg_monthly_demand / avg_inventory, 4)
        else:
            context["turnover_rate"] = 0.0

        context["product_type"] = getattr(product, 'product_type', 'finished_good')
        context["aging_tier"] = getattr(snapshot, 'aging_tier', 'unknown') if snapshot else 'unknown'
        context["age_days"] = getattr(snapshot, 'age_days', 0) if snapshot else 0
        context["batch_no"] = getattr(snapshot, 'batch_no', None) if snapshot else None
        context["expiry_date"] = str(getattr(snapshot, 'expiry_date', '')) if snapshot and getattr(snapshot, 'expiry_date', None) else None

        logger.debug(
            "构建上下文完成: 产品=%d, 仓库=%d, 字段数=%d",
            product_id, warehouse_id, len(context),
        )
        return context

    # ==================== 规则检查 ====================

    async def check_product(
        self,
        product_id: int,
        warehouse_id: int,
    ) -> list[AlertEvent]:
        """
        检查单个产品的所有活跃告警规则

        流程：
        1. 获取所有活跃规则
        2. 构建评估上下文
        3. 逐条评估规则条件
        4. 检查冷却期，避免重复告警
        5. 创建告警事件

        Args:
            product_id: 产品ID
            warehouse_id: 仓库ID

        Returns:
            新创建的告警事件列表
        """
        logger.debug("检查告警: 产品=%d, 仓库=%d", product_id, warehouse_id)

        # 获取所有活跃规则
        rules_stmt = (
            select(AlertRule)
            .where(AlertRule.is_active == True)  # noqa: E712
        )
        rules_result = await self.db.execute(rules_stmt)
        rules = rules_result.scalars().all()

        if not rules:
            return []

        # 获取产品和快照用于作用域过滤
        product_stmt = select(Product).where(Product.id == product_id)
        product_result = await self.db.execute(product_stmt)
        product = product_result.scalar_one_or_none()

        snapshot_stmt = (
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
        snapshot_result = await self.db.execute(snapshot_stmt)
        snapshot = snapshot_result.scalar_one_or_none()

        # 按作用域过滤规则
        applicable_rules = []
        for rule in rules:
            if not self._is_rule_applicable(rule, product, snapshot):
                continue
            applicable_rules.append(rule)

        # 构建上下文
        context = await self._build_context(product_id, warehouse_id)

        triggered_events: list[AlertEvent] = []

        for rule in applicable_rules:
            try:
                # 评估规则条件
                is_triggered = self._evaluate_conditions(rule.conditions, context)

                if not is_triggered:
                    continue

                logger.info(
                    "规则触发: rule_id=%d, name='%s', 产品=%d, 仓库=%d",
                    rule.id, rule.name, product_id, warehouse_id,
                )

                # 检查冷却期
                if await self._is_in_cooldown(rule.id, product_id, warehouse_id, rule.cooldown_seconds):
                    logger.debug(
                        "规则 %d 在冷却期内，跳过", rule.id,
                    )
                    continue

                # 创建告警事件
                event = await self._create_alert_event(
                    rule=rule,
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    context=context,
                )
                if event is not None:
                    triggered_events.append(event)

            except Exception as e:
                logger.error(
                    "评估规则 %d 时出错: %s", rule.id, e,
                    exc_info=True,
                )

        return triggered_events

    async def check_all_products(self) -> list[AlertEvent]:
        """
        检查所有产品的告警规则（用于 Celery 定时任务）

        遍历所有活跃产品和仓库组合，执行告警规则检查。

        Returns:
            所有新创建的告警事件列表
        """
        logger.info("开始全量告警检查")

        # 获取所有活跃产品
        product_stmt = select(Product.id).where(Product.is_active == True)  # noqa: E712
        product_result = await self.db.execute(product_stmt)
        product_ids = [row[0] for row in product_result.all()]

        # 获取所有活跃仓库
        warehouse_stmt = select(Warehouse.id).where(Warehouse.is_active == True)  # noqa: E712
        warehouse_result = await self.db.execute(warehouse_stmt)
        warehouse_ids = [row[0] for row in warehouse_result.all()]

        all_events: list[AlertEvent] = []

        for product_id in product_ids:
            for warehouse_id in warehouse_ids:
                try:
                    events = await self.check_product(product_id, warehouse_id)
                    all_events.extend(events)
                except Exception as e:
                    logger.error(
                        "检查产品 %d 仓库 %d 告警时出错: %s",
                        product_id, warehouse_id, e,
                        exc_info=True,
                    )

        logger.info("全量告警检查完成: 共触发 %d 个告警事件", len(all_events))
        return all_events

    # ==================== 辅助方法 ====================

    async def _is_in_cooldown(
        self,
        rule_id: int,
        product_id: int,
        warehouse_id: int,
        cooldown_seconds: int,
    ) -> bool:
        """
        检查是否在冷却期内

        查询最近是否已有相同规则+产品+仓库的告警事件，
        且在冷却时间窗口内。

        Args:
            rule_id: 规则ID
            product_id: 产品ID
            warehouse_id: 仓库ID
            cooldown_seconds: 冷却时间（秒）

        Returns:
            是否在冷却期内
        """
        since = datetime.now(timezone.utc) - timedelta(seconds=cooldown_seconds)

        stmt = (
            select(func.count())
            .select_from(AlertEvent)
            .where(
                and_(
                    AlertEvent.rule_id == rule_id,
                    AlertEvent.product_id == product_id,
                    AlertEvent.warehouse_id == warehouse_id,
                    AlertEvent.created_at >= since,
                )
            )
        )

        result = await self.db.execute(stmt)
        count = result.scalar() or 0
        return count > 0

    async def _create_alert_event(
        self,
        rule: AlertRule,
        product_id: int,
        warehouse_id: int,
        context: dict,
    ) -> AlertEvent | None:
        """
        创建告警事件

        根据触发的规则和上下文信息，创建 AlertEvent 记录并持久化。

        Args:
            rule: 触发的告警规则
            product_id: 产品ID
            warehouse_id: 仓库ID
            context: 评估上下文

        Returns:
            新创建的告警事件，失败时返回 None
        """
        try:
            # 构建告警标题和消息
            product_name = context.get("product_name", f"产品#{product_id}")
            title = f"[{rule.rule_type}] {rule.name} - {product_name}"

            # 提取触发条件的关键信息
            conditions = rule.conditions
            condition_details = self._format_conditions(conditions, context)

            message = (
                f"告警规则「{rule.name}」已触发。\n"
                f"产品: {product_name} (ID: {product_id})\n"
                f"仓库ID: {warehouse_id}\n"
                f"规则类型: {rule.rule_type}\n"
                f"触发条件: {condition_details}\n"
                f"优先级: {rule.priority}"
            )

            # 确定当前值和阈值（取第一个条件作为代表）
            current_value = None
            threshold_value = None
            if isinstance(conditions, dict) and "conditions" in conditions:
                first_cond = conditions["conditions"][0] if conditions["conditions"] else {}
                current_value = context.get(first_cond.get("field"))
                threshold_value = first_cond.get("value")
            elif isinstance(conditions, list) and conditions:
                current_value = context.get(conditions[0].get("field"))
                threshold_value = conditions[0].get("value")

            event = AlertEvent(
                rule_id=rule.id,
                rule_name=rule.name,
                product_id=product_id,
                warehouse_id=warehouse_id,
                severity=rule.priority,
                title=title,
                message=message,
                current_value=float(current_value) if current_value is not None else None,
                threshold_value=float(threshold_value) if threshold_value is not None else None,
                context_data={
                    "evaluation_context": {
                        k: v for k, v in context.items()
                        if isinstance(v, (int, float, str, bool))
                    },
                    "rule_conditions": conditions,
                },
                status="new",
            )

            self.db.add(event)
            await self.db.flush()
            await self.db.refresh(event)

            logger.info(
                "告警事件已创建: event_id=%d, rule='%s', 产品=%d",
                event.id, rule.name, product_id,
            )
            return event

        except Exception as e:
            logger.error(
                "创建告警事件失败: rule_id=%d, product_id=%d, error=%s",
                rule.id, product_id, e,
                exc_info=True,
            )
            return None

    def _format_conditions(self, conditions: dict | list, context: dict) -> str:
        """
        格式化条件描述为可读字符串

        Args:
            conditions: 条件结构
            context: 评估上下文

        Returns:
            可读的条件描述字符串
        """
        parts = []

        if isinstance(conditions, list):
            for cond in conditions:
                field = cond.get("field", "?")
                operator = cond.get("operator", "?")
                value = cond.get("value", "?")
                actual = context.get(field, "?")
                parts.append(f"{field}({actual}) {operator} {value}")

        elif isinstance(conditions, dict):
            logic = conditions.get("logic", "AND")
            sub_conditions = conditions.get("conditions", [])
            sub_parts = self._format_conditions(sub_conditions, context)
            parts.append(f"({sub_parts}) [{logic}]")

        return " AND ".join(parts) if parts else "N/A"

    async def _calc_avg_daily_demand(
        self,
        product_id: int,
        warehouse_id: int,
        days: int = 30,
    ) -> float:
        """计算日均出库需求"""
        from datetime import timedelta

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
        total = result.scalar() or 0
        return float(total) / days

    async def _calc_avg_inventory(
        self,
        product_id: int,
        warehouse_id: int,
        days: int = 30,
    ) -> float:
        """计算平均库存水平"""
        from datetime import timedelta

        since = datetime.now(timezone.utc) - timedelta(days=days)

        stmt = (
            select(func.avg(InventorySnapshot.quantity_on_hand))
            .where(
                and_(
                    InventorySnapshot.product_id == product_id,
                    InventorySnapshot.warehouse_id == warehouse_id,
                    InventorySnapshot.timestamp >= since,
                )
            )
        )

        result = await self.db.execute(stmt)
        avg = result.scalar()
        return float(avg) if avg is not None else 0.0
