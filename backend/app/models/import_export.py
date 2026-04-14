# -*- coding: utf-8 -*-
"""
数据导入导出模型

定义导入导出任务的数据结构。
"""

from sqlalchemy import String, Integer, Text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ImportExportJob(Base, TimestampMixin):
    """导入导出任务模型"""

    __tablename__ = "import_export_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="任务类型: import/export",
    )
    data_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="数据类型: products/inventory/suppliers",
    )
    file_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="文件名",
    )
    file_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="文件路径",
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, comment="文件大小(字节)",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", comment="状态: pending/processing/success/failed",
    )
    total_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="总行数",
    )
    processed_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="已处理行数",
    )
    success_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="成功行数",
    )
    error_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="失败行数",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="错误信息",
    )
    triggered_by: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="触发人ID",
    )
