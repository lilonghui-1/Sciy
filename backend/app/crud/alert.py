# -*- coding: utf-8 -*-
"""
预警 CRUD 操作

提供预警规则和预警事件的数据库操作。
"""
from __future__ import annotations

import logging
from typing import Optional, Sequence
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.alert_rule import AlertRule
from app.models.alert_event import AlertEvent

logger = logging.getLogger(__name__)


class AlertRuleCRUD(BaseCRUD[AlertRule]):
    """预警规则 CRUD 操作类"""

    def __init__(self) -> None:
        super().__init__(AlertRule)

    async def get_active_rules(self, db: AsyncSession) -> Sequence[AlertRule]:
        """
        获取所有活跃的预警规则

        Args:
            db: 数据库会话

        Returns:
            活跃预警规则列表
        """
        stmt = (
            select(AlertRule)
            .where(AlertRule.is_active == True)  # noqa: E712
            .order_by(AlertRule.created_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()


class AlertEventCRUD(BaseCRUD[AlertEvent]):
    """预警事件 CRUD 操作类"""

    def __init__(self) -> None:
        super().__init__(AlertEvent)

    async def get_by_product(
        self,
        db: AsyncSession,
        *,
        product_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AlertEvent], int]:
        """
        获取指定产品的预警事件

        Args:
            db: 数据库会话
            product_id: 产品 ID
            skip: 跳过记录数
            limit: 返回记录数上限

        Returns:
            (事件列表, 总数) 元组
        """
        stmt = select(AlertEvent).where(AlertEvent.product_id == product_id)
        count_stmt = (
            select(func.count())
            .select_from(AlertEvent)
            .where(AlertEvent.product_id == product_id)
        )

        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(desc(AlertEvent.created_at)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()

        return items, total

    async def get_recent(
        self,
        db: AsyncSession,
        *,
        hours: int = 24,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AlertEvent], int]:
        """
        获取最近的预警事件

        Args:
            db: 数据库会话
            hours: 查询最近多少小时的事件
            severity: 严重级别筛选
            status: 状态筛选
            skip: 跳过记录数
            limit: 返回记录数上限

        Returns:
            (事件列表, 总数) 元组
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        conditions = [AlertEvent.created_at >= since]
        if severity is not None:
            conditions.append(AlertEvent.severity == severity)
        if status is not None:
            conditions.append(AlertEvent.status == status)

        stmt = select(AlertEvent).where(and_(*conditions))
        count_stmt = select(func.count()).select_from(AlertEvent).where(and_(*conditions))

        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(desc(AlertEvent.created_at)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()

        return items, total


# 创建全局预警 CRUD 实例
alert_rule_crud = AlertRuleCRUD()
alert_event_crud = AlertEventCRUD()
