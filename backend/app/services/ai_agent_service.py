# -*- coding: utf-8 -*-
"""
AI 智能助手服务

基于 LangChain Tool-Calling 的库存管理智能助手，集成 OpenAI GPT-4o-mini 模型。
提供库存查询、需求预测、库存调整建议、告警分析、周转分析等能力。
"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, and_, desc, asc, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ==================== 系统提示词 ====================

SYSTEM_PROMPT = """你是一个专业的供应链库存管理助手。你可以帮助用户：
1. 查询产品库存状态和趋势
2. 分析库存风险（缺货、积压）
3. 生成库存调整建议（采购量、调拨方案、促销建议）
4. 查看告警信息
5. 分析产品周转情况（畅销品、滞销品）

回答要求：
- 使用专业但易懂的中文
- 数据引用要准确
- 建议要具体可执行（包含具体数量、优先级）
- 如果数据不足，明确说明
- 建议格式：先分析现状，再给出建议，最后说明理由"""


# ==================== 依赖检查 ====================

def _check_dependencies() -> bool:
    """
    检查 langchain 和 openai 依赖是否已安装

    Returns:
        True 表示依赖可用，False 表示缺少依赖
    """
    try:
        import langchain_openai  # noqa: F401
        from langchain.agents import create_tool_calling_agent, AgentExecutor  # noqa: F401
        from langchain_core.prompts import ChatPromptTemplate  # noqa: F401
        from langchain_core.tools import StructuredTool  # noqa: F401
        return True
    except ImportError:
        return False


# ==================== 工具函数定义 ====================

async def _get_inventory_status_tool(db: AsyncSession, product_sku: str) -> str:
    """
    查询指定 SKU 的当前库存状态

    Args:
        db: 异步数据库会话
        product_sku: 产品 SKU 编码

    Returns:
        库存状态信息字符串
    """
    from app.models.product import Product
    from app.models.inventory_snapshot import InventorySnapshot
    from app.models.warehouse import Warehouse

    # 查询产品信息
    stmt = select(Product).where(Product.sku == product_sku)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if product is None:
        return f"未找到 SKU 为 '{product_sku}' 的产品，请确认 SKU 编码是否正确。"

    # 查询该产品在所有仓库的最新库存快照
    # 使用子查询获取每个仓库的最新快照
    latest_snapshot_subquery = (
        select(
            InventorySnapshot.id,
            InventorySnapshot.warehouse_id,
            func.max(InventorySnapshot.timestamp).label("max_ts"),
        )
        .where(InventorySnapshot.product_id == product.id)
        .group_by(InventorySnapshot.id, InventorySnapshot.warehouse_id)
        .subquery()
    )

    stmt = (
        select(InventorySnapshot, Warehouse.name)
        .join(
            latest_snapshot_subquery,
            and_(
                InventorySnapshot.id == latest_snapshot_subquery.c.id,
            ),
        )
        .join(Warehouse, InventorySnapshot.warehouse_id == Warehouse.id)
        .where(InventorySnapshot.product_id == product.id)
        .order_by(desc(InventorySnapshot.timestamp))
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return (
            f"产品: {product.name} (SKU: {product_sku})\n"
            f"分类: {product.category or '未分类'}\n"
            f"单位: {product.unit}\n"
            f"单位成本: {float(product.unit_cost):.2f} 元\n"
            f"销售单价: {float(product.selling_price):.2f} 元\n"
            f"补货提前期: {product.lead_time_days} 天\n"
            f"安全库存天数: {product.safety_stock_days} 天\n\n"
            f"当前暂无库存快照记录。"
        )

    lines = [
        f"产品: {product.name} (SKU: {product_sku})",
        f"分类: {product.category or '未分类'}",
        f"单位: {product.unit}",
        f"单位成本: {float(product.unit_cost):.2f} 元",
        f"销售单价: {float(product.selling_price):.2f} 元",
        f"补货提前期: {product.lead_time_days} 天",
        f"安全库存天数: {product.safety_stock_days} 天",
        "",
        "各仓库库存情况：",
    ]

    total_on_hand = 0
    total_reserved = 0
    total_available = 0
    total_value = 0.0

    for snapshot, warehouse_name in rows:
        on_hand = snapshot.quantity_on_hand
        reserved = snapshot.quantity_reserved
        available = snapshot.quantity_available
        value = float(snapshot.total_value)
        ts = snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S") if snapshot.timestamp else "未知"

        total_on_hand += on_hand
        total_reserved += reserved
        total_available += available
        total_value += value

        lines.append(
            f"  - {warehouse_name}: 在手 {on_hand}, 预留 {reserved}, "
            f"可用 {available}, 库存价值 {value:.2f} 元 "
            f"(快照时间: {ts})"
        )

    lines.append("")
    lines.append(f"合计: 在手 {total_on_hand}, 预留 {total_reserved}, "
                 f"可用 {total_available}, 总价值 {total_value:.2f} 元")

    return "\n".join(lines)


async def _get_demand_forecast_tool(db: AsyncSession, product_sku: str, days: int = 14) -> str:
    """
    获取指定 SKU 的需求预测数据

    Args:
        db: 异步数据库会话
        product_sku: 产品 SKU 编码
        days: 预测天数，默认 14 天

    Returns:
        需求预测信息字符串
    """
    from app.models.product import Product
    from app.models.demand_forecast import DemandForecast

    # 查询产品
    stmt = select(Product).where(Product.sku == product_sku)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if product is None:
        return f"未找到 SKU 为 '{product_sku}' 的产品。"

    # 查询未来的预测数据
    now = datetime.now(timezone.utc)
    future_date = now + timedelta(days=days)

    stmt = (
        select(DemandForecast)
        .where(
            and_(
                DemandForecast.product_id == product.id,
                DemandForecast.forecast_date >= now,
                DemandForecast.forecast_date <= future_date,
            )
        )
        .order_by(asc(DemandForecast.forecast_date))
        .limit(days)
    )

    result = await db.execute(stmt)
    forecasts = result.scalars().all()

    if not forecasts:
        # 尝试查询最近的预测数据（即使已过期）
        stmt_recent = (
            select(DemandForecast)
            .where(DemandForecast.product_id == product.id)
            .order_by(desc(DemandForecast.forecast_date))
            .limit(14)
        )
        result_recent = await db.execute(stmt_recent)
        recent_forecasts = result_recent.scalars().all()

        if recent_forecasts:
            lines = [
                f"产品: {product.name} (SKU: {product_sku})",
                f"注意: 未来 {days} 天内无预测数据，以下为最近的预测记录：",
                "",
            ]
            total_predicted = 0.0
            for f in recent_forecasts:
                date_str = f.forecast_date.strftime("%Y-%m-%d") if f.forecast_date else "未知"
                pred = float(f.predicted_demand)
                total_predicted += pred
                lower = float(f.predicted_demand_lower) if f.predicted_demand_lower else None
                upper = float(f.predicted_demand_upper) if f.predicted_demand_upper else None
                line = f"  {date_str}: 预测需求 {pred:.1f}"
                if lower is not None and upper is not None:
                    line += f" (区间: {lower:.1f} ~ {upper:.1f})"
                line += f" [模型: {f.model_name}]"
                lines.append(line)

            lines.append("")
            lines.append(f"日均预测需求: {total_predicted / len(recent_forecasts):.1f}")
            return "\n".join(lines)

        return (
            f"产品: {product.name} (SKU: {product_sku})\n"
            f"当前无需求预测数据。建议先运行预测任务生成预测数据。"
        )

    lines = [
        f"产品: {product.name} (SKU: {product_sku})",
        f"未来 {days} 天需求预测：",
        "",
    ]

    total_predicted = 0.0
    for f in forecasts:
        date_str = f.forecast_date.strftime("%Y-%m-%d") if f.forecast_date else "未知"
        pred = float(f.predicted_demand)
        total_predicted += pred
        lower = float(f.predicted_demand_lower) if f.predicted_demand_lower else None
        upper = float(f.predicted_demand_upper) if f.predicted_demand_upper else None
        line = f"  {date_str}: 预测需求 {pred:.1f}"
        if lower is not None and upper is not None:
            line += f" (区间: {lower:.1f} ~ {upper:.1f})"
        line += f" [模型: {f.model_name}]"
        lines.append(line)

    lines.append("")
    avg_daily = total_predicted / len(forecasts)
    lines.append(f"日均预测需求: {avg_daily:.1f}")
    lines.append(f"总预测需求: {total_predicted:.1f}")

    return "\n".join(lines)


async def _suggest_inventory_adjustment_tool(db: AsyncSession, product_sku: str) -> str:
    """
    基于当前库存、预测数据和安全库存，生成库存调整建议

    Args:
        db: 异步数据库会话
        product_sku: 产品 SKU 编码

    Returns:
        库存调整建议字符串
    """
    from app.models.product import Product
    from app.models.inventory_snapshot import InventorySnapshot
    from app.models.demand_forecast import DemandForecast
    from app.models.inventory_transaction import InventoryTransaction

    # 查询产品
    stmt = select(Product).where(Product.sku == product_sku)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()

    if product is None:
        return f"未找到 SKU 为 '{product_sku}' 的产品。"

    # 查询最新库存快照（所有仓库合计）
    stmt_snap = (
        select(
            func.sum(InventorySnapshot.quantity_on_hand).label("total_on_hand"),
            func.sum(InventorySnapshot.quantity_reserved).label("total_reserved"),
            func.sum(InventorySnapshot.quantity_available).label("total_available"),
            func.sum(InventorySnapshot.total_value).label("total_value"),
            func.max(InventorySnapshot.timestamp).label("latest_ts"),
        )
        .where(InventorySnapshot.product_id == product.id)
    )
    result_snap = await db.execute(stmt_snap)
    snap_row = result_snap.one()

    total_on_hand = int(snap_row.total_on_hand or 0)
    total_reserved = int(snap_row.total_reserved or 0)
    total_available = int(snap_row.total_available or 0)
    total_value = float(snap_row.total_value or 0)

    # 计算日均出库需求（最近30天）
    since = datetime.now(timezone.utc) - timedelta(days=30)
    stmt_demand = (
        select(func.sum(func.abs(InventoryTransaction.quantity_change)))
        .where(
            and_(
                InventoryTransaction.product_id == product.id,
                InventoryTransaction.transaction_type == "outbound",
                InventoryTransaction.created_at >= since,
            )
        )
    )
    result_demand = await db.execute(stmt_demand)
    total_outbound = result_demand.scalar() or 0
    avg_daily_demand = float(total_outbound) / 30.0

    # 查询未来14天预测
    now = datetime.now(timezone.utc)
    future_date = now + timedelta(days=14)
    stmt_forecast = (
        select(
            func.sum(DemandForecast.predicted_demand).label("total_forecast"),
            func.avg(DemandForecast.predicted_demand).label("avg_forecast"),
        )
        .where(
            and_(
                DemandForecast.product_id == product.id,
                DemandForecast.forecast_date >= now,
                DemandForecast.forecast_date <= future_date,
            )
        )
    )
    result_forecast = await db.execute(stmt_forecast)
    forecast_row = result_forecast.one()
    total_forecast_14d = float(forecast_row.total_forecast or 0)
    avg_forecast_demand = float(forecast_row.avg_forecast or 0)

    # 使用预测日均需求（如果有），否则使用历史日均需求
    effective_daily_demand = avg_forecast_demand if avg_forecast_demand > 0 else avg_daily_demand

    # 计算关键指标
    safety_stock_qty = effective_daily_demand * product.safety_stock_days
    reorder_point = effective_daily_demand * product.lead_time_days + safety_stock_qty
    days_of_stock = total_available / effective_daily_demand if effective_daily_demand > 0 else float("inf")

    # 构建建议
    lines = [
        f"产品: {product.name} (SKU: {product_sku})",
        "",
        "=== 现状分析 ===",
        f"当前总库存: {total_on_hand} {product.unit} (可用: {total_available})",
        f"库存总价值: {total_value:.2f} 元",
        f"近30天日均出库: {avg_daily_demand:.1f} {product.unit}/天",
    ]

    if avg_forecast_demand > 0:
        lines.append(f"预测日均需求: {avg_forecast_demand:.1f} {product.unit}/天")
        lines.append(f"未来14天预测总需求: {total_forecast_14d:.1f} {product.unit}")

    lines.extend([
        f"安全库存量: {safety_stock_qty:.0f} {product.unit} ({product.safety_stock_days}天)",
        f"再订货点: {reorder_point:.0f} {product.unit}",
        f"库存可维持天数: {days_of_stock:.1f} 天",
        "",
    ])

    # 生成具体建议
    lines.append("=== 调整建议 ===")

    suggestions = []

    if total_available <= 0:
        suggestions.append(
            f"[紧急-高优先级] 产品已缺货！建议立即采购至少 "
            f"{reorder_point:.0f} {product.unit} 以恢复安全库存水平。"
        )
    elif total_available < safety_stock_qty:
        shortage = safety_stock_qty - total_available
        suggestions.append(
            f"[紧急-高优先级] 库存低于安全库存 {shortage:.0f} {product.unit}，"
            f"建议立即补货 {reorder_point - total_available:.0f} {product.unit}。"
        )
    elif days_of_stock < product.lead_time_days:
        shortage = effective_daily_demand * (product.lead_time_days - days_of_stock + product.safety_stock_days)
        suggestions.append(
            f"[警告-中优先级] 库存可维持 {days_of_stock:.1f} 天，"
            f"小于补货提前期 {product.lead_time_days} 天，"
            f"建议尽快补货 {shortage:.0f} {product.unit}。"
        )
    elif days_of_stock > 90:
        excess = total_available - effective_daily_demand * 60
        if excess > 0:
            suggestions.append(
                f"[注意-低优先级] 库存可维持 {days_of_stock:.1f} 天，存在积压风险。"
                f"建议考虑促销或调拨减少 {excess:.0f} {product.unit} 库存。"
            )
    else:
        suggestions.append(
            f"[正常] 库存水平健康，可维持 {days_of_stock:.1f} 天。"
            f"当前无需紧急操作，建议持续监控。"
        )

    # 补货建议（如果有预测数据）
    if avg_forecast_demand > 0 and days_of_stock < product.lead_time_days + product.safety_stock_days:
        target_stock = effective_daily_demand * (product.lead_time_days + product.safety_stock_days)
        suggested_order = target_stock - total_available
        if suggested_order > 0:
            order_cost = suggested_order * float(product.unit_cost)
            suggestions.append(
                f"[采购建议] 建议采购量: {suggested_order:.0f} {product.unit}，"
                f"预计采购成本: {order_cost:.2f} 元，"
                f"采购后库存可维持 {product.lead_time_days + product.safety_stock_days} 天。"
            )

    for s in suggestions:
        lines.append(s)

    lines.append("")
    lines.append("=== 理由 ===")
    if effective_daily_demand > 0:
        lines.append(
            f"基于{'预测' if avg_forecast_demand > 0 else '历史'}日均需求 {effective_daily_demand:.1f} {product.unit}/天，"
            f"安全库存 {product.safety_stock_days} 天 + 补货提前期 {product.lead_time_days} 天，"
            f"计算得出再订货点为 {reorder_point:.0f} {product.unit}。"
        )
    else:
        lines.append(
            "该产品近30天无出库记录，无法计算日均需求。"
            "建议关注该产品是否为滞销品，考虑促销清仓。"
        )

    return "\n".join(lines)


async def _get_alert_summary_tool(db: AsyncSession, severity: str = "all") -> str:
    """
    获取最近的告警事件摘要

    Args:
        db: 异步数据库会话
        severity: 告警级别过滤，可选 all/low/medium/high/critical

    Returns:
        告警摘要信息字符串
    """
    from app.models.alert_event import AlertEvent

    # 构建查询条件
    conditions = []
    if severity and severity.lower() != "all":
        conditions.append(AlertEvent.severity == severity.lower())

    # 查询最近50条告警
    since = datetime.now(timezone.utc) - timedelta(days=7)
    conditions.append(AlertEvent.created_at >= since)

    stmt = (
        select(AlertEvent)
        .where(and_(*conditions))
        .order_by(desc(AlertEvent.created_at))
        .limit(50)
    )

    result = await db.execute(stmt)
    alerts = result.scalars().all()

    if not alerts:
        return f"最近7天内没有{'级别为 ' + severity if severity and severity.lower() != 'all' else ''}告警记录。"

    # 统计各级别数量
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    status_counts = {"new": 0, "acknowledged": 0, "resolved": 0}

    for alert in alerts:
        severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
        status_counts[alert.status] = status_counts.get(alert.status, 0) + 1

    lines = [
        f"最近7天告警摘要 (共 {len(alerts)} 条)",
        "",
        "按严重程度统计：",
        f"  - 紧急 (critical): {severity_counts['critical']} 条",
        f"  - 高 (high): {severity_counts['high']} 条",
        f"  - 中 (medium): {severity_counts['medium']} 条",
        f"  - 低 (low): {severity_counts['low']} 条",
        "",
        "按状态统计：",
        f"  - 待处理 (new): {status_counts['new']} 条",
        f"  - 已确认 (acknowledged): {status_counts['acknowledged']} 条",
        f"  - 已解决 (resolved): {status_counts['resolved']} 条",
        "",
        "最近告警详情（最多显示20条）：",
    ]

    display_alerts = alerts[:20]
    for alert in display_alerts:
        severity_map = {"critical": "紧急", "high": "高", "medium": "中", "low": "低"}
        status_map = {"new": "待处理", "acknowledged": "已确认", "resolved": "已解决"}
        created_str = alert.created_at.strftime("%m-%d %H:%M") if alert.created_at else "未知"
        lines.append(
            f"  [{severity_map.get(alert.severity, alert.severity)}] "
            f"[{status_map.get(alert.status, alert.status)}] "
            f"{created_str} - {alert.title}"
        )
        if alert.message:
            # 截断过长的消息
            msg = alert.message[:100] + "..." if len(alert.message) > 100 else alert.message
            lines.append(f"    {msg}")

    return "\n".join(lines)


async def _get_slow_moving_products_tool(db: AsyncSession, limit: int = 10) -> str:
    """
    获取周转率最低的产品列表（滞销品）

    Args:
        db: 异步数据库会话
        limit: 返回数量，默认 10

    Returns:
        滞销产品信息字符串
    """
    from app.models.product import Product
    from app.models.inventory_snapshot import InventorySnapshot
    from app.models.inventory_transaction import InventoryTransaction

    # 计算每个产品的周转率 = 近30天总出库量 / 平均库存
    since = datetime.now(timezone.utc) - timedelta(days=30)

    # 子查询：每个产品的平均库存
    avg_inventory_sub = (
        select(
            InventorySnapshot.product_id,
            func.avg(InventorySnapshot.quantity_on_hand).label("avg_inventory"),
        )
        .where(InventorySnapshot.timestamp >= since)
        .group_by(InventorySnapshot.product_id)
        .subquery()
    )

    # 子查询：每个产品近30天总出库量
    outbound_sub = (
        select(
            InventoryTransaction.product_id,
            func.sum(func.abs(InventoryTransaction.quantity_change)).label("total_outbound"),
        )
        .where(
            and_(
                InventoryTransaction.transaction_type == "outbound",
                InventoryTransaction.created_at >= since,
            )
        )
        .group_by(InventoryTransaction.product_id)
        .subquery()
    )

    # 主查询：计算周转率
    stmt = (
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.category,
            Product.unit,
            func.coalesce(avg_inventory_sub.c.avg_inventory, 0).label("avg_inventory"),
            func.coalesce(outbound_sub.c.total_outbound, 0).label("total_outbound_30d"),
        )
        .outerjoin(avg_inventory_sub, Product.id == avg_inventory_sub.c.product_id)
        .outerjoin(outbound_sub, Product.id == outbound_sub.c.product_id)
        .where(
            and_(
                Product.is_active == True,  # noqa: E712
                func.coalesce(avg_inventory_sub.c.avg_inventory, 0) > 0,
            )
        )
        .order_by(
            asc(
                func.coalesce(outbound_sub.c.total_outbound, 0)
                / func.nullif(func.coalesce(avg_inventory_sub.c.avg_inventory, 0), 0)
            )
        )
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return "当前没有活跃的产品库存数据。"

    lines = [
        f"滞销产品 TOP {len(rows)}（按周转率从低到高排列）",
        "",
        "周转率 = 近30天出库量 / 平均库存，值越低表示周转越慢。",
        "",
    ]

    for i, row in enumerate(rows, 1):
        avg_inv = float(row.avg_inventory)
        total_out = float(row.total_outbound_30d)
        turnover_rate = total_out / avg_inv if avg_inv > 0 else 0
        days_of_stock = avg_inv / (total_out / 30) if total_out > 0 else float("inf")

        lines.append(
            f"{i}. {row.name} (SKU: {row.sku})"
        )
        lines.append(
            f"   分类: {row.category or '未分类'} | 平均库存: {avg_inv:.0f} {row.unit} | "
            f"30天出库: {total_out:.0f} | 周转率: {turnover_rate:.2f} | "
            f"可维持天数: {days_of_stock:.0f}天"
        )

    return "\n".join(lines)


async def _get_fast_moving_products_tool(db: AsyncSession, limit: int = 10) -> str:
    """
    获取周转率最高的产品列表（畅销品）

    Args:
        db: 异步数据库会话
        limit: 返回数量，默认 10

    Returns:
        畅销产品信息字符串
    """
    from app.models.product import Product
    from app.models.inventory_snapshot import InventorySnapshot
    from app.models.inventory_transaction import InventoryTransaction

    since = datetime.now(timezone.utc) - timedelta(days=30)

    # 子查询：每个产品的平均库存
    avg_inventory_sub = (
        select(
            InventorySnapshot.product_id,
            func.avg(InventorySnapshot.quantity_on_hand).label("avg_inventory"),
        )
        .where(InventorySnapshot.timestamp >= since)
        .group_by(InventorySnapshot.product_id)
        .subquery()
    )

    # 子查询：每个产品近30天总出库量
    outbound_sub = (
        select(
            InventoryTransaction.product_id,
            func.sum(func.abs(InventoryTransaction.quantity_change)).label("total_outbound"),
        )
        .where(
            and_(
                InventoryTransaction.transaction_type == "outbound",
                InventoryTransaction.created_at >= since,
            )
        )
        .group_by(InventoryTransaction.product_id)
        .subquery()
    )

    # 主查询：按周转率降序排列
    stmt = (
        select(
            Product.id,
            Product.sku,
            Product.name,
            Product.category,
            Product.unit,
            func.coalesce(avg_inventory_sub.c.avg_inventory, 0).label("avg_inventory"),
            func.coalesce(outbound_sub.c.total_outbound, 0).label("total_outbound_30d"),
        )
        .outerjoin(avg_inventory_sub, Product.id == avg_inventory_sub.c.product_id)
        .outerjoin(outbound_sub, Product.id == outbound_sub.c.product_id)
        .where(
            and_(
                Product.is_active == True,  # noqa: E712
                func.coalesce(avg_inventory_sub.c.avg_inventory, 0) > 0,
                func.coalesce(outbound_sub.c.total_outbound, 0) > 0,
            )
        )
        .order_by(
            desc(
                func.coalesce(outbound_sub.c.total_outbound, 0)
                / func.nullif(func.coalesce(avg_inventory_sub.c.avg_inventory, 0), 0)
            )
        )
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return "当前没有活跃的产品出库数据。"

    lines = [
        f"畅销产品 TOP {len(rows)}（按周转率从高到低排列）",
        "",
        "周转率 = 近30天出库量 / 平均库存，值越高表示周转越快。",
        "",
    ]

    for i, row in enumerate(rows, 1):
        avg_inv = float(row.avg_inventory)
        total_out = float(row.total_outbound_30d)
        turnover_rate = total_out / avg_inv if avg_inv > 0 else 0
        days_of_stock = avg_inv / (total_out / 30) if total_out > 0 else float("inf")

        lines.append(
            f"{i}. {row.name} (SKU: {row.sku})"
        )
        lines.append(
            f"   分类: {row.category or '未分类'} | 平均库存: {avg_inv:.0f} {row.unit} | "
            f"30天出库: {total_out:.0f} | 周转率: {turnover_rate:.2f} | "
            f"可维持天数: {days_of_stock:.0f}天"
        )

    return "\n".join(lines)


# ==================== AI Agent 服务 ====================

class AIAgentService:
    """
    AI 智能助手服务

    基于 LangChain Tool-Calling Agent，集成 OpenAI GPT-4o-mini 模型，
    提供库存管理领域的自然语言交互能力。

    使用方式：
        service = AIAgentService(db_session)
        async for chunk in service.chat("查询SKU-001的库存"):
            print(chunk, end="")
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化 AI Agent 服务

        Args:
            db: 异步数据库会话
        """
        self.db = db
        self._available = False
        self._agent_executor = None
        self._error_message = None

        # 检查依赖
        if not _check_dependencies():
            self._error_message = (
                "AI 助手服务暂不可用：缺少必要的依赖包。"
                "请安装 langchain-openai 和 langchain 相关依赖："
                "pip install langchain-openai langchain langchain-core"
            )
            logger.warning(self._error_message)
            return

        # 检查 API Key
        settings = get_settings()
        if not settings.openai_api_key:
            self._error_message = (
                "AI 助手服务暂不可用：未配置 OpenAI API Key。"
                "请在环境变量中设置 INVENTORY_OPENAI_API_KEY。"
            )
            logger.warning(self._error_message)
            return

        try:
            self._initialize_agent(settings)
            self._available = True
            logger.info("AI Agent 服务初始化成功")
        except Exception as e:
            self._error_message = f"AI 助手服务初始化失败: {str(e)}"
            logger.error(self._error_message, exc_info=True)

    def _initialize_agent(self, settings) -> None:
        """
        初始化 LangChain Agent

        Args:
            settings: 应用配置
        """
        from langchain_openai import ChatOpenAI
        from langchain.agents import create_tool_calling_agent, AgentExecutor
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
        from langchain_core.tools import StructuredTool

        # 初始化 LLM
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=settings.openai_api_key,
            max_tokens=settings.openai_max_tokens,
        )

        # 创建工具列表，每个工具闭包捕获 self.db
        tools = [
            StructuredTool.from_function(
                coroutine=lambda product_sku: _get_inventory_status_tool(self.db, product_sku),
                name="get_inventory_status",
                description=(
                    "查询指定 SKU 产品的当前库存状态。"
                    "返回产品基本信息、各仓库库存数量、库存价值等。"
                    "参数: product_sku - 产品SKU编码（字符串）。"
                ),
            ),
            StructuredTool.from_function(
                coroutine=lambda product_sku, days=14: _get_demand_forecast_tool(
                    self.db, product_sku, days,
                ),
                name="get_demand_forecast",
                description=(
                    "获取指定 SKU 产品的需求预测数据。"
                    "返回未来若干天的预测需求量、预测区间和使用的模型信息。"
                    "参数: product_sku - 产品SKU编码（字符串）, "
                    "days - 预测天数（整数，默认14）。"
                ),
            ),
            StructuredTool.from_function(
                coroutine=lambda product_sku: _suggest_inventory_adjustment_tool(self.db, product_sku),
                name="suggest_inventory_adjustment",
                description=(
                    "生成指定 SKU 产品的库存调整建议。"
                    "基于当前库存、需求预测和安全库存参数，给出采购量、调拨或促销建议。"
                    "参数: product_sku - 产品SKU编码（字符串）。"
                ),
            ),
            StructuredTool.from_function(
                coroutine=lambda severity="all": _get_alert_summary_tool(self.db, severity),
                name="get_alert_summary",
                description=(
                    "获取最近的告警事件摘要。"
                    "返回告警按严重程度和状态的统计，以及最近告警的详细信息。"
                    "参数: severity - 告警级别过滤（字符串，可选值: all/low/medium/high/critical，默认all）。"
                ),
            ),
            StructuredTool.from_function(
                coroutine=lambda limit=10: _get_slow_moving_products_tool(self.db, limit),
                name="get_slow_moving_products",
                description=(
                    "获取周转率最低的产品列表（滞销品）。"
                    "返回按周转率从低到高排列的产品，包含库存量、出库量和周转率。"
                    "参数: limit - 返回数量（整数，默认10）。"
                ),
            ),
            StructuredTool.from_function(
                coroutine=lambda limit=10: _get_fast_moving_products_tool(self.db, limit),
                name="get_fast_moving_products",
                description=(
                    "获取周转率最高的产品列表（畅销品）。"
                    "返回按周转率从高到低排列的产品，包含库存量、出库量和周转率。"
                    "参数: limit - 返回数量（整数，默认10）。"
                ),
            ),
        ]

        # 构建 Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 创建 Agent
        agent = create_tool_calling_agent(self.llm, tools, prompt)

        # 创建 AgentExecutor
        self._agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            return_intermediate_steps=False,
            max_iterations=5,
            handle_parsing_errors=True,
        )

    @property
    def is_available(self) -> bool:
        """检查 AI Agent 服务是否可用"""
        return self._available

    async def chat(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式对话接口

        将用户消息发送给 AI Agent，以异步生成器方式流式返回响应内容。

        Args:
            message: 用户消息
            history: 对话历史，格式为 [{"role": "user/assistant", "content": "..."}]

        Yields:
            响应文本片段
        """
        # 检查服务可用性
        if not self._available:
            yield self._error_message or "AI 助手服务暂不可用，请稍后再试。"
            return

        if not message or not message.strip():
            yield "请输入有效的问题。"
            return

        # 构建 LangChain 消息历史
        from langchain_core.messages import HumanMessage, AIMessage

        lc_history = []
        if history:
            for msg in history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    lc_history.append(HumanMessage(content=content))
                elif role == "assistant":
                    lc_history.append(AIMessage(content=content))

        try:
            # 使用 astream 进行流式输出
            async for event in self._agent_executor.astream(
                {"input": message, "chat_history": lc_history},
            ):
                if isinstance(event, dict):
                    # AgentExecutor 的 astream 返回格式
                    output = event.get("output", "")
                    if output:
                        yield output
                elif isinstance(event, str):
                    yield event

        except Exception as e:
            logger.error("AI Agent 对话出错: %s", e, exc_info=True)
            yield f"抱歉，处理您的问题时出现了错误：{str(e)}。请稍后再试或联系管理员。"

    async def chat_sync(
        self,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        非流式对话接口（用于测试）

        将用户消息发送给 AI Agent，等待完整响应后返回。

        Args:
            message: 用户消息
            history: 对话历史

        Returns:
            完整的响应文本
        """
        # 检查服务可用性
        if not self._available:
            return self._error_message or "AI 助手服务暂不可用，请稍后再试。"

        if not message or not message.strip():
            return "请输入有效的问题。"

        # 构建 LangChain 消息历史
        from langchain_core.messages import HumanMessage, AIMessage

        lc_history = []
        if history:
            for msg in history:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role == "user":
                    lc_history.append(HumanMessage(content=content))
                elif role == "assistant":
                    lc_history.append(AIMessage(content=content))

        try:
            result = await self._agent_executor.ainvoke(
                {"input": message, "chat_history": lc_history},
            )
            return result.get("output", "抱歉，未能获取到有效回复。")

        except Exception as e:
            logger.error("AI Agent 同步对话出错: %s", e, exc_info=True)
            return f"抱歉，处理您的问题时出现了错误：{str(e)}。请稍后再试或联系管理员。"
