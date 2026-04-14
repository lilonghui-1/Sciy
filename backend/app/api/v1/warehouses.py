# -*- coding: utf-8 -*-
"""
仓库管理路由

处理仓库 CRUD 操作，包括列表查询、创建、详情、更新和停用。
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import NotFoundException, ConflictException
from app.crud.base import BaseCRUD
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseUpdate,
    WarehouseResponse,
    WarehouseListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/warehouses", tags=["仓库管理"])

warehouse_crud = BaseCRUD(Warehouse)


@router.get("/", response_model=PaginatedResponse[WarehouseListResponse], summary="获取仓库列表")
async def get_warehouses(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    is_active: bool | None = Query(default=None, description="是否启用"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[WarehouseListResponse]:
    """
    获取仓库列表

    支持分页和状态筛选。
    """
    skip = (page - 1) * page_size

    stmt = select(Warehouse)
    count_stmt = select(func.count()).select_from(Warehouse)

    if is_active is not None:
        stmt = stmt.where(Warehouse.is_active == is_active)
        count_stmt = count_stmt.where(Warehouse.is_active == is_active)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Warehouse.created_at.desc()).offset(skip).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return PaginatedResponse.create(
        items=[WarehouseListResponse.model_validate(w) for w in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建仓库",
)
async def create_warehouse(
    warehouse_in: WarehouseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WarehouseResponse:
    """
    创建新仓库

    - 检查仓库编码是否已存在
    - 创建仓库记录
    """
    existing = await warehouse_crud.get_by_field(db, field_name="code", value=warehouse_in.code)
    if existing:
        raise ConflictException(detail=f"仓库编码 '{warehouse_in.code}' 已存在")

    warehouse = await warehouse_crud.create(db, obj_in=warehouse_in.model_dump())

    logger.info(f"仓库创建成功: {warehouse.name} (编码: {warehouse.code}, ID: {warehouse.id})")
    return WarehouseResponse.model_validate(warehouse)


@router.get("/{warehouse_id}", response_model=WarehouseResponse, summary="获取仓库详情")
async def get_warehouse(
    warehouse_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WarehouseResponse:
    """
    根据 ID 获取仓库详细信息
    """
    warehouse = await warehouse_crud.get(db, id=warehouse_id)
    if not warehouse:
        raise NotFoundException(detail=f"仓库 (ID: {warehouse_id}) 不存在")

    return WarehouseResponse.model_validate(warehouse)


@router.put("/{warehouse_id}", response_model=WarehouseResponse, summary="更新仓库信息")
async def update_warehouse(
    warehouse_id: int,
    warehouse_in: WarehouseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> WarehouseResponse:
    """
    更新指定仓库的信息

    仅更新请求中提供的字段（部分更新）。
    """
    warehouse = await warehouse_crud.get(db, id=warehouse_id)
    if not warehouse:
        raise NotFoundException(detail=f"仓库 (ID: {warehouse_id}) 不存在")

    updated_warehouse = await warehouse_crud.update(
        db,
        id=warehouse_id,
        obj_in=warehouse_in.model_dump(exclude_unset=True),
    )
    if not updated_warehouse:
        raise NotFoundException(detail=f"仓库 (ID: {warehouse_id}) 不存在")

    logger.info(f"仓库信息已更新: {warehouse.name} (ID: {warehouse_id})")
    return WarehouseResponse.model_validate(updated_warehouse)


@router.delete("/{warehouse_id}", summary="停用仓库", status_code=status.HTTP_200_OK)
async def delete_warehouse(
    warehouse_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """
    停用指定仓库

    将仓库标记为未启用状态，不会从数据库中物理删除。
    """
    warehouse = await warehouse_crud.get(db, id=warehouse_id)
    if not warehouse:
        raise NotFoundException(detail=f"仓库 (ID: {warehouse_id}) 不存在")

    await warehouse_crud.update(db, id=warehouse_id, obj_in={"is_active": False})

    logger.info(f"仓库已停用: {warehouse.name} (ID: {warehouse_id})")
    return MessageResponse(message=f"仓库 '{warehouse.name}' 已成功停用")
