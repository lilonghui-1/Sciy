from __future__ import annotations

# -*- coding: utf-8 -*-
"""
用户模型

管理系统用户信息，包括认证、角色权限等。
"""

from datetime import datetime

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(TimestampMixin, Base):
    """
    用户模型

    存储系统用户的基本信息和认证数据。
    支持三种角色：admin（管理员）、manager（经理）、viewer（查看者）。
    """

    __tablename__ = "users"

    # ==================== 主键 ====================
    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="用户ID",
    )

    # ==================== 认证信息 ====================
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="用户名",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="电子邮箱",
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="哈希密码",
    )

    # ==================== 个人信息 ====================
    full_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="全名",
    )
    phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="联系电话",
    )

    # ==================== 角色与状态 ====================
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="viewer",
        comment="角色: admin/manager/viewer",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
    )

    # ==================== 关系 ====================
    alert_rules: Mapped[list["AlertRule"]] = relationship(  # noqa: F821
        "AlertRule",
        back_populates="creator",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
