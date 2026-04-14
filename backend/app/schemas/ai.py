# -*- coding: utf-8 -*-
"""
AI 对话相关数据模式

包含聊天请求、消息、响应等模式定义。
"""

from typing import Any

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """聊天消息"""

    role: str = Field(..., description="角色（user / assistant / system）")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str = Field(..., min_length=1, description="用户消息")
    history: list[dict[str, str]] = Field(
        default_factory=list, description="对话历史"
    )


class ChatResponse(BaseModel):
    """聊天响应"""

    message: str = Field(..., description="AI 回复消息")
    sources: list[dict[str, Any]] | None = Field(
        default=None, description="引用来源列表"
    )
