# -*- coding: utf-8 -*-
"""
产品管理路由

处理产品 CRUD 操作，包括列表查询（搜索/过滤/分页）、创建、详情、更新和软删除。
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import NotFoundException, ConflictException
from app.crud.product import product_crud
from app.models.user import User
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/products", tags=["产品管理"])


@router.get("/", response_model=PaginatedResponse[ProductListResponse], summary="获取产品列表")
async def get_products(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    category: str | None = Query(default=None, description="分类筛选"),
    product_type: str | None = Query(default=None, description="产品类型筛选: raw_material/finished_good"),
    is_active: bool | None = Query(default=None, description="是否启用"),
    search: str | None = Query(default=None, min_length=1, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[ProductListResponse]:
    """
    获取产品列表

    支持分页、搜索（匹配名称/SKU/描述）、分类筛选和状态筛选。
    """
    skip = (page - 1) * page_size
    items, total = await product_crud.get_multi_with_filters(
        db,
        skip=skip,
        limit=page_size,
        category=category,
        product_type=product_type,
        is_active=is_active,
        search=search,
    )

    return PaginatedResponse.create(
        items=[ProductListResponse.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建产品",
)
async def create_product(
    product_in: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProductResponse:
    """
    创建新产品

    - 检查 SKU 是否已存在
    - 创建产品记录
    """
    existing = await product_crud.get_by_sku(db, sku=product_in.sku)
    if existing:
        raise ConflictException(detail=f"SKU '{product_in.sku}' 已存在")

    product = await product_crud.create(db, obj_in=product_in.model_dump())

    logger.info(f"产品创建成功: {product.name} (SKU: {product.sku}, ID: {product.id})")
    return ProductResponse.model_validate(product)


@router.get("/{product_id}", response_model=ProductResponse, summary="获取产品详情")
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProductResponse:
    """
    根据 ID 获取产品详细信息
    """
    product = await product_crud.get(db, id=product_id)
    if not product:
        raise NotFoundException(detail=f"产品 (ID: {product_id}) 不存在")

    return ProductResponse.model_validate(product)


@router.put("/{product_id}", response_model=ProductResponse, summary="更新产品信息")
async def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ProductResponse:
    """
    更新指定产品的信息

    仅更新请求中提供的字段（部分更新）。
    """
    product = await product_crud.get(db, id=product_id)
    if not product:
        raise NotFoundException(detail=f"产品 (ID: {product_id}) 不存在")

    updated_product = await product_crud.update(
        db,
        id=product_id,
        obj_in=product_in.model_dump(exclude_unset=True),
    )
    if not updated_product:
        raise NotFoundException(detail=f"产品 (ID: {product_id}) 不存在")

    logger.info(f"产品信息已更新: {product.name} (ID: {product_id})")
    return ProductResponse.model_validate(updated_product)


@router.delete("/{product_id}", summary="删除产品（软删除）", status_code=status.HTTP_200_OK)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """
    软删除指定产品

    将产品标记为未启用状态，不会从数据库中物理删除。
    """
    product = await product_crud.get(db, id=product_id)
    if not product:
        raise NotFoundException(detail=f"产品 (ID: {product_id}) 不存在")

    await product_crud.update(db, id=product_id, obj_in={"is_active": False})

    logger.info(f"产品已软删除: {product.name} (ID: {product_id})")
    return MessageResponse(message=f"产品 '{product.name}' 已成功删除")
