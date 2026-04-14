# -*- coding: utf-8 -*-
"""
仓库模型

定义仓库的数据结构，包含地理位置、容量等信息。
"""

from sqlalchemy import String, Boolean, Text, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Warehouse(Base, TimestampMixin):
    """仓库模型"""

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="仓库名称",
    )
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="仓库编码",
    )
    address: Mapped[str | None] = mapped_column(
        String(300), nullable=True, comment="仓库地址",
    )
    city: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="所在城市",
    )
    province: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="所在省份",
    )
    country: Mapped[str] = mapped_column(
        String(50), nullable=False, default="中国", comment="所在国家",
    )
    latitude: Mapped[float | None] = mapped_column(
        Numeric(10, 7), nullable=True, comment="纬度",
    )
    longitude: Mapped[float | None] = mapped_column(
        Numeric(10, 7), nullable=True, comment="经度",
    )
    capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="仓库容量",
    )
    manager_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="负责人姓名",
    )
    manager_phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="负责人电话",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="仓库描述",
    )
