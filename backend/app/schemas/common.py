# -*- coding: utf-8 -*-
"""
通用数据模式

定义分页、通用响应等公共模式。
"""

from typing import Any, Generic, TypeVar, Optional

from pydantic import BaseModel, Field


T = TypeVar("T")


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""

    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")
    pages: int = Field(default=0, description="总页数")

    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "PaginatedResponse[T]":
        """创建分页响应"""
        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class MessageResponse(BaseModel):
    """通用消息响应"""

    message: str = Field(description="消息内容")
    success: bool = Field(default=True, description="是否成功")


class ErrorResponse(BaseModel):
    """错误响应"""

    success: bool = Field(default=False)
    error_code: str = Field(description="错误码")
    message: str = Field(description="错误信息")
    details: Optional[Any] = Field(default=None, description="错误详情")
