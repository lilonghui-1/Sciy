"""
FastAPI 应用工厂模块

创建并配置 FastAPI 应用实例，包含：
- 应用生命周期管理（启动/关闭事件）
- TimescaleDB 初始化
- CORS 中间件配置
- 路由注册
- 全局异常处理器注册
- WebSocket 实时通信端点
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from jose import jwt, ExpiredSignatureError, JWTError
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.init_timescaledb import init_timescaledb
from app.utils.websocket_manager import ws_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理器

    管理应用启动和关闭时的资源初始化与清理：
    - 启动时：初始化 TimescaleDB 扩展和超表
    - 关闭时：关闭数据库连接池

    Args:
        app: FastAPI 应用实例

    Yields:
        None
    """
    # ==================== 启动阶段 ====================
    logger.info("=" * 60)
    logger.info("库存管理系统后端服务正在启动...")
    logger.info("=" * 60)

    settings = get_settings()
    logger.info(f"应用名称: {settings.app_name}")
    logger.info(f"运行环境: {settings.app_env}")
    logger.info(f"调试模式: {settings.debug}")
    logger.info(f"API 前缀: {settings.api_v1_prefix}")

    # 初始化 TimescaleDB
    try:
        logger.info("正在初始化 TimescaleDB...")
        await init_timescaledb()
        logger.info("TimescaleDB 初始化完成")
    except Exception as e:
        logger.warning(f"TimescaleDB 初始化失败（将以普通模式运行）: {e}")

    logger.info("库存管理系统后端服务启动完成")
    logger.info("=" * 60)

    yield  # 应用运行中

    # ==================== 关闭阶段 ====================
    logger.info("库存管理系统后端服务正在关闭...")

    # 关闭数据库连接池
    from app.db.engine import async_engine
    await async_engine.dispose()
    logger.info("数据库连接池已关闭")

    logger.info("库存管理系统后端服务已关闭")


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例

    包含以下配置：
    1. 应用元数据（标题、描述、版本等）
    2. CORS 跨域中间件
    3. 全局异常处理器
    4. API 路由注册
    5. 健康检查端点

    Returns:
        FastAPI: 配置完成的应用实例
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="""
        ## 智能库存管理系统 API

        ### 功能模块
        - **用户认证**: JWT 令牌认证、用户管理
        - **产品管理**: 产品信息 CRUD
        - **仓库管理**: 仓库信息维护
        - **供应商管理**: 供应商信息维护
        - **库存管理**: 库存变动记录、库存查询
        - **需求预测**: 基于 AI 的库存需求预测
        - **预警管理**: 库存预警规则与通知
        - **通知服务**: 邮件/短信/WebSocket 通知
        - **ERP 同步**: 与外部 ERP 系统数据同步
        - **数据导入导出**: Excel/CSV 批量导入导出
        - **AI 智能助手**: 基于自然语言的库存查询与分析
        """,
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
        contact={
            "name": "Inventory System Team",
            "email": "admin@inventory-system.com",
        },
        license_info={
            "name": "MIT",
        },
    )

    # ==================== 注册 CORS 中间件 ====================
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # ==================== 注册全局异常处理器 ====================
    register_exception_handlers(app)

    # ==================== 注册健康检查端点 ====================
    @app.get("/api/v1/health", tags=["系统"], summary="健康检查")
    async def health_check() -> dict:
        """
        系统健康检查端点

        返回系统运行状态信息，用于负载均衡器和监控系统探测。
        """
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
        }

    # ==================== 注册 WebSocket 端点 ====================
    @app.websocket("/ws/{token}")
    async def websocket_endpoint(websocket: WebSocket, token: str) -> None:
        """
        WebSocket 实时通信端点

        通过 URL 路径参数传递 JWT token 进行认证。
        认证成功后建立 WebSocket 连接，保持长连接用于实时消息推送。

        认证流程：
        1. 从路径参数获取 JWT token
        2. 使用系统密钥解码 token，提取 user_id
        3. 认证失败则关闭连接（code 4001）
        4. 认证成功则注册到 ws_manager 并保持连接

        Args:
            websocket: WebSocket 连接实例
            token: JWT 访问令牌（通过 URL 路径参数传递）
        """
        settings = get_settings()

        # 解码 JWT token 获取 user_id
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            user_id: int = payload.get("sub")
            if user_id is None:
                logger.warning(
                    "WebSocket 认证失败: token 中无 sub 字段"
                )
                await websocket.close(code=4001, reason="无效的令牌: 缺少用户标识")
                return

            # sub 字段可能是字符串形式的 user_id，需转换为 int
            user_id = int(user_id)

        except ExpiredSignatureError:
            logger.warning("WebSocket 认证失败: 令牌已过期")
            await websocket.close(code=4001, reason="令牌已过期")
            return
        except JWTError as e:
            logger.warning("WebSocket 认证失败: 无效的令牌, 错误=%s", str(e))
            await websocket.close(code=4001, reason="无效的令牌")
            return
        except (ValueError, TypeError) as e:
            logger.warning(
                "WebSocket 认证失败: user_id 格式错误, 错误=%s", str(e)
            )
            await websocket.close(code=4001, reason="无效的令牌: 用户标识格式错误")
            return
        except Exception as e:
            logger.error(
                "WebSocket 认证过程异常: 错误=%s", str(e), exc_info=True
            )
            await websocket.close(code=4001, reason="认证过程异常")
            return

        # 认证成功，建立连接
        await ws_manager.connect(websocket, user_id)
        logger.info(
            "WebSocket 连接已建立: user_id=%d, 在线用户数=%d",
            user_id,
            ws_manager.get_online_count(),
        )

        try:
            # 保持连接，接收客户端消息（心跳等）
            while True:
                data = await websocket.receive_text()
                # 处理心跳消息，客户端发送 "ping" 时回复 "pong"
                if data == "ping":
                    await websocket.send_text("pong")
                else:
                    logger.debug(
                        "WebSocket 收到消息: user_id=%d, data=%s",
                        user_id,
                        data[:200] if len(data) > 200 else data,
                    )

        except WebSocketDisconnect:
            logger.info(
                "WebSocket 客户端断开连接: user_id=%d", user_id
            )
        except Exception as e:
            logger.error(
                "WebSocket 连接异常断开: user_id=%d, 错误=%s",
                user_id,
                str(e),
                exc_info=True,
            )
        finally:
            ws_manager.disconnect(websocket, user_id)
            logger.info(
                "WebSocket 连接已清理: user_id=%d, 在线用户数=%d",
                user_id,
                ws_manager.get_online_count(),
            )

    # ==================== 注册 API 路由 ====================
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    return app


# 创建应用实例（供 uvicorn 直接导入）
app = create_app()
