"""
安全模块 - JWT 令牌管理与密码哈希

提供用户认证相关的核心安全功能：
- JWT 访问令牌和刷新令牌的创建与验证
- 密码哈希（bcrypt）与验证
- OAuth2 密码流认证
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# ==================== 密码哈希上下文 ====================
# 使用 bcrypt 算法进行密码哈希，自动处理盐值
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==================== OAuth2 令牌提取 ====================
# 从请求头 Authorization: Bearer <token> 中提取令牌
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码与哈希密码是否匹配

    Args:
        plain_password: 用户输入的明文密码
        hashed_password: 数据库中存储的哈希密码

    Returns:
        bool: 密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    对明文密码进行 bcrypt 哈希

    Args:
        password: 用户输入的明文密码

    Returns:
        str: 哈希后的密码字符串
    """
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建 JWT 访问令牌

    Args:
        data: 要编码到令牌中的数据载荷（通常包含 sub: user_id）
        expires_delta: 令牌有效期，默认使用配置中的过期时间

    Returns:
        str: 编码后的 JWT 令牌字符串
    """
    settings = get_settings()
    to_encode = data.copy()

    # 设置过期时间
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode.update({
        "exp": expire,
        "type": "access",  # 令牌类型标识
        "iat": datetime.now(timezone.utc),  # 签发时间
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建 JWT 刷新令牌

    刷新令牌的有效期比访问令牌长，用于获取新的访问令牌。

    Args:
        data: 要编码到令牌中的数据载荷
        expires_delta: 令牌有效期，默认使用配置中的过期时间

    Returns:
        str: 编码后的 JWT 刷新令牌字符串
    """
    settings = get_settings()
    to_encode = data.copy()

    # 设置过期时间
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

    to_encode.update({
        "exp": expire,
        "type": "refresh",  # 标记为刷新令牌
        "iat": datetime.now(timezone.utc),
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    解码并验证 JWT 令牌

    Args:
        token: JWT 令牌字符串

    Returns:
        dict: 令牌中的数据载荷

    Raises:
        JWTError: 令牌无效、过期或签名不匹配
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    return payload


def verify_token_type(token: str, expected_type: str) -> dict:
    """
    验证令牌类型并返回载荷

    Args:
        token: JWT 令牌字符串
        expected_type: 期望的令牌类型（"access" 或 "refresh"）

    Returns:
        dict: 令牌数据载荷

    Raises:
        ValueError: 令牌类型不匹配
        JWTError: 令牌无效或已过期
    """
    payload = decode_token(token)
    token_type = payload.get("type")
    if token_type != expected_type:
        raise ValueError(f"令牌类型错误: 期望 '{expected_type}'，实际 '{token_type}'")
    return payload
