# -*- coding: utf-8 -*-
"""
ERP 同步服务

提供与外部 ERP 系统之间的数据同步能力，包括：
- 从 ERP 拉取产品与库存数据（全量 / 增量）
- 向 ERP 推送库存调整数据
- 同步日志记录与状态追踪

所有 HTTP 请求使用 httpx.AsyncClient，并通过 tenacity 实现自动重试。
"""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.crud.inventory import inventory_crud
from app.crud.product import product_crud
from app.models.erp_sync_log import ErpSyncLog
from app.models.product import Product

logger = logging.getLogger(__name__)

# ==================== 重试策略 ====================
# 3 次重试，指数退避（1s -> 2s -> 4s），仅对连接错误和超时重试

_RETRYABLE_ERRORS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
)


def _build_retry_decorator() -> Any:
    """
    构建带配置的 tenacity retry 装饰器。

    使用函数包装以便在运行时读取 settings 中的超时配置。
    """
    settings = get_settings()

    return retry(
        retry=retry_if_exception_type(_RETRYABLE_ERRORS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )


class ErpSyncService:
    """
    ERP 同步服务

    封装与 ERP 系统的所有数据交互，包括拉取和推送操作。
    每次同步操作都会生成 ErpSyncLog 记录以供审计。
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化 ERP 同步服务。

        Args:
            db: 异步数据库会话
        """
        self.db = db
        self.settings = get_settings()

    # ==================== HTTP 客户端 ====================

    def _build_headers(self) -> dict[str, str]:
        """构建请求头，包含 API 密钥（如已配置）。"""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.settings.erp_api_key:
            headers["Authorization"] = f"Bearer {self.settings.erp_api_key}"
        return headers

    def _build_client(self) -> httpx.AsyncClient:
        """创建 httpx 异步客户端实例。"""
        return httpx.AsyncClient(
            base_url=self.settings.erp_api_url,
            headers=self._build_headers(),
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(self.settings.erp_sync_timeout),
                write=30.0,
                pool=10.0,
            ),
        )

    # ==================== ERP API 调用 ====================

    @_build_retry_decorator()
    async def fetch_inventory(
        self,
        updated_since: str | None = None,
    ) -> dict:
        """
        从 ERP 拉取库存数据。

        Args:
            updated_since: 增量同步起始时间（ISO 8601 格式），为 None 时拉取全量

        Returns:
            ERP API 返回的库存数据字典，格式如：
            {"items": [...], "total": int, "has_more": bool}

        Raises:
            httpx.HTTPStatusError: ERP 返回非 2xx 状态码
            httpx.ConnectError: 无法连接到 ERP 服务
            httpx.TimeoutException: 请求超时
        """
        params: dict[str, Any] = {}
        if updated_since:
            params["updated_since"] = updated_since

        async with self._build_client() as client:
            response = await client.get("/inventory", params=params)
            response.raise_for_status()
            data = response.json()

        logger.info(
            "从 ERP 拉取库存数据完成: total=%s, updated_since=%s",
            data.get("total", 0),
            updated_since,
        )
        return data

    @_build_retry_decorator()
    async def fetch_products(self) -> dict:
        """
        从 ERP 拉取产品列表。

        Returns:
            ERP API 返回的产品数据字典，格式如：
            {"items": [...], "total": int}

        Raises:
            httpx.HTTPStatusError: ERP 返回非 2xx 状态码
            httpx.ConnectError: 无法连接到 ERP 服务
            httpx.TimeoutException: 请求超时
        """
        async with self._build_client() as client:
            response = await client.get("/products")
            response.raise_for_status()
            data = response.json()

        logger.info("从 ERP 拉取产品数据完成: total=%s", data.get("total", 0))
        return data

    @_build_retry_decorator()
    async def push_adjustment(
        self,
        product_erp_code: str,
        new_quantity: int,
        reason: str,
    ) -> dict:
        """
        向 ERP 推送库存调整。

        Args:
            product_erp_code: 产品的 ERP 编码
            new_quantity: 调整后的新数量
            reason: 调整原因

        Returns:
            ERP API 的响应字典

        Raises:
            httpx.HTTPStatusError: ERP 返回非 2xx 状态码
            httpx.ConnectError: 无法连接到 ERP 服务
            httpx.TimeoutException: 请求超时
        """
        payload = {
            "erp_code": product_erp_code,
            "new_quantity": new_quantity,
            "reason": reason,
        }

        async with self._build_client() as client:
            response = await client.post("/inventory/adjustment", json=payload)
            response.raise_for_status()
            data = response.json()

        logger.info(
            "向 ERP 推送库存调整完成: erp_code='%s', new_quantity=%d",
            product_erp_code,
            new_quantity,
        )
        return data

    # ==================== 同步日志 ====================

    async def _create_sync_log(
        self,
        sync_type: str,
        direction: str,
    ) -> ErpSyncLog:
        """
        创建同步日志记录。

        Args:
            sync_type: 同步类型 ("full" / "incremental")
            direction: 同步方向 ("pull" / "push")

        Returns:
            新创建的同步日志实例
        """
        log = ErpSyncLog(
            sync_type=sync_type,
            direction=direction,
            entity_type="inventory",
            status="running",
            records_processed=0,
            records_failed=0,
            started_at=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        return log

    async def _update_sync_log(
        self,
        log: ErpSyncLog,
        status: str,
        processed: int,
        failed: int = 0,
        error: str | None = None,
    ) -> ErpSyncLog:
        """
        更新同步日志记录。

        Args:
            log: 同步日志实例
            status: 新状态 ("success" / "failed")
            processed: 已处理记录数
            failed: 失败记录数
            error: 错误信息（可选）

        Returns:
            更新后的同步日志实例
        """
        log.status = status
        log.records_processed = processed
        log.records_failed = failed
        log.error_message = error
        log.finished_at = datetime.utcnow()
        await self.db.flush()
        await self.db.refresh(log)
        return log

    # ==================== 产品 Upsert ====================

    async def _upsert_product(self, item: dict) -> Product:
        """
        根据 ERP 数据创建或更新产品。

        优先通过 erp_code 查找产品，找不到则通过 sku 查找。
        都找不到则创建新产品。

        Args:
            item: ERP 返回的单条产品数据，预期包含以下字段：
                - erp_code: ERP 编码
                - sku: SKU 编码
                - name: 产品名称
                - barcode: 条形码（可选）
                - category: 分类（可选）
                - unit: 计量单位（可选）
                - unit_cost: 单位成本（可选）
                - selling_price: 销售单价（可选）

        Returns:
            产品实例
        """
        erp_code = item.get("erp_code", "")
        sku = item.get("sku", "")

        # 优先按 erp_code 查找
        product: Product | None = None
        if erp_code:
            stmt = select(Product).where(Product.erp_code == erp_code)
            result = await self.db.execute(stmt)
            product = result.scalar_one_or_none()

        # 其次按 sku 查找
        if product is None and sku:
            product = await product_crud.get_by_sku(db=self.db, sku=sku)

        # 准备更新/创建数据
        product_data: dict[str, Any] = {
            "sku": sku,
            "name": item.get("name", sku),
            "barcode": item.get("barcode"),
            "category": item.get("category"),
            "unit": item.get("unit", "个"),
            "is_active": True,
        }

        # 安全解析数值字段
        unit_cost = item.get("unit_cost")
        if unit_cost is not None:
            try:
                product_data["unit_cost"] = float(Decimal(str(unit_cost)))
            except (InvalidOperation, ValueError, TypeError):
                product_data["unit_cost"] = 0.0

        selling_price = item.get("selling_price")
        if selling_price is not None:
            try:
                product_data["selling_price"] = float(Decimal(str(selling_price)))
            except (InvalidOperation, ValueError, TypeError):
                product_data["selling_price"] = product_data.get("unit_cost", 0.0)
        else:
            product_data["selling_price"] = product_data.get("unit_cost", 0.0)

        if erp_code:
            product_data["erp_code"] = erp_code

        if product is not None:
            # 更新已有产品
            update_data = {k: v for k, v in product_data.items() if v is not None}
            if update_data:
                await product_crud.update(self.db, id=product.id, obj_in=update_data)
            return product
        else:
            # 创建新产品
            product_data.setdefault("supplier_id", 1)
            product = await product_crud.create(self.db, obj_in=product_data)
            logger.info("ERP 同步创建新产品: id=%d, sku='%s', erp_code='%s'", product.id, product.sku, erp_code)
            return product

    # ==================== 全量同步 ====================

    async def full_sync(
        self,
        operator_id: int | None = None,
    ) -> dict:
        """
        执行全量同步：从 ERP 拉取所有产品和库存数据，写入本地数据库。

        处理流程：
        1. 创建同步日志（状态: running）
        2. 拉取 ERP 产品列表
        3. 拉取 ERP 库存数据
        4. 逐条 upsert 产品
        5. 创建库存快照
        6. 更新同步日志（状态: success / failed）

        Args:
            operator_id: 操作人 ID（可选，用于审计）

        Returns:
            {"success": int, "failed": int, "total": int, "sync_log_id": int, "error": str | None}
        """
        log = await self._create_sync_log(sync_type="full", direction="pull")
        processed = 0
        failed = 0
        total = 0

        try:
            # 拉取产品数据
            products_data = await self.fetch_products()
            product_items = products_data.get("items", [])
            total += len(product_items)

            for item in product_items:
                try:
                    await self._upsert_product(item)
                    processed += 1
                except Exception as exc:
                    failed += 1
                    logger.error("全量同步 - 产品处理失败: %s", exc, exc_info=True)

            # 拉取库存数据
            inventory_data = await self.fetch_inventory()
            inventory_items = inventory_data.get("items", [])
            total += len(inventory_items)

            for item in inventory_items:
                try:
                    await self._sync_inventory_item(item)
                    processed += 1
                except Exception as exc:
                    failed += 1
                    logger.error("全量同步 - 库存处理失败: %s", exc, exc_info=True)

            # 更新同步日志
            status = "success" if failed == 0 else "partial_success"
            error_msg = None if failed == 0 else f"{failed} 条记录处理失败"
            await self._update_sync_log(
                log, status=status, processed=processed, failed=failed, error=error_msg,
            )

            logger.info(
                "全量同步完成: log_id=%d, processed=%d, failed=%d",
                log.id, processed, failed,
            )

            return {
                "success": processed - failed,
                "failed": failed,
                "total": total,
                "sync_log_id": log.id,
                "error": error_msg,
            }

        except Exception as exc:
            # 整体失败
            error_msg = f"全量同步异常: {exc}"
            logger.error(error_msg, exc_info=True)
            await self._update_sync_log(
                log, status="failed", processed=processed, failed=failed, error=error_msg,
            )
            return {
                "success": processed - failed,
                "failed": failed + (total - processed),
                "total": total,
                "sync_log_id": log.id,
                "error": error_msg,
            }

    # ==================== 增量同步 ====================

    async def incremental_sync(
        self,
        operator_id: int | None = None,
    ) -> dict:
        """
        执行增量同步：从 ERP 拉取上次同步后更新的数据。

        处理流程：
        1. 查询最近一次成功的同步日志，获取 finished_at 作为 updated_since
        2. 创建同步日志
        3. 拉取增量数据
        4. 逐条 upsert 产品 + 创建库存快照
        5. 更新同步日志

        Args:
            operator_id: 操作人 ID（可选）

        Returns:
            {"success": int, "failed": int, "total": int, "sync_log_id": int, "error": str | None}
        """
        # 查询上次同步时间
        updated_since: str | None = None
        stmt = (
            select(ErpSyncLog)
            .where(
                ErpSyncLog.direction == "pull",
                ErpSyncLog.status.in_(["success", "partial_success"]),
            )
            .order_by(desc(ErpSyncLog.finished_at))
            .limit(1)
        )
        result = await self.db.execute(stmt)
        last_log = result.scalar_one_or_none()

        if last_log and last_log.finished_at:
            updated_since = last_log.finished_at.strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.info("增量同步起始时间: %s", updated_since)

        log = await self._create_sync_log(sync_type="incremental", direction="pull")
        processed = 0
        failed = 0
        total = 0

        try:
            # 拉取增量库存数据
            inventory_data = await self.fetch_inventory(updated_since=updated_since)
            inventory_items = inventory_data.get("items", [])
            total = len(inventory_items)

            for item in inventory_items:
                try:
                    await self._sync_inventory_item(item)
                    processed += 1
                except Exception as exc:
                    failed += 1
                    logger.error("增量同步 - 库存处理失败: %s", exc, exc_info=True)

            # 同步更新产品信息
            products_data = await self.fetch_products()
            product_items = products_data.get("items", [])
            total += len(product_items)

            for item in product_items:
                try:
                    await self._upsert_product(item)
                    processed += 1
                except Exception as exc:
                    failed += 1
                    logger.error("增量同步 - 产品处理失败: %s", exc, exc_info=True)

            # 更新同步日志
            status = "success" if failed == 0 else "partial_success"
            error_msg = None if failed == 0 else f"{failed} 条记录处理失败"
            await self._update_sync_log(
                log, status=status, processed=processed, failed=failed, error=error_msg,
            )

            logger.info(
                "增量同步完成: log_id=%d, processed=%d, failed=%d",
                log.id, processed, failed,
            )

            return {
                "success": processed - failed,
                "failed": failed,
                "total": total,
                "sync_log_id": log.id,
                "error": error_msg,
            }

        except Exception as exc:
            error_msg = f"增量同步异常: {exc}"
            logger.error(error_msg, exc_info=True)
            await self._update_sync_log(
                log, status="failed", processed=processed, failed=failed, error=error_msg,
            )
            return {
                "success": processed - failed,
                "failed": failed + max(0, total - processed),
                "total": total,
                "sync_log_id": log.id,
                "error": error_msg,
            }

    # ==================== 库存项同步 ====================

    async def _sync_inventory_item(self, item: dict) -> None:
        """
        处理单条 ERP 库存数据。

        流程：
        1. 通过 ERP 数据中的产品信息 upsert 产品
        2. 查找仓库（默认使用第一个启用的仓库）
        3. 创建库存快照

        Args:
            item: ERP 返回的单条库存数据，预期包含：
                - erp_code / sku: 产品标识
                - quantity: 库存数量
                - warehouse_code: 仓库编码（可选）
                - unit_cost: 单位成本（可选）
        """
        # Upsert 产品
        product = await self._upsert_product(item)

        # 查找仓库
        warehouse_code = item.get("warehouse_code")
        warehouse_id = 1  # 默认仓库 ID

        if warehouse_code:
            from app.models.warehouse import Warehouse

            stmt = select(Warehouse).where(
                Warehouse.code == warehouse_code,
                Warehouse.is_active.is_(True),
            )
            result = await self.db.execute(stmt)
            warehouse = result.scalar_one_or_none()
            if warehouse:
                warehouse_id = warehouse.id

        # 解析数量和成本
        quantity = 0
        try:
            quantity = int(float(str(item.get("quantity", 0))))
        except (ValueError, TypeError):
            pass

        unit_cost = Decimal("0")
        try:
            unit_cost = Decimal(str(item.get("unit_cost", 0)))
        except (InvalidOperation, ValueError, TypeError):
            pass

        total_value = float(unit_cost * quantity)

        # 创建库存快照
        await inventory_crud.create_snapshot(
            self.db,
            obj_in={
                "product_id": product.id,
                "warehouse_id": warehouse_id,
                "quantity": quantity,
                "unit_cost": float(unit_cost),
                "total_value": total_value,
                "source": "erp",
            },
        )
