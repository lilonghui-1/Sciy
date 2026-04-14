# -*- coding: utf-8 -*-
"""
数据导入服务

提供 Excel / CSV 文件中库存数据和产品主数据的批量导入能力。
支持中英文列名自动映射、数据校验、产品自动创建/更新以及库存快照与事务记录。
"""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.inventory import inventory_crud
from app.crud.product import product_crud
from app.models.inventory_snapshot import InventorySnapshot
from app.models.inventory_transaction import InventoryTransaction
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.utils.excel_parser import (
    COLUMN_MAPPING,
    map_columns,
    parse_csv,
    parse_excel,
    validate_dataframe,
)

logger = logging.getLogger(__name__)


class ImportService:
    """
    数据导入服务

    将用户上传的 Excel / CSV 文件解析、映射、校验后写入数据库。
    支持两种导入模式：
    - 库存导入：导入库存数据，自动创建/更新产品，生成快照和入库事务
    - 产品导入：仅导入产品主数据
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化导入服务。

        Args:
            db: 异步数据库会话
        """
        self.db = db

    # ==================== 列名映射 ====================

    @staticmethod
    def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
        """
        将用户文件列名映射为系统字段名。

        Args:
            df: 原始 DataFrame

        Returns:
            映射后的 DataFrame
        """
        return map_columns(df)

    # ==================== 文件解析 ====================

    @staticmethod
    def _parse_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
        """
        根据文件扩展名自动选择解析方式。

        Args:
            file_bytes: 文件原始字节
            filename: 文件名（用于判断扩展名）

        Returns:
            解析后的 DataFrame

        Raises:
            ValueError: 不支持的文件格式或解析失败
        """
        ext = filename.rsplit(".", maxsplit=1)[-1].lower() if "." in filename else ""

        if ext in ("xlsx", "xls"):
            return parse_excel(file_bytes)
        elif ext == "csv":
            return parse_csv(file_bytes)
        else:
            raise ValueError(
                f"不支持的文件格式 '.{ext}'，"
                f"请上传 .xlsx / .xls / .csv 格式的文件"
            )

    # ==================== 数据清洗辅助 ====================

    @staticmethod
    def _to_int(value, default: int = 0) -> int:
        """安全地将值转换为整数。"""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _to_decimal(value, default: str = "0") -> Decimal:
        """安全地将值转换为 Decimal。"""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return Decimal(default)
        try:
            return Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError):
            return Decimal(default)

    @staticmethod
    def _to_str(value, default: str = "") -> str:
        """安全地将值转换为非空字符串。"""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        s = str(value).strip()
        return s if s else default

    # ==================== 仓库查找 ====================

    async def _get_or_default_warehouse(
        self,
        warehouse_name: str | None,
    ) -> Warehouse | None:
        """
        根据仓库名称查找仓库，找不到则返回默认仓库（第一个启用的仓库）。

        Args:
            warehouse_name: 仓库名称

        Returns:
            仓库实例，找不到返回 None
        """
        if warehouse_name:
            stmt = select(Warehouse).where(
                Warehouse.name == warehouse_name,
                Warehouse.is_active.is_(True),
            )
            result = await self.db.execute(stmt)
            warehouse = result.scalar_one_or_none()
            if warehouse:
                return warehouse

        # 回退：返回第一个启用的仓库
        stmt = select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(Warehouse.id).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ==================== 库存导入 ====================

    async def import_inventory(
        self,
        file_bytes: bytes,
        filename: str,
        operator_id: int | None = None,
    ) -> dict:
        """
        导入库存数据（主入口方法）。

        处理流程：
        1. 解析文件（Excel 或 CSV）
        2. 映射列名
        3. 校验必需列（至少包含 sku）
        4. 逐行处理：查找或创建产品 -> 创建库存快照 -> 创建入库事务

        Args:
            file_bytes: 文件原始字节
            filename: 文件名
            operator_id: 操作人 ID（可选）

        Returns:
            {"success": int, "failed": int, "errors": list[str], "total": int}
        """
        # 1. 解析文件
        try:
            df = self._parse_file(file_bytes, filename)
        except ValueError as exc:
            return {
                "success": 0,
                "failed": 0,
                "errors": [str(exc)],
                "total": 0,
            }

        # 2. 映射列名
        df = self._map_columns(df)

        # 3. 校验必需列
        is_valid, missing = validate_dataframe(df, required_columns=["sku"])
        if not is_valid:
            return {
                "success": 0,
                "failed": 0,
                "errors": [f"缺少必需列: {', '.join(missing)}"],
                "total": len(df),
            }

        # 4. 逐行处理
        success_count = 0
        failed_count = 0
        errors: list[str] = []

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel/CSV 行号从 1 开始，加上表头行
            try:
                await self._import_inventory_row(row, row_num, operator_id)
                success_count += 1
            except Exception as exc:
                failed_count += 1
                error_msg = f"第 {row_num} 行: {exc}"
                errors.append(error_msg)
                logger.warning("库存导入行处理失败 - %s", error_msg)

        total = len(df)
        logger.info(
            "库存导入完成: 总计 %d 行, 成功 %d, 失败 %d",
            total, success_count, failed_count,
        )

        return {
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
            "total": total,
        }

    async def _import_inventory_row(
        self,
        row: pd.Series,
        row_num: int,
        operator_id: int | None,
    ) -> None:
        """
        处理单行库存数据。

        Args:
            row: DataFrame 的一行数据
            row_num: 行号（用于错误信息）
            operator_id: 操作人 ID
        """
        sku = self._to_str(row.get("sku"))
        if not sku:
            raise ValueError("SKU 为空")

        quantity = self._to_int(row.get("quantity"))
        unit_cost = self._to_decimal(row.get("unit_cost"))
        warehouse_name = self._to_str(row.get("warehouse"), default=None) or None

        # 查找或创建产品
        product = await product_crud.get_by_sku(db=self.db, sku=sku)

        if product is None:
            # 创建新产品
            name = self._to_str(row.get("name"), default=sku)
            barcode = self._to_str(row.get("barcode"), default=None) or None
            category = self._to_str(row.get("category"), default=None) or None
            unit = self._to_str(row.get("unit"), default="个")

            product = await product_crud.create(
                self.db,
                obj_in={
                    "sku": sku,
                    "name": name,
                    "barcode": barcode,
                    "category": category,
                    "unit": unit,
                    "unit_cost": float(unit_cost),
                    "selling_price": float(unit_cost),  # 默认售价等于成本价
                    "supplier_id": 1,  # 默认供应商 ID，需根据实际业务调整
                    "is_active": True,
                },
            )
            logger.info("导入创建新产品: id=%d, sku='%s'", product.id, product.sku)
        else:
            # 更新产品信息（如果文件中提供了新数据）
            update_data: dict = {}
            name = self._to_str(row.get("name"))
            if name:
                update_data["name"] = name
            barcode = self._to_str(row.get("barcode"), default=None) or None
            if barcode is not None:
                update_data["barcode"] = barcode
            category = self._to_str(row.get("category"), default=None) or None
            if category is not None:
                update_data["category"] = category
            unit = self._to_str(row.get("unit"))
            if unit:
                update_data["unit"] = unit
            if update_data:
                await product_crud.update(self.db, id=product.id, obj_in=update_data)

        # 查找仓库
        warehouse = await self._get_or_default_warehouse(warehouse_name)
        if warehouse is None:
            raise ValueError(f"未找到仓库 '{warehouse_name}'，且系统中没有可用的默认仓库")

        # 获取当前库存
        latest_snapshot = await inventory_crud.get_latest_snapshot(
            self.db,
            product_id=product.id,
            warehouse_id=warehouse.id,
        )
        previous_quantity = latest_snapshot.quantity if latest_snapshot else 0

        # 创建库存快照
        total_value = float(unit_cost * quantity)
        await inventory_crud.create_snapshot(
            self.db,
            obj_in={
                "product_id": product.id,
                "warehouse_id": warehouse.id,
                "quantity": quantity,
                "unit_cost": float(unit_cost),
                "total_value": total_value,
                "source": "import",
            },
        )

        # 创建入库事务（仅当数量有变化时）
        if quantity != previous_quantity:
            quantity_change = quantity - previous_quantity
            await inventory_crud.create_transaction(
                self.db,
                obj_in={
                    "product_id": product.id,
                    "warehouse_id": warehouse.id,
                    "transaction_type": "inbound",
                    "quantity": abs(quantity_change),
                    "previous_quantity": previous_quantity,
                    "new_quantity": quantity,
                    "reference_no": f"IMPORT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    "operator_id": operator_id,
                    "notes": f"文件导入: {sku}",
                },
            )

    # ==================== 产品导入 ====================

    async def import_products(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> dict:
        """
        导入产品主数据。

        处理流程：
        1. 解析文件
        2. 映射列名
        3. 校验必需列（sku 和 name）
        4. 逐行处理：查找或创建产品

        Args:
            file_bytes: 文件原始字节
            filename: 文件名

        Returns:
            {"success": int, "failed": int, "errors": list[str], "total": int}
        """
        # 1. 解析文件
        try:
            df = self._parse_file(file_bytes, filename)
        except ValueError as exc:
            return {
                "success": 0,
                "failed": 0,
                "errors": [str(exc)],
                "total": 0,
            }

        # 2. 映射列名
        df = self._map_columns(df)

        # 3. 校验必需列
        is_valid, missing = validate_dataframe(df, required_columns=["sku", "name"])
        if not is_valid:
            return {
                "success": 0,
                "failed": 0,
                "errors": [f"缺少必需列: {', '.join(missing)}"],
                "total": len(df),
            }

        # 4. 逐行处理
        success_count = 0
        failed_count = 0
        errors: list[str] = []

        for idx, row in df.iterrows():
            row_num = idx + 2
            try:
                await self._import_product_row(row, row_num)
                success_count += 1
            except Exception as exc:
                failed_count += 1
                error_msg = f"第 {row_num} 行: {exc}"
                errors.append(error_msg)
                logger.warning("产品导入行处理失败 - %s", error_msg)

        total = len(df)
        logger.info(
            "产品导入完成: 总计 %d 行, 成功 %d, 失败 %d",
            total, success_count, failed_count,
        )

        return {
            "success": success_count,
            "failed": failed_count,
            "errors": errors,
            "total": total,
        }

    async def _import_product_row(
        self,
        row: pd.Series,
        row_num: int,
    ) -> None:
        """
        处理单行产品数据。

        Args:
            row: DataFrame 的一行数据
            row_num: 行号
        """
        sku = self._to_str(row.get("sku"))
        if not sku:
            raise ValueError("SKU 为空")

        name = self._to_str(row.get("name"))
        if not name:
            raise ValueError("产品名称为空")

        # 查找已有产品
        product = await product_crud.get_by_sku(db=self.db, sku=sku)

        if product is not None:
            # 更新已有产品信息
            update_data: dict = {"name": name}

            barcode = self._to_str(row.get("barcode"), default=None) or None
            if barcode is not None:
                update_data["barcode"] = barcode

            category = self._to_str(row.get("category"), default=None) or None
            if category is not None:
                update_data["category"] = category

            unit = self._to_str(row.get("unit"))
            if unit:
                update_data["unit"] = unit

            unit_cost = self._to_decimal(row.get("unit_cost"))
            if unit_cost > 0:
                update_data["unit_cost"] = float(unit_cost)

            await product_crud.update(self.db, id=product.id, obj_in=update_data)
            logger.info("导入更新产品: id=%d, sku='%s'", product.id, product.sku)
        else:
            # 创建新产品
            barcode = self._to_str(row.get("barcode"), default=None) or None
            category = self._to_str(row.get("category"), default=None) or None
            unit = self._to_str(row.get("unit"), default="个")
            unit_cost = self._to_decimal(row.get("unit_cost"))

            await product_crud.create(
                self.db,
                obj_in={
                    "sku": sku,
                    "name": name,
                    "barcode": barcode,
                    "category": category,
                    "unit": unit,
                    "unit_cost": float(unit_cost) if unit_cost > 0 else 0.0,
                    "selling_price": float(unit_cost) if unit_cost > 0 else 0.0,
                    "supplier_id": 1,
                    "is_active": True,
                },
            )
            logger.info("导入创建新产品: sku='%s'", sku)

    # ==================== 模板信息 ====================

    @staticmethod
    def get_import_template_info() -> dict:
        """
        返回导入模板的列说明信息，供前端展示或生成模板文件。

        Returns:
            包含模板描述的字典
        """
        return {
            "description": "库存导入模板说明",
            "required_columns": [
                {
                    "field": "sku",
                    "aliases": COLUMN_MAPPING["sku"],
                    "description": "SKU 编码（必填）",
                    "example": "SKU-001",
                },
            ],
            "optional_columns": [
                {
                    "field": "name",
                    "aliases": COLUMN_MAPPING["name"],
                    "description": "产品名称",
                    "example": "无线蓝牙耳机",
                },
                {
                    "field": "barcode",
                    "aliases": COLUMN_MAPPING["barcode"],
                    "description": "条形码",
                    "example": "6901234567890",
                },
                {
                    "field": "category",
                    "aliases": COLUMN_MAPPING["category"],
                    "description": "产品分类",
                    "example": "电子产品",
                },
                {
                    "field": "quantity",
                    "aliases": COLUMN_MAPPING["quantity"],
                    "description": "库存数量",
                    "example": "100",
                },
                {
                    "field": "warehouse",
                    "aliases": COLUMN_MAPPING["warehouse"],
                    "description": "仓库名称",
                    "example": "主仓库",
                },
                {
                    "field": "unit_cost",
                    "aliases": COLUMN_MAPPING["unit_cost"],
                    "description": "单位成本",
                    "example": "29.90",
                },
                {
                    "field": "unit",
                    "aliases": COLUMN_MAPPING["unit"],
                    "description": "计量单位",
                    "example": "个",
                },
            ],
            "supported_formats": [".xlsx", ".xls", ".csv"],
            "encoding_hint": "CSV 文件建议使用 UTF-8 编码，如遇乱码可尝试 GBK 编码",
        }
