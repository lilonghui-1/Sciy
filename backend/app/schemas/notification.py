# -*- coding: utf-8 -*-
"""
通知数据模式

定义通知相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationPreferenceResponse(BaseModel):
    """通知偏好响应"""

    id: int
    user_id: int
    notify_email: bool
    notify_sms: bool
    notify_in_app: bool
    notify_webhook: bool
    low_stock_alert: bool
    over_stock_alert: bool
    forecast_alert: bool
    daily_summary: bool

    model_config = {"from_attributes": True}


class NotificationPreferenceUpdate(BaseModel):
    """更新通知偏好请求"""

    notify_email: Optional[bool] = Field(default=None, description="邮件通知")
    notify_sms: Optional[bool] = Field(default=None, description="短信通知")
    notify_in_app: Optional[bool] = Field(default=None, description="站内通知")
    notify_webhook: Optional[bool] = Field(default=None, description="Webhook通知")
    low_stock_alert: Optional[bool] = Field(default=None, description="低库存预警")
    over_stock_alert: Optional[bool] = Field(default=None, description="超库存预警")
    forecast_alert: Optional[bool] = Field(default=None, description="预测预警")
    daily_summary: Optional[bool] = Field(default=None, description="每日汇总")


class NotificationLogResponse(BaseModel):
    """通知日志响应"""

    id: int
    alert_event_id: Optional[int] = None
    channel: str
    recipient: str
    subject: Optional[str] = None
    body: str
    status: str
    error_message: Optional[str] = None
    retry_count: int
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
