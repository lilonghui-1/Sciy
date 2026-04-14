"""
应用配置模块 - 基于 Pydantic Settings 的集中配置管理

所有配置项均支持通过环境变量覆盖，环境变量名以 INVENTORY_ 为前缀。
例如: INVENTORY_DATABASE_URL, INVENTORY_SECRET_KEY 等。
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置类，从环境变量和 .env 文件加载配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="INVENTORY_",
        case_sensitive=False,
        extra="ignore",
    )

    # ==================== 应用基础配置 ====================
    app_name: str = Field(default="Inventory Management System", description="应用名称")
    app_env: str = Field(default="development", description="运行环境: development / staging / production")
    app_version: str = Field(default="0.1.0", description="应用版本号")
    debug: bool = Field(default=False, description="调试模式")
    secret_key: str = Field(
        default="change-me-in-production-please-use-a-secure-random-key",
        description="JWT 签名密钥，生产环境必须修改",
    )
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 路由前缀")

    # ==================== CORS 配置 ====================
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="允许的跨域来源列表",
    )
    cors_allow_credentials: bool = Field(default=True, description="允许跨域携带凭证")
    cors_allow_methods: list[str] = Field(
        default=["*"],
        description="允许的跨域 HTTP 方法",
    )
    cors_allow_headers: list[str] = Field(
        default=["*"],
        description="允许的跨域请求头",
    )

    # ==================== 数据库配置 ====================
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/inventory_db",
        description="异步数据库连接 URL",
    )
    database_sync_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/inventory_db",
        description="同步数据库连接 URL（用于 Alembic 迁移）",
    )
    database_pool_size: int = Field(default=20, description="数据库连接池大小")
    database_max_overflow: int = Field(default=10, description="数据库连接池最大溢出数")
    database_pool_timeout: int = Field(default=30, description="数据库连接池超时时间（秒）")
    database_pool_recycle: int = Field(default=3600, description="数据库连接回收时间（秒）")
    database_echo: bool = Field(default=False, description="是否输出 SQL 日志")

    # ==================== Redis 配置 ====================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 连接 URL",
    )
    redis_cache_ttl: int = Field(default=3600, description="Redis 缓存默认过期时间（秒）")

    # ==================== JWT 配置 ====================
    jwt_algorithm: str = Field(default="HS256", description="JWT 签名算法")
    jwt_access_token_expire_minutes: int = Field(default=30, description="访问令牌过期时间（分钟）")
    jwt_refresh_token_expire_days: int = Field(default=7, description="刷新令牌过期时间（天）")

    # ==================== OpenAI 配置 ====================
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API 密钥")
    openai_model: str = Field(default="gpt-4o", description="OpenAI 模型名称")
    openai_temperature: float = Field(default=0.7, description="OpenAI 模型温度参数")
    openai_max_tokens: int = Field(default=2000, description="OpenAI 最大生成 token 数")

    # ==================== ERP 系统配置 ====================
    erp_api_url: str = Field(
        default="http://localhost:8080/api",
        description="ERP 系统 API 地址",
    )
    erp_api_key: Optional[str] = Field(default=None, description="ERP 系统 API 密钥")
    erp_sync_batch_size: int = Field(default=100, description="ERP 同步批次大小")
    erp_sync_timeout: int = Field(default=60, description="ERP 同步请求超时时间（秒）")

    # ==================== SMTP 邮件配置 ====================
    smtp_host: str = Field(default="smtp.gmail.com", description="SMTP 服务器地址")
    smtp_port: int = Field(default=587, description="SMTP 服务器端口")
    smtp_username: Optional[str] = Field(default=None, description="SMTP 用户名")
    smtp_password: Optional[str] = Field(default=None, description="SMTP 密码")
    smtp_use_tls: bool = Field(default=True, description="是否启用 TLS")
    smtp_from_email: str = Field(default="noreply@inventory-system.com", description="发件人邮箱")
    smtp_from_name: str = Field(default="库存管理系统", description="发件人名称")

    # ==================== Twilio 短信配置 ====================
    twilio_account_sid: Optional[str] = Field(default=None, description="Twilio 账户 SID")
    twilio_auth_token: Optional[str] = Field(default=None, description="Twilio 认证令牌")
    twilio_phone_number: Optional[str] = Field(default=None, description="Twilio 发送号码")
    twilio_verify_sid: Optional[str] = Field(default=None, description="Twilio 验证服务 SID")

    # ==================== Webhook 配置 ====================
    webhook_url: Optional[str] = Field(default=None, description="Webhook 回调 URL")
    webhook_secret: Optional[str] = Field(default=None, description="Webhook 签名密钥")

    # ==================== Celery 配置 ====================
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        description="Celery 消息代理 URL",
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        description="Celery 结果存储 URL",
    )

    # ==================== 文件上传配置 ====================
    upload_max_size_mb: int = Field(default=10, description="文件上传最大大小（MB）")
    upload_allowed_extensions: list[str] = Field(
        default=["xlsx", "xls", "csv"],
        description="允许上传的文件扩展名",
    )

    # ==================== 分页默认配置 ====================
    default_page_size: int = Field(default=20, description="默认分页大小")
    max_page_size: int = Field(default=100, description="最大分页大小")

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """验证运行环境只能是预定义值"""
        allowed = {"development", "staging", "production", "test"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"app_env 必须是以下值之一: {allowed}")
        return v_lower

    @property
    def is_production(self) -> bool:
        """判断是否为生产环境"""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """判断是否为开发环境"""
        return self.app_env == "development"

    @property
    def is_testing(self) -> bool:
        """判断是否为测试环境"""
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    """
    获取全局配置单例（使用 lru_cache 确保只创建一次）

    在整个应用生命周期中，配置对象只会被实例化一次，
    后续调用直接返回缓存的结果，避免重复读取环境变量。
    """
    return Settings()
