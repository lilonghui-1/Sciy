"""
TimescaleDB 初始化模块

提供 TimescaleDB 扩展安装和超表创建功能。
TimescaleDB 是基于 PostgreSQL 的时序数据库扩展，
适用于库存变动记录、传感器数据等时序场景。
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import async_session_factory

logger = logging.getLogger(__name__)


async def ensure_timescaledb_extension(session: AsyncSession) -> None:
    """
    确保 TimescaleDB 扩展已安装

    在数据库中创建 timescaledb 扩展（如果尚未安装）。
    需要超级用户权限才能安装扩展。

    Args:
        session: 异步数据库会话

    Raises:
        Exception: 扩展安装失败时抛出异常
    """
    try:
        # 检查扩展是否已存在
        check_query = text(
            "SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"
        )
        result = await session.execute(check_query)
        exists = result.scalar()

        if exists:
            logger.info("TimescaleDB 扩展已存在，跳过安装")
            return

        # 安装 TimescaleDB 扩展
        create_query = text("CREATE EXTENSION IF NOT EXISTS timescaledb")
        await session.execute(create_query)
        await session.commit()
        logger.info("TimescaleDB 扩展安装成功")

    except Exception as e:
        await session.rollback()
        logger.error(f"TimescaleDB 扩展安装失败: {e}")
        raise


async def create_hypertable(
    session: AsyncSession,
    table_name: str,
    time_column: str = "created_at",
    chunk_time_interval: str = "1 day",
    if_not_exists: bool = True,
) -> None:
    """
    将普通表转换为 TimescaleDB 超表

    超表是 TimescaleDB 的核心概念，自动按时间分区，
    提供高效的时序数据查询和压缩能力。

    Args:
        session: 异步数据库会话
        table_name: 要转换的表名
        time_column: 时间分区列名，默认为 created_at
        chunk_time_interval: 分区时间间隔，默认为 1 天
        if_not_exists: 如果超表已存在是否跳过，默认为 True

    Raises:
        Exception: 超表创建失败时抛出异常

    Example:
        await create_hypertable(session, "inventory_transactions", "created_at", "1 week")
    """
    try:
        # 构建超表创建 SQL
        exists_clause = "IF NOT EXISTS" if if_not_exists else ""
        create_hypertable_query = text(
            f"SELECT create_hypertable('{exists_clause}' {table_name}', "
            f"'{time_column}', chunk_time_interval => INTERVAL '{chunk_time_interval}')"
        )

        await session.execute(create_hypertable_query)
        await session.commit()
        logger.info(
            f"超表创建成功: {table_name}，时间列: {time_column}，"
            f"分区间隔: {chunk_time_interval}"
        )

    except Exception as e:
        await session.rollback()
        # 如果超表已存在，忽略错误
        error_msg = str(e).lower()
        if "already a hypertable" in error_msg or "already exists" in error_msg:
            logger.info(f"超表 {table_name} 已存在，跳过创建")
            return
        logger.error(f"超表创建失败 ({table_name}): {e}")
        raise


async def enable_compression(
    session: AsyncSession,
    table_name: str,
    compress_after: str = "7 days",
    compress_segmentby: str = "",
) -> None:
    """
    为超表启用压缩策略

    TimescaleDB 压缩可以显著减少历史数据的存储空间。

    Args:
        session: 异步数据库会话
        table_name: 超表名称
        compress_after: 数据压缩的延迟时间，默认 7 天后压缩
        compress_segmentby: 压缩分段列（逗号分隔），优化查询性能

    Example:
        await enable_compression(
            session,
            "inventory_transactions",
            compress_after="30 days",
            compress_segmentby="product_id,warehouse_id"
        )
    """
    try:
        # 添加压缩设置
        if compress_segmentby:
            alter_query = text(
                f"ALTER TABLE {table_name} SET ("
                f"timescaledb.compress, "
                f"timescaledb.compress_segmentby = '{compress_segmentby}')"
            )
        else:
            alter_query = text(
                f"ALTER TABLE {table_name} SET (timescaledb.compress)"
            )

        await session.execute(alter_query)

        # 添加自动压缩策略
        policy_query = text(
            f"SELECT add_compression_policy('{table_name}', "
            f"INTERVAL '{compress_after}')"
        )
        await session.execute(policy_query)

        await session.commit()
        logger.info(
            f"压缩策略已启用: {table_name}，压缩延迟: {compress_after}"
        )

    except Exception as e:
        await session.rollback()
        logger.error(f"启用压缩策略失败 ({table_name}): {e}")
        raise


async def add_retention_policy(
    session: AsyncSession,
    table_name: str,
    retention_period: str = "365 days",
) -> None:
    """
    添加数据保留策略

    自动删除超过保留期限的历史数据，防止数据无限增长。

    Args:
        session: 异步数据库会话
        table_name: 超表名称
        retention_period: 数据保留期限，默认保留 365 天

    Example:
        await add_retention_policy(session, "inventory_transactions", "2 years")
    """
    try:
        policy_query = text(
            f"SELECT add_retention_policy('{table_name}', "
            f"INTERVAL '{retention_period}')"
        )
        await session.execute(policy_query)
        await session.commit()
        logger.info(
            f"数据保留策略已添加: {table_name}，保留期限: {retention_period}"
        )

    except Exception as e:
        await session.rollback()
        logger.error(f"添加保留策略失败 ({table_name}): {e}")
        raise


async def init_timescaledb() -> None:
    """
    初始化 TimescaleDB 扩展和所有超表

    在应用启动时调用，确保 TimescaleDB 扩展已安装，
    并将需要的表转换为超表。

    通常在 FastAPI 的 lifespan 事件中调用。
    """
    async with async_session_factory() as session:
        try:
            # 第一步：确保 TimescaleDB 扩展已安装
            await ensure_timescaledb_extension(session)

            # 第二步：将库存变动记录表转换为超表
            # 注意：表必须在 Alembic 迁移中创建后才能转换为超表
            # 这里使用 try-except 处理表可能尚未创建的情况
            hypertable_configs = [
                {
                    "table_name": "inventory_transactions",
                    "time_column": "created_at",
                    "chunk_time_interval": "1 day",
                },
                {
                    "table_name": "inventory_snapshots",
                    "time_column": "snapshot_time",
                    "chunk_time_interval": "1 day",
                },
            ]

            for config in hypertable_configs:
                try:
                    await create_hypertable(
                        session=session,
                        table_name=config["table_name"],
                        time_column=config["time_column"],
                        chunk_time_interval=config["chunk_time_interval"],
                    )
                except Exception as e:
                    # 表可能尚未创建（首次迁移前），记录警告但继续
                    logger.warning(
                        f"超表创建跳过 ({config['table_name']}): {e}"
                    )

            logger.info("TimescaleDB 初始化完成")

        except Exception as e:
            logger.error(f"TimescaleDB 初始化失败: {e}")
            # 初始化失败不应阻止应用启动
            # 在非生产环境可以降级为普通 PostgreSQL
            import os
            if os.getenv("INVENTORY_APP_ENV", "development") != "production":
                logger.warning("TimescaleDB 初始化失败，将以普通 PostgreSQL 模式运行")
            else:
                raise
