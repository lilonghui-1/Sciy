# -*- coding: utf-8 -*-
"""
数据模式包

包含所有 Pydantic 请求/响应模式定义。
"""

# ---------------------------------------------------------------------------
# 通用模式
# ---------------------------------------------------------------------------
from app.schemas.common import (
    PaginatedResponse,
    PaginationParams,
    MessageResponse,
    ErrorResponse,
)

# ---------------------------------------------------------------------------
# 用户模式
# ---------------------------------------------------------------------------
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
)

# ---------------------------------------------------------------------------
# 产品模式
# ---------------------------------------------------------------------------
from app.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)

# ---------------------------------------------------------------------------
# 仓库模式
# ---------------------------------------------------------------------------
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)

# ---------------------------------------------------------------------------
# 供应商模式
# ---------------------------------------------------------------------------
from app.schemas.supplier import (
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)

# ---------------------------------------------------------------------------
# 库存模式
# ---------------------------------------------------------------------------
from app.schemas.inventory import (
    InventoryOverviewResponse,
    InventorySnapshotResponse,
    InventoryTransactionCreate,
    InventoryTransactionResponse,
)

# ---------------------------------------------------------------------------
# 预测模式
# ---------------------------------------------------------------------------
from app.schemas.forecast import (
    BatchForecastRequest,
    ForecastResponse,
    ForecastRunRequest,
    SafetyStockResponse,
)

# ---------------------------------------------------------------------------
# 告警模式
# ---------------------------------------------------------------------------
from app.schemas.alert import (
    AlertEventAcknowledge,
    AlertEventResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)

# ---------------------------------------------------------------------------
# 通知模式
# ---------------------------------------------------------------------------
from app.schemas.notification import (
    NotificationLogResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)

# ---------------------------------------------------------------------------
# ERP 模式
# ---------------------------------------------------------------------------
from app.schemas.erp_sync import (
    ErpSyncLogResponse,
)

# ---------------------------------------------------------------------------
# AI 模式
# ---------------------------------------------------------------------------
from app.schemas.ai import (
    ChatMessage,
    ChatRequest,
)

__all__ = [
    # common
    "PaginationParams",
    "PaginatedResponse",
    "MessageResponse",
    "ErrorResponse",
    # user
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "LoginRequest",
    "LoginResponse",
    "RefreshTokenRequest",
    # product
    "ProductCreate",
    "ProductUpdate",
    "ProductResponse",
    "ProductListResponse",
    # warehouse
    "WarehouseCreate",
    "WarehouseUpdate",
    "WarehouseResponse",
    # supplier
    "SupplierCreate",
    "SupplierUpdate",
    "SupplierResponse",
    # inventory
    "InventorySnapshotResponse",
    "InventoryTransactionCreate",
    "InventoryTransactionResponse",
    "InventoryOverviewResponse",
    # forecast
    "ForecastResponse",
    "ForecastRunRequest",
    "BatchForecastRequest",
    "SafetyStockResponse",
    # alert
    "AlertRuleCreate",
    "AlertRuleUpdate",
    "AlertRuleResponse",
    "AlertEventResponse",
    "AlertEventAcknowledge",
    # notification
    "NotificationPreferenceResponse",
    "NotificationPreferenceUpdate",
    "NotificationLogResponse",
    # erp
    "ErpSyncLogResponse",
    # ai
    "ChatRequest",
    "ChatMessage",
]
