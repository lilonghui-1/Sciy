"""
全局异常处理模块

定义应用中使用的自定义异常类，以及 FastAPI 全局异常处理器。
所有 API 错误响应都遵循统一的 JSON 格式。
"""

from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppException(Exception):
    """
    应用基础异常类

    所有自定义业务异常的父类，包含状态码、错误码和详细信息。
    """

    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = "服务器内部错误",
        error_code: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code or f"ERR_{status_code}"
        self.headers = headers
        super().__init__(detail)


class NotFoundException(AppException):
    """资源未找到异常 - 对应 HTTP 404"""

    def __init__(
        self,
        detail: str = "请求的资源不存在",
        error_code: Optional[str] = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code=error_code or "NOT_FOUND",
        )


class UnauthorizedException(AppException):
    """未认证异常 - 对应 HTTP 401"""

    def __init__(
        self,
        detail: str = "认证失败，请检查您的凭据",
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        # 401 响应通常需要 WWW-Authenticate 头
        default_headers = {"WWW-Authenticate": "Bearer"}
        if headers:
            default_headers.update(headers)
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="UNAUTHORIZED",
            headers=default_headers,
        )


class ForbiddenException(AppException):
    """权限不足异常 - 对应 HTTP 403"""

    def __init__(
        self,
        detail: str = "您没有权限执行此操作",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="FORBIDDEN",
        )


class BadRequestException(AppException):
    """请求参数错误异常 - 对应 HTTP 400"""

    def __init__(
        self,
        detail: str = "请求参数不正确",
        error_code: Optional[str] = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code or "BAD_REQUEST",
        )


class ConflictException(AppException):
    """资源冲突异常 - 对应 HTTP 409（如唯一约束冲突）"""

    def __init__(
        self,
        detail: str = "资源冲突，该记录已存在",
        error_code: Optional[str] = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code=error_code or "CONFLICT",
        )


class RateLimitException(AppException):
    """请求频率超限异常 - 对应 HTTP 429"""

    def __init__(
        self,
        detail: str = "请求过于频繁，请稍后再试",
        retry_after: int = 60,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            error_code="RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )


class ExternalServiceException(AppException):
    """外部服务调用异常 - 对应 HTTP 502"""

    def __init__(
        self,
        detail: str = "外部服务调用失败",
        service_name: Optional[str] = None,
    ) -> None:
        error_code = f"EXTERNAL_SERVICE_ERROR"
        if service_name:
            error_code = f"{service_name.upper()}_SERVICE_ERROR"
            detail = f"{service_name} 服务调用失败: {detail}"
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
            error_code=error_code,
        )


class DatabaseException(AppException):
    """数据库操作异常 - 对应 HTTP 500"""

    def __init__(
        self,
        detail: str = "数据库操作失败",
    ) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="DATABASE_ERROR",
        )


class FileUploadException(AppException):
    """文件上传异常 - 对应 HTTP 413 或 415"""

    def __init__(
        self,
        detail: str = "文件上传失败",
        status_code: int = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail=detail,
            error_code="FILE_UPLOAD_ERROR",
        )


class InventoryException(AppException):
    """库存业务逻辑异常 - 对应 HTTP 422"""

    def __init__(
        self,
        detail: str = "库存操作失败",
        error_code: Optional[str] = None,
    ) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code=error_code or "INVENTORY_ERROR",
        )


def build_error_response(
    status_code: int,
    detail: str,
    error_code: str,
    path: str,
) -> dict[str, Any]:
    """
    构建统一的错误响应格式

    Args:
        status_code: HTTP 状态码
        detail: 错误详情
        error_code: 应用层错误码
        path: 请求路径

    Returns:
        dict: 标准化的错误响应体
    """
    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": detail,
            "status": status_code,
        },
        "path": path,
    }


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册全局异常处理器到 FastAPI 应用

    包含以下异常的处理器：
    - AppException: 所有自定义业务异常
    - RequestValidationError: 请求参数验证错误
    - Exception: 兜底的未捕获异常处理

    Args:
        app: FastAPI 应用实例
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """自定义业务异常处理器"""
        content = build_error_response(
            status_code=exc.status_code,
            detail=exc.detail,
            error_code=exc.error_code,
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """请求参数验证错误处理器"""
        # 将 Pydantic 验证错误转换为更友好的格式
        errors = exc.errors()
        formatted_errors: list[dict[str, Any]] = []
        for error in errors:
            formatted_errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            })

        content = {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数验证失败",
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "details": formatted_errors,
            },
            "path": str(request.url.path),
        }
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(content),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """全局兜底异常处理器 - 捕获所有未处理的异常"""
        content = build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试",
            error_code="INTERNAL_SERVER_ERROR",
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content,
        )
