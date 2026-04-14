"""
SQLAlchemy 声明式基类

定义所有 ORM 模型的公共基类，包含统一的命名约定和元数据配置。
所有数据模型都应继承自 Base 类。
"""

from datetime import datetime

from sqlalchemy import MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm.properties import MappedColumn


# ==================== 命名约定 ====================
# 统一数据库表名、列名、约束名等的命名规范
# 使用 snake_case 风格，确保数据库命名的一致性
convention = {
    "ix": "ix_%(column_0_label)s",          # 索引命名: ix_字段名
    "uq": "uq_%(table_name)s_%(column_0_name)s",  # 唯一约束: uq_表名_字段名
    "ck": "ck_%(table_name)s_%(constraint_name)s", # 检查约束: ck_表名_约束名
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",  # 外键
    "pk": "pk_%(table_name)s",               # 主键: pk_表名
}


class Base(DeclarativeBase):
    """
    所有 ORM 模型的声明式基类

    特性：
    - 使用 snake_case 命名约定自动生成约束名
    - 所有模型默认包含 id, created_at, updated_at 字段（通过 Mixin）
    - 支持 SQLAlchemy 2.0 的 Mapped 类型注解语法
    """
    metadata = MetaData(naming_convention=convention)


class TimestampMixin:
    """
    时间戳混入类

    为模型提供自动管理的创建时间和更新时间字段。
    使用 server_default 确保数据库层面也有默认值。
    """
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=datetime.utcnow,
        nullable=False,
        comment="更新时间",
    )
