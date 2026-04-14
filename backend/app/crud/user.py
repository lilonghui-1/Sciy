from __future__ import annotations

# -*- coding: utf-8 -*-
"""
用户 CRUD 操作

提供用户相关的数据库操作，包括认证功能。
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.core.security import verify_password
from app.models.user import User

logger = logging.getLogger(__name__)


class UserCRUD(BaseCRUD[User]):
    """用户 CRUD 操作类"""

    def __init__(self) -> None:
        super().__init__(User)

    async def get_by_username(self, db: AsyncSession, *, username: str) -> User | None:
        """
        根据用户名获取用户

        Args:
            db: 数据库会话
            username: 用户名

        Returns:
            用户实例，未找到返回 None
        """
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, *, email: str) -> User | None:
        """
        根据电子邮箱获取用户

        Args:
            db: 数据库会话
            email: 电子邮箱地址

        Returns:
            用户实例，未找到返回 None
        """
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def authenticate(
        self,
        db: AsyncSession,
        *,
        username: str,
        password: str,
    ) -> User | None:
        """
        验证用户凭据并返回用户

        根据用户名查找用户，然后验证密码是否匹配。
        如果用户不存在、未启用或密码错误，返回 None。

        Args:
            db: 数据库会话
            username: 用户名
            password: 明文密码

        Returns:
            认证成功的用户实例，失败返回 None
        """
        user = await self.get_by_username(db, username=username)
        if user is None:
            return None
        if not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


# 创建全局用户 CRUD 实例
user_crud = UserCRUD()
