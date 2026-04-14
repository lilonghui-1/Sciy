# -*- coding: utf-8 -*-
"""
用户管理路由

处理用户列表查询、用户详情、更新和停用操作。
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user, get_current_admin_user
from app.core.exceptions import NotFoundException, ForbiddenException
from app.crud.user import user_crud
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.user import UserResponse, UserListResponse, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("/", response_model=PaginatedResponse[UserListResponse], summary="获取用户列表")
async def get_users(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> PaginatedResponse[UserListResponse]:
    """
    获取系统用户列表（仅管理员）

    支持分页查询。
    """
    skip = (page - 1) * page_size
    users = await user_crud.get_multi(db, skip=skip, limit=page_size, order_by="created_at desc")
    total = await user_crud.count(db)

    return PaginatedResponse.create(
        items=[UserListResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=UserResponse, summary="获取用户详情")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    根据 ID 获取用户详细信息

    普通用户只能查看自己的信息，管理员可以查看所有用户。
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise ForbiddenException(detail="您没有权限查看其他用户的信息")

    user = await user_crud.get(db, id=user_id)
    if not user:
        raise NotFoundException(detail=f"用户 (ID: {user_id}) 不存在")

    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse, summary="更新用户信息")
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    更新指定用户的信息

    普通用户只能更新自己的信息（不能修改角色和状态），
    管理员可以更新所有用户的信息。
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise ForbiddenException(detail="您没有权限修改其他用户的信息")

    # 普通用户不能修改角色和激活状态
    if current_user.role != "admin":
        if user_in.role is not None:
            raise ForbiddenException(detail="普通用户不能修改角色")
        if user_in.is_active is not None:
            raise ForbiddenException(detail="普通用户不能修改激活状态")

    user = await user_crud.get(db, id=user_id)
    if not user:
        raise NotFoundException(detail=f"用户 (ID: {user_id}) 不存在")

    updated_user = await user_crud.update(db, id=user_id, obj_in=user_in.model_dump(exclude_unset=True))
    if not updated_user:
        raise NotFoundException(detail=f"用户 (ID: {user_id}) 不存在")

    logger.info(f"用户信息已更新: {user.username} (ID: {user_id})")
    return UserResponse.model_validate(updated_user)


@router.delete("/{user_id}", summary="停用用户", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> dict:
    """
    停用指定用户（仅管理员）

    执行软删除操作，将用户标记为未激活状态。
    """
    if current_user.id == user_id:
        raise ForbiddenException(detail="不能停用自己的账户")

    user = await user_crud.get(db, id=user_id)
    if not user:
        raise NotFoundException(detail=f"用户 (ID: {user_id}) 不存在")

    await user_crud.update(db, id=user_id, obj_in={"is_active": False})

    logger.info(f"用户已停用: {user.username} (ID: {user_id})")
    return {"message": f"用户 '{user.username}' 已成功停用", "success": True}
