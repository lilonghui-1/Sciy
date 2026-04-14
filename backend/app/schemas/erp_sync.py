# -*- coding: utf-8 -*-
"""
ERP 同步数据模式

定义 ERP 同步相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class ErpSyncLogResponse(BaseModel):
    """ERP 同步日志响应"""

    id: int
    sync_type: str
    direction: str
    entity_type: Optional[str] = None
    status: str
    records_processed: int
    records_failed: int
    error_message: Optional[str] = None
    request_params: Optional[dict] = None
    response_summary: Optional[dict] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ErpConfigResponse(BaseModel):
    """ERP 配置响应"""

    id: int
    config_key: str
    config_value: str
    description: Optional[str] = None
    is_encrypted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ErpConfigUpdate(BaseModel):
    """ERP 配置更新"""

    config_value: str = Field(..., description="配置值")
    description: Optional[str] = None
    is_encrypted: Optional[bool] = None
