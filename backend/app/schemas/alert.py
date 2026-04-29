# -*- coding: utf-8 -*-
"""
预警数据模式

定义预警相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class AlertRuleCreate(BaseModel):
    """创建预警规则请求"""

    name: str = Field(..., min_length=1, max_length=100, description="规则名称")
    description: Optional[str] = Field(default=None, description="规则描述")
    rule_type: str = Field(..., description="规则类型: stockout/overstock/delay/turnover/custom")
    conditions: dict = Field(..., description="触发条件(JSON)")
    priority: str = Field(default="medium", description="优先级: low/medium/high/critical")
    notify_channels: dict = Field(default_factory=lambda: ["in_app"], description="通知渠道(JSON数组)")
    notify_recipients: Optional[dict] = Field(default=None, description="通知接收人ID列表(JSON数组)")
    cooldown_seconds: int = Field(default=3600, ge=1, description="冷却时间(秒)")
    product_type: Optional[str] = Field(default=None, description="适用产品类型: raw_material/finished_good")
    category_scope: Optional[str] = Field(default=None, description="适用品类(逗号分隔)")
    aging_tier_scope: Optional[str] = Field(default=None, description="适用库龄分层: normal/attention/slow_moving")
    product_type: Optional[str] = None
    category_scope: Optional[str] = None
    aging_tier_scope: Optional[str] = None
    creator_id: int = Field(..., description="创建人ID")


class AlertRuleUpdate(BaseModel):
    """更新预警规则请求"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100, description="规则名称")
    description: Optional[str] = Field(default=None, description="规则描述")
    rule_type: Optional[str] = Field(default=None, description="规则类型")
    conditions: Optional[dict] = Field(default=None, description="触发条件(JSON)")
    priority: Optional[str] = Field(default=None, description="优先级: low/medium/high/critical")
    notify_channels: Optional[dict] = Field(default=None, description="通知渠道(JSON数组)")
    notify_recipients: Optional[dict] = Field(default=None, description="通知接收人ID列表(JSON数组)")
    cooldown_seconds: Optional[int] = Field(default=None, ge=1, description="冷却时间(秒)")
    product_type: Optional[str] = Field(default=None, description="适用产品类型")
    category_scope: Optional[str] = Field(default=None, description="适用品类")
    aging_tier_scope: Optional[str] = Field(default=None, description="适用库龄分层")
    is_active: Optional[bool] = Field(default=None, description="是否启用")


class AlertRuleResponse(BaseModel):
    """预警规则响应"""

    id: int
    name: str
    description: Optional[str] = None
    rule_type: str
    conditions: dict
    priority: str
    notify_channels: dict
    notify_recipients: Optional[dict] = None
    cooldown_seconds: int
    is_active: bool
    creator_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertEventResponse(BaseModel):
    """预警事件响应"""

    id: int
    rule_id: int
    rule_name: str
    product_id: int
    warehouse_id: Optional[int] = None
    severity: str
    title: str
    message: str
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    context_data: Optional[dict] = None
    status: str
    acknowledged_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AlertEventAcknowledge(BaseModel):
    """确认/解决预警事件请求"""

    note: Optional[str] = Field(default=None, description="备注")
