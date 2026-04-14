# -*- coding: utf-8 -*-
"""
预警管理路由

处理预警规则和预警事件的 CRUD 操作。
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import NotFoundException
from app.crud.alert import alert_rule_crud, alert_event_crud
from app.models.user import User
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.alert import (
    AlertRuleCreate,
    AlertRuleUpdate,
    AlertRuleResponse,
    AlertEventResponse,
    AlertEventAcknowledge,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["预警管理"])


# ==================== 预警规则路由 ====================

@router.get("/rules", response_model=list[AlertRuleResponse], summary="获取预警规则列表")
async def get_alert_rules(
    is_active: bool | None = Query(default=None, description="是否启用"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[AlertRuleResponse]:
    """
    获取预警规则列表

    支持按启用状态筛选。
    """
    if is_active is True:
        rules = await alert_rule_crud.get_active_rules(db)
    else:
        rules = await alert_rule_crud.get_multi(db, limit=1000, order_by="created_at desc")

    return [AlertRuleResponse.model_validate(r) for r in rules]


@router.post(
    "/rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建预警规则",
)
async def create_alert_rule(
    rule_in: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AlertRuleResponse:
    """
    创建新的预警规则

    定义库存预警的触发条件和通知方式。
    """
    rule = await alert_rule_crud.create(db, obj_in=rule_in.model_dump())

    logger.info(f"预警规则创建成功: {rule.name} (ID: {rule.id})")
    return AlertRuleResponse.model_validate(rule)


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse, summary="更新预警规则")
async def update_alert_rule(
    rule_id: int,
    rule_in: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AlertRuleResponse:
    """
    更新指定预警规则

    仅更新请求中提供的字段（部分更新）。
    """
    rule = await alert_rule_crud.get(db, id=rule_id)
    if not rule:
        raise NotFoundException(detail=f"预警规则 (ID: {rule_id}) 不存在")

    updated_rule = await alert_rule_crud.update(
        db,
        id=rule_id,
        obj_in=rule_in.model_dump(exclude_unset=True),
    )
    if not updated_rule:
        raise NotFoundException(detail=f"预警规则 (ID: {rule_id}) 不存在")

    logger.info(f"预警规则已更新: {rule.name} (ID: {rule_id})")
    return AlertRuleResponse.model_validate(updated_rule)


@router.delete("/rules/{rule_id}", summary="停用预警规则", status_code=status.HTTP_200_OK)
async def delete_alert_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> MessageResponse:
    """
    停用指定预警规则

    将规则标记为未启用状态。
    """
    rule = await alert_rule_crud.get(db, id=rule_id)
    if not rule:
        raise NotFoundException(detail=f"预警规则 (ID: {rule_id}) 不存在")

    await alert_rule_crud.update(db, id=rule_id, obj_in={"is_active": False})

    logger.info(f"预警规则已停用: {rule.name} (ID: {rule_id})")
    return MessageResponse(message=f"预警规则 '{rule.name}' 已成功停用")


# ==================== 预警事件路由 ====================

@router.get(
    "/events",
    response_model=PaginatedResponse[AlertEventResponse],
    summary="获取预警事件列表",
)
async def get_alert_events(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    severity: str | None = Query(default=None, description="严重级别筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
    hours: int | None = Query(default=None, ge=1, le=720, description="最近多少小时"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[AlertEventResponse]:
    """
    获取预警事件列表

    支持按严重级别、状态和时间范围筛选，支持分页。
    """
    skip = (page - 1) * page_size

    if hours is not None:
        items, total = await alert_event_crud.get_recent(
            db,
            hours=hours,
            severity=severity,
            status=status,
            skip=skip,
            limit=page_size,
        )
    else:
        # 不限制时间范围
        stmt = select(AlertEvent)
        count_stmt = select(func.count()).select_from(AlertEvent)

        if severity is not None:
            stmt = stmt.where(AlertEvent.severity == severity)
            count_stmt = count_stmt.where(AlertEvent.severity == severity)
        if status is not None:
            stmt = stmt.where(AlertEvent.status == status)
            count_stmt = count_stmt.where(AlertEvent.status == status)

        total_result = await db.execute(count_stmt)
        total = total_result.scalar() or 0

        from sqlalchemy import desc
        stmt = stmt.order_by(desc(AlertEvent.created_at)).offset(skip).limit(page_size)
        result = await db.execute(stmt)
        items = result.scalars().all()

    return PaginatedResponse.create(
        items=[AlertEventResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/events/{event_id}/acknowledge",
    response_model=AlertEventResponse,
    summary="确认预警事件",
)
async def acknowledge_event(
    event_id: int,
    ack_in: AlertEventAcknowledge | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AlertEventResponse:
    """
    确认指定的预警事件

    将事件状态从 pending 变更为 acknowledged。
    """
    event = await alert_event_crud.get(db, id=event_id)
    if not event:
        raise NotFoundException(detail=f"预警事件 (ID: {event_id}) 不存在")

    if event.status != "pending":
        from app.core.exceptions import BadRequestException
        raise BadRequestException(
            detail=f"预警事件当前状态为 '{event.status}'，只有 'pending' 状态的事件可以确认",
        )

    updated_event = await alert_event_crud.update(
        db,
        id=event_id,
        obj_in={
            "status": "acknowledged",
            "acknowledged_by": current_user.id,
            "acknowledged_at": datetime.now(timezone.utc),
        },
    )
    if not updated_event:
        raise NotFoundException(detail=f"预警事件 (ID: {event_id}) 不存在")

    logger.info(f"预警事件已确认: (ID: {event_id}) by 用户 (ID: {current_user.id})")
    return AlertEventResponse.model_validate(updated_event)


@router.put(
    "/events/{event_id}/resolve",
    response_model=AlertEventResponse,
    summary="解决预警事件",
)
async def resolve_event(
    event_id: int,
    resolve_in: AlertEventAcknowledge | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> AlertEventResponse:
    """
    解决指定的预警事件

    将事件状态变更为 resolved，并记录解决备注。
    """
    event = await alert_event_crud.get(db, id=event_id)
    if not event:
        raise NotFoundException(detail=f"预警事件 (ID: {event_id}) 不存在")

    update_data = {
        "status": "resolved",
        "resolved_by": current_user.id,
        "resolved_at": datetime.now(timezone.utc),
    }
    if resolve_in and resolve_in.note:
        update_data["resolved_note"] = resolve_in.note

    updated_event = await alert_event_crud.update(db, id=event_id, obj_in=update_data)
    if not updated_event:
        raise NotFoundException(detail=f"预警事件 (ID: {event_id}) 不存在")

    logger.info(f"预警事件已解决: (ID: {event_id}) by 用户 (ID: {current_user.id})")
    return AlertEventResponse.model_validate(updated_event)
