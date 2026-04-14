# -*- coding: utf-8 -*-
"""
用户数据模式

定义用户相关的请求/响应模式。
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """创建用户请求"""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., max_length=255, description="邮箱")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    full_name: str = Field(default="", max_length=100, description="姓名")
    phone: Optional[str] = Field(default=None, max_length=20, description="手机号")
    role: str = Field(default="viewer", description="角色: admin/manager/viewer")


class UserUpdate(BaseModel):
    """更新用户请求"""

    full_name: Optional[str] = Field(default=None, max_length=100, description="姓名")
    phone: Optional[str] = Field(default=None, max_length=20, description="手机号")
    email: Optional[str] = Field(default=None, max_length=255, description="邮箱")
    role: Optional[str] = Field(default=None, description="角色")
    is_active: Optional[bool] = Field(default=None, description="是否激活")


class UserResponse(BaseModel):
    """用户响应"""

    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """用户列表响应"""

    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    """登录请求"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    """登录响应"""

    access_token: str = Field(description="访问令牌")
    refresh_token: str = Field(description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(description="访问令牌过期时间(秒)")
    user: UserResponse = Field(description="用户信息")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求"""

    refresh_token: str = Field(..., description="刷新令牌")
