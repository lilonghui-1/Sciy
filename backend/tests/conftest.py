"""
Pytest 测试配置与共享 fixtures

提供异步测试客户端、测试数据库会话等测试基础设施。
所有测试文件自动使用此配置。
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ==================== 测试数据库配置 ====================
# 使用 SQLite 作为测试数据库，避免依赖外部 PostgreSQL
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

# 创建测试专用引擎
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# 创建测试会话工厂
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ==================== 事件循环 fixture ====================
@pytest.fixture(scope="session")
def event_loop():
    """
    创建事件循环 fixture

    为所有异步测试提供统一的事件循环实例。
    使用 session 级别确保整个测试会话共享同一个事件循环。
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ==================== 数据库 fixture ====================
@pytest.fixture(scope="session")
async def test_db_engine():
    """
    创建测试数据库引擎

    在测试会话开始时创建所有表结构，
    在测试会话结束时清理所有表。
    """
    # 导入所有模型以确保 Base.metadata 包含所有表定义
    from app.db.base import Base

    # 创建所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    # 测试结束后删除所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # 关闭引擎
    await test_engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    """
    创建测试数据库会话

    为每个测试函数提供独立的数据库会话，
    测试结束后自动回滚，确保测试之间互不影响。

    Args:
        test_db_engine: 测试数据库引擎

    Yields:
        AsyncSession: 测试用数据库会话
    """
    # 使用连接级别的嵌套事务
    async with test_db_engine.connect() as connection:
        # 开始事务
        transaction = await connection.begin()

        # 创建绑定到该连接的会话
        session = TestSessionLocal(bind=connection)

        yield session

        # 测试结束后回滚事务，撤销所有数据变更
        await session.close()
        await transaction.rollback()


# ==================== FastAPI 测试客户端 fixture ====================
@pytest.fixture(scope="function")
async def client(test_db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    创建异步 HTTP 测试客户端

    基于 FastAPI 的 TestClient，使用 ASGI 传输层进行测试。
    自动注入测试数据库会话，替代真实的数据库连接。

    Args:
        test_db_session: 测试数据库会话

    Yields:
        AsyncClient: 异步 HTTP 测试客户端

    Usage:
        async def test_health_check(client: AsyncClient):
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
    """
    from app.main import app
    from app.api.deps import get_db

    # 覆盖数据库依赖，注入测试会话
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    # 创建异步测试客户端
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # 清理依赖覆盖
    app.dependency_overrides.clear()


# ==================== 认证相关 fixture ====================
@pytest.fixture(scope="function")
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """
    获取认证请求头

    模拟用户登录流程，获取有效的 JWT 令牌，
    返回包含 Authorization 头的字典。

    Args:
        client: 异步测试客户端

    Returns:
        dict: 包含 Bearer 令牌的请求头字典

    Usage:
        async def test_get_me(client: AsyncClient, auth_headers: dict):
            response = await client.get("/api/v1/users/me", headers=auth_headers)
            assert response.status_code == 200
    """
    from app.core.security import create_access_token

    # 创建测试用户令牌
    token = create_access_token(data={"sub": "1", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
async def admin_auth_headers(client: AsyncClient) -> dict[str, str]:
    """
    获取管理员认证请求头

    与 auth_headers 类似，但使用管理员角色的令牌。

    Args:
        client: 异步测试客户端

    Returns:
        dict: 包含管理员 Bearer 令牌的请求头字典
    """
    from app.core.security import create_access_token

    token = create_access_token(data={"sub": "1", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


# ==================== Mock fixtures ====================
@pytest.fixture(scope="function")
def mock_redis():
    """
    创建 Redis 客户端 mock

    模拟 Redis 操作，避免测试时依赖真实的 Redis 服务。

    Yields:
        AsyncMock: Redis 客户端 mock 对象
    """
    redis_mock = AsyncMock()
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = True
    redis_mock.exists.return_value = False
    redis_mock.expire.return_value = True
    redis_mock.ping.return_value = True
    return redis_mock


@pytest.fixture(scope="function")
def mock_celery():
    """
    创建 Celery 任务 mock

    模拟 Celery 异步任务调用，避免测试时启动 Worker。

    Yields:
        AsyncMock: Celery 任务 mock 对象
    """
    celery_mock = AsyncMock()
    celery_mock.delay.return_value = AsyncMock(id="test-task-id")
    celery_mock.apply_async.return_value = AsyncMock(id="test-task-id")
    return celery_mock


@pytest.fixture(scope="function")
def mock_openai():
    """
    创建 OpenAI API mock

    模拟 OpenAI API 调用，避免测试时消耗 API 额度。

    Yields:
        AsyncMock: OpenAI 客户端 mock 对象
    """
    openai_mock = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "这是 AI 助手的测试回复。"
    openai_mock.chat.completions.create.return_value = mock_response
    return openai_mock


# ==================== 测试数据 fixtures ====================
@pytest.fixture(scope="function")
def sample_product_data() -> dict:
    """
    创建测试用产品数据

    Returns:
        dict: 模拟产品数据字典
    """
    return {
        "name": "测试产品A",
        "sku": "TEST-SKU-001",
        "description": "这是一个测试产品",
        "category": "电子产品",
        "unit": "个",
        "unit_price": 99.99,
        "cost_price": 59.99,
        "reorder_point": 50,
        "safety_stock": 20,
        "supplier_id": 1,
    }


@pytest.fixture(scope="function")
def sample_warehouse_data() -> dict:
    """
    创建测试用仓库数据

    Returns:
        dict: 模拟仓库数据字典
    """
    return {
        "name": "测试仓库A",
        "code": "WH-TEST-001",
        "address": "上海市浦东新区测试路100号",
        "city": "上海",
        "province": "上海市",
        "postal_code": "200000",
        "capacity": 10000,
        "manager_name": "张三",
        "manager_phone": "13800138000",
    }


@pytest.fixture(scope="function")
def sample_supplier_data() -> dict:
    """
    创建测试用供应商数据

    Returns:
        dict: 模拟供应商数据字典
    """
    return {
        "name": "测试供应商A",
        "code": "SUP-TEST-001",
        "contact_person": "李四",
        "contact_phone": "13900139000",
        "email": "test@supplier.com",
        "address": "北京市朝阳区供应商大厦1号",
        "city": "北京",
        "province": "北京市",
        "lead_time_days": 7,
    }


@pytest.fixture(scope="function")
def sample_user_data() -> dict:
    """
    创建测试用用户数据

    Returns:
        dict: 模拟用户数据字典
    """
    return {
        "username": "testuser",
        "email": "test@example.com",
        "full_name": "测试用户",
        "phone": "13700137000",
        "role": "user",
        "is_active": True,
    }
