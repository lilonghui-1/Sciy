# -*- coding: utf-8 -*-
"""
Excel / CSV 解析工具

提供将 Excel 和 CSV 文件字节流解析为 pandas DataFrame 的能力，
并内置中英文列名映射与数据校验功能，服务于库存导入场景。
"""

import io
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ==================== 列名映射 ====================
# 系统内部字段名 -> 用户文件中可能出现的列名（中文/英文）
COLUMN_MAPPING: dict[str, list[str]] = {
    "sku": ["sku", "SKU", "编码", "商品编码", "货号"],
    "name": ["name", "名称", "商品名称", "品名"],
    "barcode": ["barcode", "条码", "条形码"],
    "category": ["category", "分类", "类别"],
    "quantity": ["quantity", "数量", "库存量", "现存量", "库存数量"],
    "warehouse": ["warehouse", "仓库", "仓库名称"],
    "unit_cost": ["unit_cost", "单价", "成本价", "采购价"],
    "unit": ["unit", "单位", "计量单位"],
}

# 反向映射：用户列名 -> 系统字段名（启动时自动构建）
_REVERSE_COLUMN_MAPPING: dict[str, str] = {}
for _sys_field, _aliases in COLUMN_MAPPING.items():
    for _alias in _aliases:
        _REVERSE_COLUMN_MAPPING[_alias] = _sys_field


# ==================== 解析函数 ====================


def parse_excel(file_bytes: bytes, sheet_name: str | int = 0) -> pd.DataFrame:
    """
    将 Excel 文件字节流解析为 DataFrame。

    支持 .xlsx 和 .xls 格式。如果文件为空或无法解析则抛出 ValueError。

    Args:
        file_bytes: Excel 文件的原始字节
        sheet_name: 工作表名称或索引，默认为第一个工作表

    Returns:
        解析后的 DataFrame

    Raises:
        ValueError: 文件为空或解析失败
    """
    if not file_bytes:
        raise ValueError("文件内容为空，无法解析")

    try:
        bio = io.BytesIO(file_bytes)
        # engine="openpyxl" 处理 .xlsx，xlrd 处理 .xls
        df = pd.read_excel(bio, sheet_name=sheet_name, dtype=str, na_values=["", " ", "NULL", "null", "None"])
    except Exception as exc:
        logger.error("Excel 文件解析失败: %s", exc)
        raise ValueError(f"Excel 文件解析失败: {exc}") from exc

    if df.empty:
        raise ValueError("Excel 文件中没有数据行")

    # 去除列名首尾空白
    df.columns = [str(col).strip() for col in df.columns]

    logger.info("Excel 解析完成，共 %d 行 %d 列", len(df), len(df.columns))
    return df


def parse_csv(file_bytes: bytes, encoding: str = "utf-8") -> pd.DataFrame:
    """
    将 CSV 文件字节流解析为 DataFrame。

    优先使用指定编码，若遇到 UnicodeDecodeError 则自动回退到 gbk 编码。

    Args:
        file_bytes: CSV 文件的原始字节
        encoding: 首选字符编码，默认 utf-8

    Returns:
        解析后的 DataFrame

    Raises:
        ValueError: 文件为空或解析失败
    """
    if not file_bytes:
        raise ValueError("文件内容为空，无法解析")

    # 尝试首选编码，失败后回退到 gbk
    for enc in (encoding, "gbk", "gb18030", "latin-1"):
        try:
            text = file_bytes.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        raise ValueError("无法识别文件编码，请确认文件格式")

    try:
        df = pd.read_csv(
            io.StringIO(text),
            dtype=str,
            skipinitialspace=True,
            na_values=["", " ", "NULL", "null", "None"],
        )
    except Exception as exc:
        logger.error("CSV 文件解析失败: %s", exc)
        raise ValueError(f"CSV 文件解析失败: {exc}") from exc

    if df.empty:
        raise ValueError("CSV 文件中没有数据行")

    # 去除列名首尾空白
    df.columns = [str(col).strip() for col in df.columns]

    logger.info("CSV 解析完成，共 %d 行 %d 列", len(df), len(df.columns))
    return df


# ==================== 列名校验 ====================


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: list[str],
) -> tuple[bool, list[str]]:
    """
    校验 DataFrame 是否包含所有必需的系统字段列。

    注意：此函数假设 DataFrame 的列名已经过 map_columns 转换，
    即列名为系统字段名（如 "sku", "name" 等）。

    Args:
        df: 待校验的 DataFrame
        required_columns: 必需的系统字段名列表

    Returns:
        (is_valid, missing_columns) 元组
        - is_valid: 是否所有必需列都存在
        - missing_columns: 缺失的列名列表
    """
    existing = set(df.columns.tolist())
    missing = [col for col in required_columns if col not in existing]
    is_valid = len(missing) == 0
    return is_valid, missing


# ==================== 列名映射 ====================


def map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    将用户文件中的列名映射为系统内部字段名。

    映射规则基于 COLUMN_MAPPING 中定义的别名。无法识别的列名保持原样。

    Args:
        df: 原始 DataFrame（列名为用户自定义）

    Returns:
        列名映射后的 DataFrame
    """
    new_columns: list[str] = []
    for col in df.columns:
        col_stripped = str(col).strip()
        mapped = _REVERSE_COLUMN_MAPPING.get(col_stripped, col_stripped)
        new_columns.append(mapped)

    df = df.copy()
    df.columns = new_columns

    # 记录映射情况
    mapped_count = sum(1 for orig, new in zip(df.columns, new_columns) if orig != new)
    if mapped_count > 0:
        logger.info("列名映射完成，共映射 %d 列", mapped_count)

    return df
