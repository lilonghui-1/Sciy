# -*- coding: utf-8 -*-
"""
仓库数据模式

定义仓库相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class WarehouseCreate(BaseModel):
    """创建仓库请求"""

    name: str = Field(..., min_length=1, max_length=100, description="仓库名称")
    code: str = Field(..., min_length=1, max_length=20, description="仓库编码")
    address: Optional[str] = Field(default=None, max_length=300, description="仓库地址")
    city: Optional[str] = Field(default=None, max_length=50, description="所在城市")
    province: Optional[str] = Field(default=None, max_length=50, description="所在省份")
    country: str = Field(default="中国", max_length=50, description="所在国家")
    latitude: Optional[float] = Field(default=None, description="纬度")
    longitude: Optional[float] = Field(default=None, description="经度")
    capacity: int = Field(default=0, ge=0, description="仓库容量")
    manager_name: Optional[str] = Field(default=None, max_length=50, description="负责人姓名")
    manager_phone: Optional[str] = Field(default=None, max_length=20, description="负责人电话")
    description: Optional[str] = Field(default=None, description="仓库描述")


class WarehouseUpdate(BaseModel):
    """更新仓库请求"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100, description="仓库名称")
    address: Optional[str] = Field(default=None, max_length=300, description="仓库地址")
    city: Optional[str] = Field(default=None, max_length=50, description="所在城市")
    province: Optional[str] = Field(default=None, max_length=50, description="所在省份")
    country: Optional[str] = Field(default=None, max_length=50, description="所在国家")
    latitude: Optional[float] = Field(default=None, description="纬度")
    longitude: Optional[float] = Field(default=None, description="经度")
    capacity: Optional[int] = Field(default=None, ge=0, description="仓库容量")
    manager_name: Optional[str] = Field(default=None, max_length=50, description="负责人姓名")
    manager_phone: Optional[str] = Field(default=None, max_length=20, description="负责人电话")
    is_active: Optional[bool] = Field(default=None, description="是否启用")
    description: Optional[str] = Field(default=None, description="仓库描述")


class WarehouseResponse(BaseModel):
    """仓库响应"""

    id: int
    name: str
    code: str
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    capacity: int
    manager_name: Optional[str] = None
    manager_phone: Optional[str] = None
    is_active: bool
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WarehouseListResponse(BaseModel):
    """仓库列表响应"""

    id: int
    name: str
    code: str
    city: Optional[str] = None
    capacity: int
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
