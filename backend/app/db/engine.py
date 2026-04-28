"""
数据库引擎与会话管理

提供异步 SQLAlchemy 引擎创建、会话工厂和 FastAPI 依赖注入。
使用 asyncpg 作为异步驱动，支持连接池管理。
兼容人大金仓 KingbaseES（基于 PostgreSQL 协议）。
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def create_engine():
    """
    创建异步 SQLAlchemy 引擎

    根据配置文件中的数据库连接参数创建引擎实例，
    配置连接池大小、超时时间等参数。

    Returns:
        AsyncEngine: SQLAlchemy 异步引擎实例
    """
    settings = get_settings()

    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_recycle=settings.database_pool_recycle,
        pool_pre_ping=True,  # 连接前先检测是否有效
        isolation_level="READ COMMITTED",  # 默认隔离级别
    )
    return engine


# 创建全局引擎实例
async_engine = create_engine()

# 创建异步会话工厂
# expire_on_commit=False 避免提交后属性访问导致懒加载报错
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：获取异步数据库会话

    使用 async with 确保会话在使用完毕后自动关闭，
    即使发生异常也能正确释放数据库连接。

    Yields:
        AsyncSession: 异步数据库会话实例

    Usage:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
