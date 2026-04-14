# -*- coding: utf-8 -*-
"""
ERP 配置模型

定义 ERP 系统连接配置的数据结构。
"""

from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ErpConfig(Base, TimestampMixin):
    """ERP 配置模型"""

    __tablename__ = "erp_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="配置键",
    )
    config_value: Mapped[str] = mapped_column(
        Text, nullable=False, comment="配置值",
    )
    description: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="配置描述",
    )
    is_encrypted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否加密",
    )
