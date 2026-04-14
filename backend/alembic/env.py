# ============================================================
# Alembic 异步迁移环境配置
# 支持异步 SQLAlchemy 引擎，自动导入所有模型用于 autogenerate
# 迁移完成后自动创建 TimescaleDB 超级表 (hypertable)
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
from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402

# 导入所有模型模块（确保所有表都被注册到 Base.metadata）
from app.models import (  # noqa: E402
    product,
    inventory,
    inventory_snapshot,
    supplier,
    purchase_order,
    sales_order,
    warehouse,
    user,
    alert,
    category,
)

# Alembic Config 对象
config = context.config

# 设置数据库 URL（从环境变量读取同步连接 URL）
# Alembic 迁移需要使用同步驱动
config.set_main_option(
    "sqlalchemy.url",
    settings.DATABASE_SYNC_URL,
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


async def create_hypertables() -> None:
    """
    迁移完成后，为 TimescaleDB 创建超级表 (hypertable)。
    inventory_snapshots 表需要转换为 hypertable 以支持时序数据查询。
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # 检查 inventory_snapshots 表是否存在
        result = await connection.execute(
            # 使用文本 SQL 检查表是否存在
            __import__("sqlalchemy").text(
                "SELECT EXISTS ("
                "  SELECT FROM information_schema.tables "
                "  WHERE table_name = 'inventory_snapshots'"
                ")"
            )
        )
        table_exists = result.scalar()

        if table_exists:
            # 检查是否已经是 hypertable
            result = await connection.execute(
                __import__("sqlalchemy").text(
                    "SELECT EXISTS ("
                    "  SELECT FROM timescaledb_information.hypertables "
                    "  WHERE table_name = 'inventory_snapshots'"
                    ")"
                )
            )
            is_hypertable = result.scalar()

            if not is_hypertable:
                # 将 inventory_snapshots 表转换为 hypertable
                # 使用 created_at 作为时间分区列
                await connection.execute(
                    __import__("sqlalchemy").text(
                        "SELECT create_hypertable("
                        "  'inventory_snapshots', "
                        "  'created_at', "
                        "  chunk_time_interval => INTERVAL '1 day', "
                        "  if_not_exists => TRUE"
                        ")"
                    )
                )
                print("已成功将 inventory_snapshots 表转换为 TimescaleDB hypertable")

                # 添加数据保留策略（可选）：保留最近 365 天的数据
                await connection.execute(
                    __import__("sqlalchemy").text(
                        "SELECT add_retention_policy("
                        "  'inventory_snapshots', "
                        "  INTERVAL '365 days', "
                        "  if_not_exists => TRUE"
                        ")"
                    )
                )
                print("已设置 inventory_snapshots 数据保留策略：365 天")

                # 启用数据压缩（7天后自动压缩）
                await connection.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE inventory_snapshots SET ("
                        "  timescaledb.compress, "
                        "  timescaledb.compress_segmentby = 'product_id,warehouse_id'"
                        ")"
                    )
                )
                await connection.execute(
                    __import__("sqlalchemy").text(
                        "SELECT add_compression_policy("
                        "  'inventory_snapshots', "
                        "  INTERVAL '7 days', "
                        "  if_not_exists => TRUE"
                        ")"
                    )
                )
                print("已启用 inventory_snapshots 数据压缩策略：7天后压缩")
            else:
                print("inventory_snapshots 表已经是 hypertable，跳过创建")

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    以 'online' 模式运行迁移。
    创建 Engine 并关联 connection 到 context。
    """
    asyncio.run(run_async_migrations())

    # 迁移完成后创建 hypertable
    asyncio.run(create_hypertables())


if __name__ == "__main__":
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
