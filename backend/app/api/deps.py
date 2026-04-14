"""
API 依赖注入模块

提供 FastAPI 路由中常用的依赖项：
- get_db: 获取数据库会话
- get_current_user: 获取当前认证用户
- get_current_active_user: 获取当前活跃用户
- get_current_admin_user: 获取当前管理员用户
"""

from typing import Optional
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.core.security import oauth2_scheme, decode_token
from app.db.engine import get_async_session

# OAuth2 令牌提取方案（复用 security 模块中的配置）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取异步数据库会话依赖

    封装数据库会话的获取逻辑，确保每个请求使用独立的会话，
    并在请求结束后正确关闭。

    Yields:
        AsyncSession: 异步数据库会话

    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async for session in get_async_session():
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    获取当前认证用户依赖

    从 JWT 令牌中解析用户信息，并从数据库查询用户详情。
    如果令牌无效或用户不存在，抛出 UnauthorizedException。

    Args:
        token: JWT 令牌（从 Authorization 头自动提取）
        db: 数据库会话（自动注入）

    Returns:
        dict: 当前用户的 ORM 模型对象

    Raises:
        UnauthorizedException: 令牌无效或用户不存在

    Usage:
        @router.get("/me")
        async def get_me(current_user = Depends(get_current_user)):
            return current_user
    """
    credentials_exception = UnauthorizedException(
        detail="无法验证用户凭据，请重新登录"
    )

    try:
        # 解码 JWT 令牌
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        # 令牌类型校验
        token_type = payload.get("type")
        if token_type != "access":
            raise UnauthorizedException(
                detail="令牌类型错误，请使用访问令牌"
            )

    except (JWTError, ValueError) as e:
        raise credentials_exception from e

    # 从数据库查询用户
    # 注意：这里使用动态导入避免循环依赖
    # 在实际模型定义后，应替换为具体的用户模型查询
    try:
        from app.models.user import User  # noqa: F811

        stmt = select(User).where(User.id == int(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
    except ImportError:
        # 模型尚未定义时的降级处理
        # 返回包含基本信息的字典
        user = None

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user=Depends(get_current_user),
) -> dict:
    """
    获取当前活跃用户依赖

    在 get_current_user 基础上增加用户状态检查，
    确保用户账户处于活跃状态。

    Args:
        current_user: 当前用户（从 get_current_user 依赖获取）

    Returns:
        当前活跃用户的 ORM 模型对象

    Raises:
        UnauthorizedException: 用户账户已被禁用
    """
    # 检查用户是否被禁用
    # 兼容 ORM 对象和字典两种格式
    if hasattr(current_user, "is_active"):
        if not current_user.is_active:
            raise UnauthorizedException(
                detail="用户账户已被禁用，请联系管理员"
            )
    elif isinstance(current_user, dict):
        if not current_user.get("is_active", True):
            raise UnauthorizedException(
                detail="用户账户已被禁用，请联系管理员"
            )

    return current_user


async def get_current_admin_user(
    current_user=Depends(get_current_active_user),
) -> dict:
    """
    获取当前管理员用户依赖

    在 get_current_active_user 基础上增加管理员权限检查，
    确保用户具有管理员角色。

    Args:
        current_user: 当前活跃用户（从 get_current_active_user 依赖获取）

    Returns:
        当前管理员用户的 ORM 模型对象

    Raises:
        ForbiddenException: 用户没有管理员权限
    """
    is_admin = False

    # 兼容 ORM 对象和字典两种格式
    if hasattr(current_user, "role"):
        is_admin = current_user.role == "admin"
    elif hasattr(current_user, "is_admin"):
        is_admin = current_user.is_admin
    elif isinstance(current_user, dict):
        is_admin = current_user.get("role") == "admin" or current_user.get("is_admin", False)

    if not is_admin:
        raise ForbiddenException(
            detail="需要管理员权限才能执行此操作"
        )

    return current_user


def get_optional_current_user(
    token: Optional[str] = Depends(OAuth2PasswordBearer(
        tokenUrl="/api/v1/auth/login",
        auto_error=False,
    )),
    db: AsyncSession = Depends(get_db),
) -> Optional[dict]:
    """
    获取可选的当前用户依赖

    与 get_current_user 类似，但如果未提供令牌或令牌无效，
    不会抛出异常，而是返回 None。适用于需要区分登录/未登录用户的场景。

    Args:
        token: JWT 令牌（可选，未提供时返回 None）
        db: 数据库会话

    Returns:
        Optional[dict]: 当前用户对象，未认证时返回 None
    """
    if token is None:
        return None

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            return None

        # 简化版：仅返回令牌中的用户 ID
        return {"id": int(user_id), **payload}
    except (JWTError, ValueError, TypeError):
        return None
