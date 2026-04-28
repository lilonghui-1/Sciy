# ============================================================
# Alembic 异步迁移环境配置
# 支持异步 SQLAlchemy 引擎，自动导入所有模型用于 autogenerate
# 数据库：人大金仓 KingbaseES（兼容 PostgreSQL 协议）
# ============================================================

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 将项目根目录添加到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入所有模型，确保 Alembic 能够检测到表结构变化
# 必须在 Base 和 metadata 定义之后导入
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# 导入所有模型模块（确保所有表都被注册到 Base.metadata）
import app.models  # noqa: E402, F401

# Alembic Config 对象
config = context.config

# 设置数据库 URL（从环境变量读取同步连接 URL）
# Alembic 迁移需要使用同步驱动
settings = get_settings()
config.set_main_option(
    "sqlalchemy.url",
    settings.database_sync_url,
)

# 解析日志配置（如果配置文件中指定了日志）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据，用于 autogenerate 生成迁移脚本
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    以 'offline' 模式运行迁移。
    仅需要 URL，不需要 Engine。调用 context.execute() 将
    迁移命令直接发送到数据库，而不需要创建 Engine。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # 比较类型时忽略默认值和服务器默认值
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    在给定连接上执行迁移。
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    以异步模式运行迁移。
    创建异步引擎并执行迁移。
    """
    # 异步引擎配置
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    以 'online' 模式运行迁移。
    创建 Engine 并关联 connection 到 context。
    """
    asyncio.run(run_async_migrations())


if __name__ == "__main__":
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
