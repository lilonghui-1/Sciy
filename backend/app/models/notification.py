# -*- coding: utf-8 -*-
"""
通知偏好模型

定义用户通知偏好设置的数据结构。
"""

from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class NotificationPreference(Base, TimestampMixin):
    """通知偏好设置模型"""

    __tablename__ = "notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, unique=True, comment="用户ID",
    )
    notify_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="邮件通知",
    )
    notify_sms: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="短信通知",
    )
    notify_in_app: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="站内通知",
    )
    notify_webhook: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Webhook通知",
    )
    low_stock_alert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="低库存预警",
    )
    over_stock_alert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="超库存预警",
    )
    forecast_alert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="预测预警",
    )
    daily_summary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="每日汇总",
    )

    # 关系
    user = relationship("User", back_populates="notification_preferences")
