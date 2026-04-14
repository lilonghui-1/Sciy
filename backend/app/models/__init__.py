# -*- coding: utf-8 -*-
"""
数据模型包

包含所有 SQLAlchemy ORM 模型定义。
导入此包即可注册所有模型到 Base.metadata，供 Alembic 自动检测。
"""

from app.models.user import User
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.inventory_snapshot import InventorySnapshot
from app.models.inventory_transaction import InventoryTransaction
from app.models.demand_forecast import DemandForecast
from app.models.alert_rule import AlertRule
from app.models.alert_event import AlertEvent
from app.models.notification_log import NotificationLog
from app.models.erp_sync_log import ErpSyncLog
from app.models.erp_sync import ErpConfig
from app.models.notification import NotificationPreference
from app.models.import_export import ImportExportJob

__all__ = [
    "User",
    "Supplier",
    "Product",
    "Warehouse",
    "InventorySnapshot",
    "InventoryTransaction",
    "DemandForecast",
    "AlertRule",
    "AlertEvent",
    "NotificationLog",
    "ErpSyncLog",
    "ErpConfig",
    "NotificationPreference",
    "ImportExportJob",
]
