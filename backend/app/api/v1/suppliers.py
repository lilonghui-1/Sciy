# -*- coding: utf-8 -*-
"""
供应商管理路由

处理供应商 CRUD 操作，包括列表查询、创建、详情、更新和停用。
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import NotFoundException, ConflictException
from app.crud.base import BaseCRUD
from app.models.user import User
from app.models.supplier import Supplier
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
    SupplierListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/suppliers", tags=["供应商管理"])

supplier_crud = BaseCRUD(Supplier)


@router.get("/", response_model=PaginatedResponse[SupplierListResponse], summary="获取供应商列表")
async def get_suppliers(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    is_active: bool | None = Query(default=None, description="是否启用"),
    search: str | None = Query(default=None, min_length=1, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[SupplierListResponse]:
    """
    获取供应商列表

    支持分页、搜索和状态筛选。
    """
    skip = (page - 1) * page_size

    stmt = select(Supplier)
    count_stmt = select(func.count()).select_from(Supplier)

    if is_active is not None:
        stmt = stmt.where(Supplier.is_active == is_active)
        count_stmt = count_stmt.where(Supplier.is_active == is_active)

    if search:
        search_pattern = f"%{search}%"
        from sqlalchemy import or_
        search_condition = or_(
            Supplier.name.ilike(search_pattern),
            Supplier.code.ilike(search_pattern),
            Supplier.contact_person.ilike(search_pattern),
        )
        stmt = stmt.where(search_condition)
        count_stmt = count_stmt.where(search_condition)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Supplier.created_at.desc()).offset(skip).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return PaginatedResponse.create(
        items=[SupplierListResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建供应商",
)
async def create_supplier(
    supplier_in: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SupplierResponse:
    """
    创建新供应商

    - 检查供应商编码是否已存在
    - 创建供应商记录
    """
    existing = await supplier_crud.get_by_field(db, field_name="code", value=supplier_in.code)
    if existing:
        raise ConflictException(detail=f"供应商编码 '{supplier_in.code}' 已存在")

    supplier = await supplier_crud.create(db, obj_in=supplier_in.model_dump())

    logger.info(f"供应商创建成功: {supplier.name} (编码: {supplier.code}, ID: {supplier.id})")
    return SupplierResponse.model_validate(supplier)


@router.get("/{supplier_id}", response_model=SupplierResponse, summary="获取供应商详情")
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SupplierResponse:
    """
    根据 ID 获取供应商详细信息
    """
    supplier = await supplier_crud.get(db, id=supplier_id)
    if not supplier:
        raise NotFoundException(detail=f"供应商 (ID: {supplier_id}) 不存在")

    return SupplierResponse.model_validate(supplier)


@router.put("/{supplier_id}", response_model=SupplierResponse, summary="更新供应商信息")
async def update_supplier(
    supplier_id: int,
    supplier_in: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SupplierResponse:
    """
    更新指定供应商的信息

    仅更新请求中提供的字段（部分更新）。
    """
    supplier = await supplier_crud.get(db, id=supplier_id)
    if not supplier:
        raise NotFoundException(detail=f"供应商 (ID: {supplier_id}) 不存在")

    updated_supplier = await supplier_crud.update(
        db,
        id=supplier_id,
        obj_in=supplier_in.model_dump(exclude_unset=True),
    )
    if not updated_supplier:
        raise NotFoundException(detail=f"供应商 (ID: {supplier_id}) 不存在")

    logger.info(f"供应商信息已更新: {supplier.name} (ID: {supplier_id})")
    return SupplierResponse.model_validate(updated_supplier)


@router.delete("/{supplier_id}", summary="停用供应商", status_code=status.HTTP_200_OK)
async def delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """
    停用指定供应商

    将供应商标记为未启用状态，不会从数据库中物理删除。
    """
    supplier = await supplier_crud.get(db, id=supplier_id)
    if not supplier:
        raise NotFoundException(detail=f"供应商 (ID: {supplier_id}) 不存在")

    await supplier_crud.update(db, id=supplier_id, obj_in={"is_active": False})

    logger.info(f"供应商已停用: {supplier.name} (ID: {supplier_id})")
    return MessageResponse(message=f"供应商 '{supplier.name}' 已成功停用")
