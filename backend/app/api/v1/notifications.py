# -*- coding: utf-8 -*-
"""
通知服务路由

处理通知日志查询和通知偏好设置。
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import NotFoundException
from app.models.user import User
from app.models.notification_log import NotificationLog
from app.models.notification import NotificationPreference
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.notification import (
    NotificationLogResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["通知服务"])


@router.get(
    "/",
    response_model=PaginatedResponse[NotificationLogResponse],
    summary="获取通知列表",
)
async def get_notifications(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    is_read: bool | None = Query(default=None, description="是否已读"),
    channel: str | None = Query(default=None, description="通知渠道筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[NotificationLogResponse]:
    """
    获取当前用户的通知日志列表

    支持按已读状态和通知渠道筛选，支持分页。
    """
    skip = (page - 1) * page_size

    stmt = select(NotificationLog).where(NotificationLog.user_id == current_user.id)
    count_stmt = (
        select(func.count())
        .select_from(NotificationLog)
        .where(NotificationLog.user_id == current_user.id)
    )

    if is_read is not None:
        stmt = stmt.where(NotificationLog.is_read == is_read)
        count_stmt = count_stmt.where(NotificationLog.is_read == is_read)
    if channel is not None:
        stmt = stmt.where(NotificationLog.channel == channel)
        count_stmt = count_stmt.where(NotificationLog.channel == channel)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    from sqlalchemy import desc
    stmt = stmt.order_by(desc(NotificationLog.created_at)).offset(skip).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return PaginatedResponse.create(
        items=[NotificationLogResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/preferences", response_model=NotificationPreferenceResponse, summary="获取通知偏好设置")
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationPreferenceResponse:
    """
    获取当前用户的通知偏好设置

    如果用户尚未设置偏好，则自动创建默认偏好。
    """
    stmt = select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    preference = result.scalar_one_or_none()

    if not preference:
        # 创建默认偏好
        preference = NotificationPreference(user_id=current_user.id)
        db.add(preference)
        await db.flush()
        await db.refresh(preference)

    return NotificationPreferenceResponse.model_validate(preference)


@router.put("/preferences", response_model=NotificationPreferenceResponse, summary="更新通知偏好设置")
async def update_notification_preferences(
    pref_in: NotificationPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> NotificationPreferenceResponse:
    """
    更新当前用户的通知偏好设置

    仅更新请求中提供的字段（部分更新）。
    """
    stmt = select(NotificationPreference).where(
        NotificationPreference.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    preference = result.scalar_one_or_none()

    if not preference:
        # 创建默认偏好后再更新
        preference = NotificationPreference(user_id=current_user.id)
        db.add(preference)
        await db.flush()
        await db.refresh(preference)

    # 更新字段
    update_data = pref_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(preference, key, value)

    await db.flush()
    await db.refresh(preference)

    logger.info(f"通知偏好已更新: 用户ID={current_user.id}")
    return NotificationPreferenceResponse.model_validate(preference)
