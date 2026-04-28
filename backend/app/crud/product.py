# -*- coding: utf-8 -*-
"""
产品 CRUD 操作

提供产品相关的数据库操作，包括按 SKU 查询和带过滤条件的列表查询。
"""
from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models.product import Product

logger = logging.getLogger(__name__)


class ProductCRUD(BaseCRUD[Product]):
    """产品 CRUD 操作类"""

    def __init__(self) -> None:
        super().__init__(Product)

    async def get_by_sku(self, db: AsyncSession, *, sku: str) -> Product | None:
        """
        根据 SKU 获取产品

        Args:
            db: 数据库会话
            sku: SKU 编码

        Returns:
            产品实例，未找到返回 None
        """
        stmt = select(Product).where(Product.sku == sku)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_with_filters(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> tuple[Sequence[Product], int]:
        """
        带过滤条件的产品列表查询

        Args:
            db: 数据库会话
            skip: 跳过记录数
            limit: 返回记录数上限
            category: 分类筛选
            is_active: 是否启用筛选
            search: 搜索关键词（匹配名称、SKU、描述）

        Returns:
            (产品列表, 总数) 元组
        """
        # 基础查询
        stmt = select(Product)
        count_stmt = select(func.count()).select_from(Product)

        # 应用过滤条件
        conditions = []
        if category is not None:
            conditions.append(Product.category == category)
        if is_active is not None:
            conditions.append(Product.is_active == is_active)
        if search:
            search_pattern = f"%{search}%"
            conditions.append(
                or_(
                    func.lower(Product.name).like(func.lower(search_pattern)),
                    func.lower(Product.sku).like(func.lower(search_pattern)),
                    func.lower(Product.description).like(func.lower(search_pattern)),
                    func.lower(Product.barcode).like(func.lower(search_pattern)),
                )
            )

        for condition in conditions:
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        # 获取总数
        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 排序和分页
        stmt = stmt.order_by(Product.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()

        return items, total


# 创建全局产品 CRUD 实例
product_crud = ProductCRUD()
