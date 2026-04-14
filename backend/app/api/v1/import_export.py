# -*- coding: utf-8 -*-
"""
数据导入导出路由

处理 Excel/CSV 文件上传和导入模板信息。
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.core.exceptions import BadRequestException, FileUploadException
from app.models.user import User
from app.schemas.import_export import ImportTemplateInfo
from app.services.import_service import ImportService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import-export", tags=["数据导入导出"])

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


def _get_file_extension(filename: str) -> str:
    """从文件名中提取扩展名（小写，含点号）。"""
    if "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return ""


@router.post("/upload", summary="上传导入文件")
async def upload_file(
    file: UploadFile = File(..., description="上传的 Excel/CSV 文件"),
    data_type: str = Query(
        default="inventory",
        description="数据类型: inventory/products/suppliers",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    上传 Excel/CSV 文件进行数据导入

    支持的文件格式: .xlsx, .xls, .csv
    支持的数据类型: inventory（库存导入）, products（产品导入）, suppliers（供应商导入）

    返回导入结果，包含成功/失败行数及错误详情。
    """
    # ---- 验证文件名 ----
    if not file.filename or not file.filename.strip():
        raise BadRequestException(detail="请选择要上传的文件")

    # ---- 验证文件类型 ----
    file_ext = _get_file_extension(file.filename)
    if file_ext not in ALLOWED_EXTENSIONS:
        raise FileUploadException(
            detail=f"不支持的文件格式: {file_ext}，仅支持 {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            status_code=415,
        )

    # ---- 验证数据类型 ----
    valid_data_types = {"inventory", "products", "suppliers"}
    if data_type not in valid_data_types:
        raise BadRequestException(
            detail=f"无效的数据类型: {data_type}，有效值为: {', '.join(sorted(valid_data_types))}",
        )

    # ---- 读取文件内容 ----
    content = await file.read()
    file_size = len(content)

    if file_size == 0:
        raise BadRequestException(detail="上传的文件为空，请检查文件内容")

    logger.info(
        "开始处理导入文件: 文件名=%s, 大小=%d字节, 数据类型=%s, 用户ID=%s",
        file.filename,
        file_size,
        data_type,
        getattr(current_user, "id", "unknown"),
    )

    # ---- 调用 ImportService 执行导入 ----
    import_service = ImportService(db)
    operator_id = getattr(current_user, "id", None)

    try:
        if data_type == "inventory":
            result = await import_service.import_inventory(
                file_bytes=content,
                filename=file.filename,
                operator_id=operator_id,
            )
        elif data_type == "products":
            result = await import_service.import_products(
                file_bytes=content,
                filename=file.filename,
            )
        elif data_type == "suppliers":
            # suppliers 暂无专用导入方法，使用通用库存导入逻辑
            result = await import_service.import_inventory(
                file_bytes=content,
                filename=file.filename,
                operator_id=operator_id,
            )
        else:
            raise BadRequestException(
                detail=f"暂不支持的数据类型: {data_type}",
            )
    except Exception as exc:
        logger.exception("导入文件处理异常: %s", exc)
        raise BadRequestException(
            detail=f"文件解析或导入失败: {exc}",
        ) from exc

    # ---- 构建响应 ----
    success = result.get("success", 0)
    failed = result.get("failed", 0)
    errors = result.get("errors", [])
    total = result.get("total", 0)

    logger.info(
        "文件导入完成: 文件名=%s, 总计=%d, 成功=%d, 失败=%d",
        file.filename,
        total,
        success,
        failed,
    )

    return {
        "message": (
            f"文件 '{file.filename}' 导入完成: "
            f"总计 {total} 行, 成功 {success} 行, 失败 {failed} 行"
        ),
        "success": failed == 0,
        "data_type": data_type,
        "total": total,
        "success_count": success,
        "failed_count": failed,
        "errors": errors,
    }


@router.get("/templates", response_model=list[ImportTemplateInfo], summary="获取导入模板信息")
async def get_import_templates(
    current_user: User = Depends(get_current_active_user),
) -> list[ImportTemplateInfo]:
    """
    获取各类数据导入的模板信息

    返回每种数据类型的导入模板说明，包括必填列和可选列。
    模板信息来源于 ImportService.get_import_template_info()。
    """
    template_info = ImportService.get_import_template_info()

    # 从 ImportService 获取库存导入模板的列信息
    required_columns = [
        col["field"]
        for col in template_info.get("required_columns", [])
    ]
    optional_columns = [
        col["field"]
        for col in template_info.get("optional_columns", [])
    ]

    templates: list[ImportTemplateInfo] = [
        ImportTemplateInfo(
            data_type="inventory",
            template_name="库存导入模板",
            description=template_info.get("description", "库存导入模板说明"),
            required_columns=required_columns,
            optional_columns=optional_columns,
            download_url="/api/v1/import-export/templates/inventory",
        ),
        ImportTemplateInfo(
            data_type="products",
            template_name="产品导入模板",
            description="用于批量导入产品信息，包含产品名称、SKU、价格等字段",
            required_columns=["sku", "name"],
            optional_columns=[
                "barcode", "category", "unit", "unit_cost",
                "quantity", "warehouse",
            ],
            download_url="/api/v1/import-export/templates/products",
        ),
        ImportTemplateInfo(
            data_type="suppliers",
            template_name="供应商导入模板",
            description="用于批量导入供应商信息，包含名称、编码、联系方式等字段",
            required_columns=["name", "code"],
            optional_columns=[
                "contact_person", "phone", "email", "address",
                "website", "bank_name", "bank_account", "tax_number",
                "rating", "notes",
            ],
            download_url="/api/v1/import-export/templates/suppliers",
        ),
    ]

    return templates
