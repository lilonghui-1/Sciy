# -*- coding: utf-8 -*-
"""
认证路由

处理用户注册、登录、令牌刷新和当前用户信息查询。
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.config import get_settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    UnauthorizedException,
)
from app.core.security import (
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token_type,
)
from app.crud.user import user_crud
from app.models.user import User
from app.schemas.user import (
    UserCreate,
    UserResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="用户注册",
)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    注册新用户

    - 检查用户名和邮箱是否已存在
    - 对密码进行哈希处理
    - 创建用户记录
    """
    # 检查用户名是否已存在
    existing_user = await user_crud.get_by_username(db, username=user_in.username)
    if existing_user:
        raise ConflictException(detail=f"用户名 '{user_in.username}' 已被注册")

    # 检查邮箱是否已存在
    existing_email = await user_crud.get_by_email(db, email=user_in.email)
    if existing_email:
        raise ConflictException(detail=f"邮箱 '{user_in.email}' 已被注册")

    # 创建用户
    user_data = user_in.model_dump(exclude={"password"})
    user_data["hashed_password"] = get_password_hash(user_in.password)
    user = await user_crud.create(db, obj_in=user_data)

    logger.info(f"新用户注册成功: {user.username} (ID: {user.id})")
    return UserResponse.model_validate(user)


@router.post("/login", response_model=LoginResponse, summary="用户登录")
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    用户登录

    - 验证用户名和密码
    - 返回 JWT 访问令牌和刷新令牌
    """
    user = await user_crud.authenticate(
        db,
        username=login_data.username,
        password=login_data.password,
    )

    if not user:
        raise UnauthorizedException(detail="用户名或密码错误")

    # 更新最后登录时间
    await user_crud.update(
        db,
        id=user.id,
        obj_in={"last_login_at": datetime.now(timezone.utc).isoformat()},
    )

    # 生成令牌
    settings = get_settings()
    token_data = {"sub": str(user.id), "username": user.username, "role": user.role}

    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    logger.info(f"用户登录成功: {user.username} (ID: {user.id})")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=LoginResponse, summary="刷新令牌")
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    使用刷新令牌获取新的访问令牌

    - 验证刷新令牌有效性
    - 返回新的访问令牌和刷新令牌
    """
    try:
        payload = verify_token_type(refresh_data.refresh_token, "refresh")
    except (ValueError, Exception) as e:
        raise UnauthorizedException(detail="刷新令牌无效或已过期") from e

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException(detail="刷新令牌中缺少用户信息")

    # 查询用户
    user = await user_crud.get(db, id=int(user_id))
    if not user or not user.is_active:
        raise UnauthorizedException(detail="用户不存在或已被禁用")

    # 生成新令牌
    settings = get_settings()
    token_data = {"sub": str(user.id), "username": user.username, "role": user.role}

    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return LoginResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserResponse:
    """
    获取当前登录用户的详细信息

    需要在请求头中携带有效的 JWT 访问令牌。
    """
    return UserResponse.model_validate(current_user)
