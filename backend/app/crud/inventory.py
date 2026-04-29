# -*- coding: utf-8 -*-
"""
库存 CRUD 操作

提供库存快照和库存事务的数据库操作。
"""
from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_snapshot import InventorySnapshot
from app.models.inventory_transaction import InventoryTransaction

logger = logging.getLogger(__name__)


class InventoryCRUD:
    """库存 CRUD 操作类（不继承 BaseCRUD，因为涉及两个模型）"""

    # ==================== 快照操作 ====================

    async def create_snapshot(
        self,
        db: AsyncSession,
        *,
        obj_in: dict,
    ) -> InventorySnapshot:
        """
        创建库存快照

        Args:
            db: 数据库会话
            obj_in: 快照数据字典

        Returns:
            新创建的快照实例
        """
        db_obj = InventorySnapshot(**obj_in)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get_latest_snapshot(
        self,
        db: AsyncSession,
        *,
        product_id: int,
        warehouse_id: int,
    ) -> InventorySnapshot | None:
        """
        获取指定产品和仓库的最新库存快照

        Args:
            db: 数据库会话
            product_id: 产品 ID
            warehouse_id: 仓库 ID

        Returns:
            最新的库存快照，未找到返回 None
        """
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
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_snapshots(
        self,
        db: AsyncSession,
        *,
        product_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[InventorySnapshot], int]:
        """
        获取库存快照列表（支持过滤和分页）

        Args:
            db: 数据库会话
            product_id: 产品 ID 筛选
            warehouse_id: 仓库 ID 筛选
            skip: 跳过记录数
            limit: 返回记录数上限

        Returns:
            (快照列表, 总数) 元组
        """
        stmt = select(InventorySnapshot)
        count_stmt = select(func.count()).select_from(InventorySnapshot)

        conditions = []
        if product_id is not None:
            conditions.append(InventorySnapshot.product_id == product_id)
        if warehouse_id is not None:
            conditions.append(InventorySnapshot.warehouse_id == warehouse_id)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(desc(InventorySnapshot.timestamp)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()

        return items, total

    # ==================== 事务操作 ====================

    async def create_transaction(
        self,
        db: AsyncSession,
        *,
        obj_in: dict,
    ) -> InventoryTransaction:
        """
        创建库存事务

        Args:
            db: 数据库会话
            obj_in: 事务数据字典

        Returns:
            新创建的事务实例
        """
        db_obj = InventoryTransaction(**obj_in)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get_transactions(
        self,
        db: AsyncSession,
        *,
        product_id: Optional[int] = None,
        warehouse_id: Optional[int] = None,
        transaction_type: Optional[str] = None,
        batch_no: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[InventoryTransaction], int]:
        """
        获取库存事务列表（支持过滤和分页）

        Args:
            db: 数据库会话
            product_id: 产品 ID 筛选
            warehouse_id: 仓库 ID 筛选
            transaction_type: 事务类型筛选
            skip: 跳过记录数
            limit: 返回记录数上限

        Returns:
            (事务列表, 总数) 元组
        """
        stmt = select(InventoryTransaction)
        count_stmt = select(func.count()).select_from(InventoryTransaction)

        conditions = []
        if product_id is not None:
            conditions.append(InventoryTransaction.product_id == product_id)
        if warehouse_id is not None:
            conditions.append(InventoryTransaction.warehouse_id == warehouse_id)
        if transaction_type is not None:
            conditions.append(InventoryTransaction.transaction_type == transaction_type)
        if batch_no is not None:
            conditions.append(InventoryTransaction.batch_no == batch_no)

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        stmt = stmt.order_by(desc(InventoryTransaction.created_at)).offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()

        return items, total


# 创建全局库存 CRUD 实例
inventory_crud = InventoryCRUD()
