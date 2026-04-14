# -*- coding: utf-8 -*-
"""
数据导入导出模式

定义导入导出相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class ImportTemplateInfo(BaseModel):
    """导入模板信息"""

    data_type: str = Field(..., description="数据类型")
    template_name: str = Field(..., description="模板名称")
    description: str = Field(..., description="模板描述")
    required_columns: list[str] = Field(..., description="必填列")
    optional_columns: list[str] = Field(default_factory=list, description="可选列")
    download_url: Optional[str] = Field(default=None, description="模板下载URL")


class ImportExportJobResponse(BaseModel):
    """导入导出任务响应"""

    id: int
    job_type: str
    data_type: str
    file_name: str
    file_size: int
    status: str
    total_rows: int
    processed_rows: int
    success_rows: int
    error_rows: int
    error_message: Optional[str] = None
    triggered_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
