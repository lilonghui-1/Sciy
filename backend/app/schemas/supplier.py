# -*- coding: utf-8 -*-
"""
供应商数据模式

定义供应商相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    """创建供应商请求"""

    name: str = Field(..., min_length=1, max_length=200, description="供应商名称")
    code: str = Field(..., min_length=1, max_length=20, description="供应商编码")
    contact_person: Optional[str] = Field(default=None, max_length=50, description="联系人")
    phone: Optional[str] = Field(default=None, max_length=20, description="联系电话")
    email: Optional[str] = Field(default=None, max_length=255, description="邮箱")
    address: Optional[str] = Field(default=None, max_length=300, description="地址")
    website: Optional[str] = Field(default=None, max_length=500, description="网站")
    bank_name: Optional[str] = Field(default=None, max_length=100, description="开户银行")
    bank_account: Optional[str] = Field(default=None, max_length=50, description="银行账号")
    tax_number: Optional[str] = Field(default=None, max_length=50, description="税号")
    rating: int = Field(default=0, ge=0, le=5, description="评分(1-5)")
    notes: Optional[str] = Field(default=None, description="备注")


class SupplierUpdate(BaseModel):
    """更新供应商请求"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200, description="供应商名称")
    contact_person: Optional[str] = Field(default=None, max_length=50, description="联系人")
    phone: Optional[str] = Field(default=None, max_length=20, description="联系电话")
    email: Optional[str] = Field(default=None, max_length=255, description="邮箱")
    address: Optional[str] = Field(default=None, max_length=300, description="地址")
    website: Optional[str] = Field(default=None, max_length=500, description="网站")
    bank_name: Optional[str] = Field(default=None, max_length=100, description="开户银行")
    bank_account: Optional[str] = Field(default=None, max_length=50, description="银行账号")
    tax_number: Optional[str] = Field(default=None, max_length=50, description="税号")
    rating: Optional[int] = Field(default=None, ge=0, le=5, description="评分(1-5)")
    is_active: Optional[bool] = Field(default=None, description="是否启用")
    notes: Optional[str] = Field(default=None, description="备注")


class SupplierResponse(BaseModel):
    """供应商响应"""

    id: int
    name: str
    code: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    tax_number: Optional[str] = None
    rating: int
    is_active: bool
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    """供应商列表响应"""

    id: int
    name: str
    code: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    rating: int
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
