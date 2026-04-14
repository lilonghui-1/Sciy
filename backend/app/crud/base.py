from __future__ import annotations

import logging
from typing import Type, TypeVar, Optional, Sequence, Any, Generic

from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseCRUD(Generic[ModelType]):
    """
    通用 CRUD 基础类

    提供标准的创建、读取、更新、删除操作。
    所有具体的 CRUD 类都应继承此类并指定模型类型。
    """

    def __init__(self, model: Type[ModelType]) -> None:
        self.model = model
