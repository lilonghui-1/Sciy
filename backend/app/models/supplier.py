# -*- coding: utf-8 -*-
"""
供应商模型

定义供应商的数据结构。
"""

from sqlalchemy import String, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Supplier(Base, TimestampMixin):
    """供应商模型"""

    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="供应商名称",
    )
    code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, comment="供应商编码",
    )
    contact_person: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="联系人",
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="联系电话",
    )
    email: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="邮箱",
    )
    address: Mapped[str | None] = mapped_column(
        String(300), nullable=True, comment="地址",
    )
    website: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="网站",
    )
    bank_name: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="开户银行",
    )
    bank_account: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="银行账号",
    )
    tax_number: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="税号",
    )
    rating: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="评分(1-5)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用",
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="备注",
    )
