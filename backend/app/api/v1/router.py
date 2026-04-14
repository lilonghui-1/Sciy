# -*- coding: utf-8 -*-
"""
API v1 路由聚合模块

将所有子模块的路由注册到统一的 API 路由器中。
每个功能模块有独立的路由前缀和标签。
"""

from fastapi import APIRouter

# ==================== 导入各子模块路由器 ====================

from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.products import router as products_router
from app.api.v1.warehouses import router as warehouses_router
from app.api.v1.suppliers import router as suppliers_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.forecasts import router as forecasts_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.erp_sync import router as erp_sync_router
from app.api.v1.import_export import router as import_export_router
from app.api.v1.ai_chat import router as ai_chat_router


# ==================== 聚合路由器 ====================
api_router = APIRouter()

# 注册所有子模块路由
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(products_router)
api_router.include_router(warehouses_router)
api_router.include_router(suppliers_router)
api_router.include_router(inventory_router)
api_router.include_router(forecasts_router)
api_router.include_router(alerts_router)
api_router.include_router(notifications_router)
api_router.include_router(erp_sync_router)
api_router.include_router(import_export_router)
api_router.include_router(ai_chat_router)
