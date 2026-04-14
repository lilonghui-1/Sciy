# -*- coding: utf-8 -*-
from __future__ import annotations

"""
CRUD 操作包

包含所有数据库 CRUD（创建、读取、更新、删除）操作实例。
"""

from app.crud.base import BaseCRUD
from app.crud.user import user_crud
from app.crud.product import product_crud
from app.crud.inventory import inventory_crud
from app.crud.forecast import forecast_crud
from app.crud.alert import alert_rule_crud, alert_event_crud

__all__ = [
    "BaseCRUD",
    "user_crud",
    "product_crud",
    "inventory_crud",
    "forecast_crud",
    "alert_rule_crud",
    "alert_event_crud",
]
