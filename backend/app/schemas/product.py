# -*- coding: utf-8 -*-
"""
产品数据模式

定义产品相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    """创建产品请求"""

    name: str = Field(..., min_length=1, max_length=200, description="产品名称")
    sku: str = Field(..., min_length=1, max_length=50, description="SKU编码")
    barcode: Optional[str] = Field(default=None, max_length=50, description="条形码")
    category: Optional[str] = Field(default=None, max_length=100, description="产品分类")
    erp_code: Optional[str] = Field(default=None, max_length=50, description="ERP系统编码")
    unit: str = Field(default="个", max_length=20, description="计量单位")
    unit_cost: Decimal = Field(default=Decimal("0.00"), ge=0, description="单位成本")
    selling_price: Decimal = Field(default=Decimal("0.00"), ge=0, description="销售单价")
    supplier_id: int = Field(..., description="供应商ID")
    lead_time_days: int = Field(default=7, ge=0, description="补货提前期(天)")
    safety_stock_days: int = Field(default=14, ge=0, description="安全库存天数")


class ProductUpdate(BaseModel):
    """更新产品请求"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200, description="产品名称")
    barcode: Optional[str] = Field(default=None, max_length=50, description="条形码")
    category: Optional[str] = Field(default=None, max_length=100, description="产品分类")
    erp_code: Optional[str] = Field(default=None, max_length=50, description="ERP系统编码")
    unit: Optional[str] = Field(default=None, max_length=20, description="计量单位")
    unit_cost: Optional[Decimal] = Field(default=None, ge=0, description="单位成本")
    selling_price: Optional[Decimal] = Field(default=None, ge=0, description="销售单价")
    supplier_id: Optional[int] = Field(default=None, description="供应商ID")
    lead_time_days: Optional[int] = Field(default=None, ge=0, description="补货提前期(天)")
    safety_stock_days: Optional[int] = Field(default=None, ge=0, description="安全库存天数")
    is_active: Optional[bool] = Field(default=None, description="是否启用")


class ProductResponse(BaseModel):
    """产品响应"""

    id: int
    name: str
    sku: str
    barcode: Optional[str] = None
    category: Optional[str] = None
    erp_code: Optional[str] = None
    unit: str
    unit_cost: Decimal
    selling_price: Decimal
    supplier_id: int
    lead_time_days: int
    safety_stock_days: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    """产品列表响应"""

    id: int
    name: str
    sku: str
    category: Optional[str] = None
    unit: str
    unit_cost: Decimal
    selling_price: Decimal
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
