# -*- coding: utf-8 -*-
"""
ERP 同步路由

处理与外部 ERP 系统的数据同步操作。
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user, get_current_admin_user
from app.core.exceptions import NotFoundException
from app.crud.base import BaseCRUD
from app.models.user import User
from app.models.erp_sync_log import ErpSyncLog
from app.models.erp_sync import ErpConfig
from app.schemas.common import PaginatedResponse, MessageResponse
from app.schemas.erp_sync import (
    ErpConfigResponse,
    ErpConfigUpdate,
    ErpSyncLogResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/erp-sync", tags=["ERP 同步"])

erp_sync_log_crud = BaseCRUD(ErpSyncLog)
erp_config_crud = BaseCRUD(ErpConfig)


@router.post("/trigger", response_model=MessageResponse, summary="手动触发同步")
async def trigger_sync(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> MessageResponse:
    """
    手动触发 ERP 数据同步

    仅管理员可操作。创建同步任务记录并启动同步流程。

    注意：当前为占位实现，后续阶段将接入真实的 ERP 同步逻辑。
    """
    # 创建同步日志记录
    sync_log = await erp_sync_log_crud.create(db, obj_in={
        "sync_type": "manual",
        "status": "pending",
        "triggered_by": current_user.id,
        "started_at": datetime.now(timezone.utc),
    })

    # 占位实现：直接标记为成功
    await erp_sync_log_crud.update(db, id=sync_log.id, obj_in={
        "status": "success",
        "total_records": 0,
        "success_count": 0,
        "error_count": 0,
        "finished_at": datetime.now(timezone.utc),
    })

    logger.info(f"ERP 同步已触发: 同步日志ID={sync_log.id}, 触发人ID={current_user.id}")

    return MessageResponse(message="ERP 同步已触发，同步任务正在后台执行")


@router.get(
    "/logs",
    response_model=PaginatedResponse[ErpSyncLogResponse],
    summary="获取同步日志列表",
)
async def get_sync_logs(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    sync_type: str | None = Query(default=None, description="同步类型筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> PaginatedResponse[ErpSyncLogResponse]:
    """
    获取 ERP 同步日志列表

    支持按同步类型和状态筛选，支持分页。
    """
    skip = (page - 1) * page_size

    stmt = select(ErpSyncLog)
    count_stmt = select(func.count()).select_from(ErpSyncLog)

    if sync_type is not None:
        stmt = stmt.where(ErpSyncLog.sync_type == sync_type)
        count_stmt = count_stmt.where(ErpSyncLog.sync_type == sync_type)
    if status is not None:
        stmt = stmt.where(ErpSyncLog.status == status)
        count_stmt = count_stmt.where(ErpSyncLog.status == status)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(desc(ErpSyncLog.created_at)).offset(skip).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return PaginatedResponse.create(
        items=[ErpSyncLogResponse.model_validate(log) for log in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/config", response_model=list[ErpConfigResponse], summary="获取 ERP 配置")
async def get_erp_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> list[ErpConfigResponse]:
    """
    获取 ERP 同步配置

    仅管理员可查看。返回所有 ERP 配置项。
    """
    configs = await erp_config_crud.get_multi(db, limit=1000)
    return [ErpConfigResponse.model_validate(c) for c in configs]


@router.put("/config", response_model=MessageResponse, summary="更新 ERP 配置")
async def update_erp_config(
    config_in: ErpConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> MessageResponse:
    """
    更新 ERP 同步配置

    仅管理员可操作。批量更新配置键值对。
    """
    updated_count = 0
    for key, value in config_in.configs.items():
        existing = await erp_config_crud.get_by_field(db, field_name="config_key", value=key)
        if existing:
            await erp_config_crud.update(db, id=existing.id, obj_in={"config_value": value})
        else:
            await erp_config_crud.create(db, obj_in={
                "config_key": key,
                "config_value": value,
                "description": f"配置项: {key}",
            })
        updated_count += 1

    logger.info(f"ERP 配置已更新: {updated_count} 项, 操作人ID={current_user.id}")
    return MessageResponse(message=f"已更新 {updated_count} 个配置项")
