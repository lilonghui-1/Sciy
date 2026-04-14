# -*- coding: utf-8 -*-
"""
多渠道通知服务

提供统一的通知发送接口，支持以下通知渠道：
- in_app: 站内推送（通过 WebSocket 实时推送）
- email: 邮件通知（通过 aiosmtplib 发送）
- sms: 短信通知（通过 Twilio REST API 发送）
- webhook: Webhook 回调（通过 httpx POST 发送，带 HMAC-SHA256 签名）

每次通知发送均记录到 notification_logs 表，便于追踪和排查。
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.alert_event import AlertEvent
from app.models.alert_rule import AlertRule
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.utils.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# 严重程度中文映射
SEVERITY_MAP = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "critical": "严重",
}


class NotificationService:
    """
    多渠道通知服务

    根据告警规则中配置的通知渠道，将告警事件通过对应渠道发送给指定接收人。
    支持渠道：in_app（站内推送）、email（邮件）、sms（短信）、webhook（回调）。
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化通知服务。

        Args:
            db: 异步数据库会话
        """
        self.db = db
        self.settings = get_settings()

    async def send_alert(self, event: AlertEvent) -> dict:
        """
        发送告警通知的主入口方法。

        根据告警事件关联的规则配置，依次通过各通知渠道发送通知。
        每个渠道的发送结果独立记录，单个渠道失败不影响其他渠道。

        Args:
            event: 告警事件对象

        Returns:
            各渠道发送结果汇总字典
        """
        logger.info(
            "开始发送告警通知: event_id=%d, rule_id=%d, title='%s'",
            event.id,
            event.rule_id,
            event.title,
        )

        # 查询关联的告警规则
        rule = await self._get_rule(event.rule_id)
        if rule is None:
            logger.error(
                "告警规则不存在，无法发送通知: rule_id=%d, event_id=%d",
                event.rule_id,
                event.id,
            )
            await self._log_notification(
                alert_event_id=event.id,
                channel="system",
                status="failed",
                recipient="",
                error=f"告警规则不存在: rule_id={event.rule_id}",
            )
            return {"status": "error", "error": "rule_not_found"}

        if not rule.is_active:
            logger.warning(
                "告警规则已禁用，跳过通知: rule_id=%d, event_id=%d",
                rule.id,
                event.id,
            )
            return {"status": "skipped", "reason": "rule_disabled"}

        # 获取通知渠道列表
        channels = rule.notify_channels if isinstance(rule.notify_channels, list) else []
        if not channels:
            logger.warning(
                "告警规则未配置通知渠道，跳过通知: rule_id=%d", rule.id
            )
            return {"status": "skipped", "reason": "no_channels"}

        # 获取通知接收人ID列表
        recipient_ids = (
            rule.notify_recipients
            if isinstance(rule.notify_recipients, list)
            else []
        )

        results = {}
        channel_handlers = {
            "in_app": self._send_in_app,
            "email": self._send_email,
            "sms": self._send_sms,
            "webhook": self._send_webhook,
        }

        for channel in channels:
            handler = channel_handlers.get(channel)
            if handler is None:
                logger.warning("未知的通知渠道，跳过: channel=%s", channel)
                results[channel] = {
                    "status": "skipped",
                    "error": f"unknown_channel: {channel}",
                }
                continue

            try:
                result = await handler(event, rule)
                results[channel] = result
            except Exception as e:
                logger.error(
                    "通知渠道发送异常: channel=%s, event_id=%d, 错误=%s",
                    channel,
                    event.id,
                    str(e),
                    exc_info=True,
                )
                results[channel] = {"status": "failed", "error": str(e)}
                await self._log_notification(
                    alert_event_id=event.id,
                    channel=channel,
                    status="failed",
                    recipient="",
                    error=str(e),
                )

        logger.info(
            "告警通知发送完成: event_id=%d, 结果=%s",
            event.id,
            json.dumps(results, ensure_ascii=False, default=str),
        )
        return {"status": "completed", "event_id": event.id, "results": results}

    async def _get_rule(self, rule_id: int) -> Optional[AlertRule]:
        """
        根据ID查询告警规则。

        Args:
            rule_id: 规则ID

        Returns:
            告警规则对象，不存在时返回 None
        """
        stmt = select(AlertRule).where(AlertRule.id == rule_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_users_by_ids(
        self, user_ids: list[int]
    ) -> list[User]:
        """
        根据用户ID列表批量查询用户信息。

        Args:
            user_ids: 用户ID列表

        Returns:
            用户对象列表
        """
        if not user_ids:
            return []
        stmt = select(User).where(User.id.in_(user_ids), User.is_active == True)  # noqa: E712
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ==================== 站内推送 ====================

    async def _send_in_app(
        self, event: AlertEvent, rule: AlertRule
    ) -> dict:
        """
        通过 WebSocket 向指定用户推送站内告警通知。

        Args:
            event: 告警事件
            rule: 告警规则

        Returns:
            发送结果字典
        """
        recipient_ids = (
            rule.notify_recipients
            if isinstance(rule.notify_recipients, list)
            else []
        )
        if not recipient_ids:
            logger.warning("站内推送无接收人，跳过: event_id=%d", event.id)
            return {"status": "skipped", "error": "no_recipients"}

        alert_data = {
            "type": "alert",
            "event_id": event.id,
            "rule_id": rule.id,
            "severity": event.severity,
            "title": event.title,
            "message": event.message,
            "current_value": event.current_value,
            "threshold_value": event.threshold_value,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }

        result = await ws_manager.send_alert(recipient_ids, alert_data)

        # 记录通知日志
        for user_id in result.get("sent", []):
            await self._log_notification(
                alert_event_id=event.id,
                channel="in_app",
                status="sent",
                recipient=str(user_id),
            )
        for user_id in result.get("failed", []):
            await self._log_notification(
                alert_event_id=event.id,
                channel="in_app",
                status="failed",
                recipient=str(user_id),
                error="用户不在线或发送失败",
            )

        return {
            "status": "completed",
            "sent_count": len(result.get("sent", [])),
            "failed_count": len(result.get("failed", [])),
        }

    # ==================== 邮件通知 ====================

    async def _send_email(
        self, event: AlertEvent, rule: AlertRule
    ) -> dict:
        """
        通过 SMTP 发送邮件通知。

        使用 aiosmtplib 异步发送邮件，支持 TLS 加密。
        邮件主题格式: [库存告警] {severity} - {title}

        Args:
            event: 告警事件
            rule: 告警规则

        Returns:
            发送结果字典
        """
        recipient_ids = (
            rule.notify_recipients
            if isinstance(rule.notify_recipients, list)
            else []
        )
        if not recipient_ids:
            logger.warning("邮件通知无接收人，跳过: event_id=%d", event.id)
            return {"status": "skipped", "error": "no_recipients"}

        # 检查 SMTP 配置
        if not self.settings.smtp_username or not self.settings.smtp_password:
            logger.error("SMTP 配置不完整（缺少用户名或密码），无法发送邮件")
            await self._log_notification(
                alert_event_id=event.id,
                channel="email",
                status="failed",
                recipient="",
                error="SMTP 配置不完整",
            )
            return {"status": "failed", "error": "smtp_not_configured"}

        # 查询接收人邮箱
        users = await self._get_users_by_ids(recipient_ids)
        if not users:
            logger.warning("邮件接收人不存在或未激活: event_id=%d", event.id)
            return {"status": "skipped", "error": "no_valid_recipients"}

        recipient_emails = [u.email for u in users if u.email]
        if not recipient_emails:
            logger.warning("接收人无有效邮箱地址: event_id=%d", event.id)
            return {"status": "skipped", "error": "no_valid_emails"}

        # 构建邮件
        severity_cn = SEVERITY_MAP.get(event.severity, event.severity)
        subject = f"[库存告警] {severity_cn} - {event.title}"

        # 构建邮件正文（纯文本 + HTML）
        text_body = self._build_email_text_body(event, rule)
        html_body = self._build_email_html_body(event, rule)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
        msg["To"] = ", ".join(recipient_emails)
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")

        # 发送邮件
        sent_count = 0
        failed_count = 0

        try:
            import aiosmtplib

            await aiosmtplib.send(
                msg,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_username,
                password=self.settings.smtp_password,
                start_tls=self.settings.smtp_use_tls,
                timeout=30,
            )
            sent_count = len(recipient_emails)
            logger.info(
                "邮件发送成功: event_id=%d, 收件人数=%d",
                event.id,
                sent_count,
            )
        except ImportError:
            logger.error("aiosmtplib 未安装，无法发送邮件")
            await self._log_notification(
                alert_event_id=event.id,
                channel="email",
                status="failed",
                recipient=", ".join(recipient_emails),
                error="aiosmtplib 未安装",
            )
            return {"status": "failed", "error": "aiosmtplib_not_installed"}
        except Exception as e:
            logger.error(
                "邮件发送失败: event_id=%d, 错误=%s",
                event.id,
                str(e),
                exc_info=True,
            )
            failed_count = len(recipient_emails)
            await self._log_notification(
                alert_event_id=event.id,
                channel="email",
                status="failed",
                recipient=", ".join(recipient_emails),
                error=str(e),
            )
            return {"status": "failed", "error": str(e)}

        # 记录成功日志
        for email in recipient_emails:
            await self._log_notification(
                alert_event_id=event.id,
                channel="email",
                status="sent",
                recipient=email,
                subject=subject,
            )

        return {
            "status": "completed",
            "sent_count": sent_count,
            "failed_count": failed_count,
        }

    def _build_email_text_body(
        self, event: AlertEvent, rule: AlertRule
    ) -> str:
        """构建纯文本邮件正文。"""
        severity_cn = SEVERITY_MAP.get(event.severity, event.severity)
        lines = [
            f"库存告警通知",
            f"{'=' * 40}",
            f"",
            f"告警级别: {severity_cn}",
            f"规则名称: {rule.name}",
            f"告警标题: {event.title}",
            f"告警详情: {event.message}",
            f"",
        ]
        if event.current_value is not None:
            lines.append(f"当前值: {event.current_value}")
        if event.threshold_value is not None:
            lines.append(f"阈值: {event.threshold_value}")
        lines.extend([
            f"",
            f"事件时间: {event.created_at.strftime('%Y-%m-%d %H:%M:%S') if event.created_at else 'N/A'}",
            f"",
            f"请及时登录系统查看并处理。",
            f"{'=' * 40}",
            f"此邮件由库存管理系统自动发送，请勿直接回复。",
        ])
        return "\n".join(lines)

    def _build_email_html_body(
        self, event: AlertEvent, rule: AlertRule
    ) -> str:
        """构建 HTML 邮件正文。"""
        severity_cn = SEVERITY_MAP.get(event.severity, event.severity)
        severity_colors = {
            "low": "#36a2eb",
            "medium": "#ff9f40",
            "high": "#ff6384",
            "critical": "#ff0000",
        }
        color = severity_colors.get(event.severity, "#333333")

        value_section = ""
        if event.current_value is not None or event.threshold_value is not None:
            value_section = "<tr>"
            if event.current_value is not None:
                value_section += f"<td style='padding:8px;border:1px solid #ddd;'>当前值</td><td style='padding:8px;border:1px solid #ddd;'>{event.current_value}</td>"
            if event.threshold_value is not None:
                value_section += f"<td style='padding:8px;border:1px solid #ddd;'>阈值</td><td style='padding:8px;border:1px solid #ddd;'>{event.threshold_value}</td>"
            value_section += "</tr>"

        created_at_str = (
            event.created_at.strftime("%Y-%m-%d %H:%M:%S")
            if event.created_at
            else "N/A"
        )

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
  <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
    <div style="background-color: {color}; color: #ffffff; padding: 20px;">
      <h2 style="margin: 0;">库存告警通知</h2>
    </div>
    <div style="padding: 20px;">
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold;width:120px;">告警级别</td>
          <td style="padding:8px;border:1px solid #ddd;color:{color};font-weight:bold;">{severity_cn}</td>
        </tr>
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold;">规则名称</td>
          <td style="padding:8px;border:1px solid #ddd;">{rule.name}</td>
        </tr>
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold;">告警标题</td>
          <td style="padding:8px;border:1px solid #ddd;">{event.title}</td>
        </tr>
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold;">告警详情</td>
          <td style="padding:8px;border:1px solid #ddd;">{event.message}</td>
        </tr>
        {value_section}
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold;">事件时间</td>
          <td style="padding:8px;border:1px solid #ddd;">{created_at_str}</td>
        </tr>
      </table>
      <p style="margin-top: 20px; color: #666;">请及时登录系统查看并处理。</p>
    </div>
    <div style="background-color: #f9f9f9; padding: 12px 20px; font-size: 12px; color: #999; text-align: center;">
      此邮件由库存管理系统自动发送，请勿直接回复。
    </div>
  </div>
</body>
</html>"""

    # ==================== 短信通知 ====================

    async def _send_sms(
        self, event: AlertEvent, rule: AlertRule
    ) -> dict:
        """
        通过 Twilio REST API 发送短信通知。

        使用 httpx 异步 HTTP 客户端调用 Twilio API。

        Args:
            event: 告警事件
            rule: 告警规则

        Returns:
            发送结果字典
        """
        recipient_ids = (
            rule.notify_recipients
            if isinstance(rule.notify_recipients, list)
            else []
        )
        if not recipient_ids:
            logger.warning("短信通知无接收人，跳过: event_id=%d", event.id)
            return {"status": "skipped", "error": "no_recipients"}

        # 检查 Twilio 配置
        if (
            not self.settings.twilio_account_sid
            or not self.settings.twilio_auth_token
            or not self.settings.twilio_phone_number
        ):
            logger.error("Twilio 配置不完整，无法发送短信")
            await self._log_notification(
                alert_event_id=event.id,
                channel="sms",
                status="failed",
                recipient="",
                error="Twilio 配置不完整",
            )
            return {"status": "failed", "error": "twilio_not_configured"}

        # 查询接收人手机号
        users = await self._get_users_by_ids(recipient_ids)
        if not users:
            logger.warning("短信接收人不存在或未激活: event_id=%d", event.id)
            return {"status": "skipped", "error": "no_valid_recipients"}

        # 构建短信内容
        severity_cn = SEVERITY_MAP.get(event.severity, event.severity)
        sms_body = (
            f"【库存告警】{severity_cn}级 - {event.title}。"
            f"{event.message}"
        )
        # Twilio 短信长度限制为 1600 字符
        if len(sms_body) > 1600:
            sms_body = sms_body[:1597] + "..."

        sent_count = 0
        failed_count = 0

        for user in users:
            if not user.phone:
                logger.warning(
                    "用户无手机号，跳过短信发送: user_id=%d", user.id
                )
                failed_count += 1
                await self._log_notification(
                    alert_event_id=event.id,
                    channel="sms",
                    status="failed",
                    recipient=f"user:{user.id}",
                    error="用户无手机号",
                )
                continue

            try:
                url = (
                    f"https://api.twilio.com/2010-04-01/Accounts/"
                    f"{self.settings.twilio_account_sid}/Messages.json"
                )
                payload = {
                    "From": self.settings.twilio_phone_number,
                    "To": user.phone,
                    "Body": sms_body,
                }

                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        url,
                        data=payload,
                        auth=(
                            self.settings.twilio_account_sid,
                            self.settings.twilio_auth_token,
                        ),
                    )

                if response.status_code in (200, 201):
                    sent_count += 1
                    logger.info(
                        "短信发送成功: event_id=%d, user_id=%d, phone=%s",
                        event.id,
                        user.id,
                        user.phone[:4] + "****" + user.phone[-4:]
                        if len(user.phone) >= 8
                        else "****",
                    )
                    await self._log_notification(
                        alert_event_id=event.id,
                        channel="sms",
                        status="sent",
                        recipient=user.phone,
                    )
                else:
                    error_msg = f"Twilio API 返回状态码 {response.status_code}: {response.text}"
                    logger.error(
                        "短信发送失败: event_id=%d, user_id=%d, %s",
                        event.id,
                        user.id,
                        error_msg,
                    )
                    failed_count += 1
                    await self._log_notification(
                        alert_event_id=event.id,
                        channel="sms",
                        status="failed",
                        recipient=user.phone,
                        error=error_msg,
                    )

            except httpx.TimeoutException:
                logger.error(
                    "短信发送超时: event_id=%d, user_id=%d",
                    event.id,
                    user.id,
                )
                failed_count += 1
                await self._log_notification(
                    alert_event_id=event.id,
                    channel="sms",
                    status="failed",
                    recipient=user.phone,
                    error="请求超时",
                )
            except Exception as e:
                logger.error(
                    "短信发送异常: event_id=%d, user_id=%d, 错误=%s",
                    event.id,
                    user.id,
                    str(e),
                    exc_info=True,
                )
                failed_count += 1
                await self._log_notification(
                    alert_event_id=event.id,
                    channel="sms",
                    status="failed",
                    recipient=user.phone,
                    error=str(e),
                )

        return {
            "status": "completed",
            "sent_count": sent_count,
            "failed_count": failed_count,
        }

    # ==================== Webhook 通知 ====================

    async def _send_webhook(
        self, event: AlertEvent, rule: AlertRule
    ) -> dict:
        """
        通过 Webhook 发送告警回调通知。

        POST JSON 数据到配置的 webhook_url，并在请求头中附带
        HMAC-SHA256 签名（X-Signature），供接收方验证请求来源。

        Args:
            event: 告警事件
            rule: 告警规则

        Returns:
            发送结果字典
        """
        if not self.settings.webhook_url:
            logger.error("Webhook URL 未配置，无法发送")
            await self._log_notification(
                alert_event_id=event.id,
                channel="webhook",
                status="failed",
                recipient=self.settings.webhook_url or "",
                error="Webhook URL 未配置",
            )
            return {"status": "failed", "error": "webhook_url_not_configured"}

        # 构建请求体
        payload = {
            "event_id": event.id,
            "rule_id": rule.id,
            "rule_name": rule.name,
            "rule_type": rule.rule_type,
            "severity": event.severity,
            "title": event.title,
            "message": event.message,
            "current_value": event.current_value,
            "threshold_value": event.threshold_value,
            "product_id": event.product_id,
            "warehouse_id": event.warehouse_id,
            "status": event.status,
            "created_at": (
                event.created_at.isoformat() if event.created_at else None
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 计算 HMAC-SHA256 签名
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        signature = ""
        if self.settings.webhook_secret:
            signature = hmac.new(
                self.settings.webhook_secret.encode("utf-8"),
                payload_json.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        else:
            logger.warning("Webhook 签名密钥未配置，请求将不带签名")

        headers = {
            "Content-Type": "application/json",
        }
        if signature:
            headers["X-Signature"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.settings.webhook_url,
                    json=payload,
                    headers=headers,
                )

            if 200 <= response.status_code < 300:
                logger.info(
                    "Webhook 发送成功: event_id=%d, url=%s, status_code=%d",
                    event.id,
                    self.settings.webhook_url,
                    response.status_code,
                )
                await self._log_notification(
                    alert_event_id=event.id,
                    channel="webhook",
                    status="sent",
                    recipient=self.settings.webhook_url,
                )
                return {
                    "status": "completed",
                    "status_code": response.status_code,
                }
            else:
                error_msg = (
                    f"Webhook 返回状态码 {response.status_code}: "
                    f"{response.text[:500]}"
                )
                logger.error(
                    "Webhook 发送失败: event_id=%d, %s",
                    event.id,
                    error_msg,
                )
                await self._log_notification(
                    alert_event_id=event.id,
                    channel="webhook",
                    status="failed",
                    recipient=self.settings.webhook_url,
                    error=error_msg,
                )
                return {
                    "status": "failed",
                    "status_code": response.status_code,
                    "error": error_msg,
                }

        except httpx.TimeoutException:
            error_msg = "Webhook 请求超时"
            logger.error("Webhook 发送超时: event_id=%d", event.id)
            await self._log_notification(
                alert_event_id=event.id,
                channel="webhook",
                status="failed",
                recipient=self.settings.webhook_url,
                error=error_msg,
            )
            return {"status": "failed", "error": error_msg}
        except httpx.ConnectError as e:
            error_msg = f"Webhook 连接失败: {e}"
            logger.error("Webhook 连接失败: event_id=%d, %s", event.id, error_msg)
            await self._log_notification(
                alert_event_id=event.id,
                channel="webhook",
                status="failed",
                recipient=self.settings.webhook_url,
                error=error_msg,
            )
            return {"status": "failed", "error": error_msg}
        except Exception as e:
            error_msg = str(e)
            logger.error(
                "Webhook 发送异常: event_id=%d, 错误=%s",
                event.id,
                error_msg,
                exc_info=True,
            )
            await self._log_notification(
                alert_event_id=event.id,
                channel="webhook",
                status="failed",
                recipient=self.settings.webhook_url,
                error=error_msg,
            )
            return {"status": "failed", "error": error_msg}

    # ==================== 通知日志记录 ====================

    async def _log_notification(
        self,
        alert_event_id: int,
        channel: str,
        status: str,
        recipient: str = "",
        subject: str = "",
        error: str = "",
    ) -> NotificationLog:
        """
        记录通知发送日志到数据库。

        Args:
            alert_event_id: 关联的告警事件ID
            channel: 通知渠道
            status: 发送状态 (pending/sent/failed)
            recipient: 接收人标识
            subject: 通知主题（可选）
            error: 错误信息（可选）

        Returns:
            创建的通知日志记录
        """
        log_record = NotificationLog(
            alert_event_id=alert_event_id,
            channel=channel,
            recipient=recipient or "N/A",
            subject=subject or None,
            body=f"[{channel}] 通知发送",
            status=status,
            error_message=error or None,
            sent_at=datetime.now(timezone.utc) if status == "sent" else None,
        )
        self.db.add(log_record)
        try:
            await self.db.flush()
        except Exception as e:
            logger.error(
                "通知日志写入失败: event_id=%d, channel=%s, 错误=%s",
                alert_event_id,
                channel,
                str(e),
                exc_info=True,
            )
        return log_record

    # ==================== 批量通知 ====================

    async def send_batch(self, events: list[AlertEvent]) -> dict:
        """
        批量发送告警通知。

        对多个告警事件逐一调用 send_alert，汇总所有结果。

        Args:
            events: 告警事件列表

        Returns:
            批量发送结果汇总
        """
        if not events:
            logger.warning("send_batch 收到空的 events 列表，跳过")
            return {"status": "skipped", "reason": "no_events"}

        logger.info("开始批量发送告警通知: 事件数=%d", len(events))

        total = len(events)
        success_count = 0
        fail_count = 0
        skip_count = 0
        details: list[dict] = []

        for event in events:
            try:
                result = await self.send_alert(event)
                details.append({
                    "event_id": event.id,
                    "result": result,
                })
                if result.get("status") == "completed":
                    success_count += 1
                elif result.get("status") == "skipped":
                    skip_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                logger.error(
                    "批量通知中单个事件发送失败: event_id=%d, 错误=%s",
                    event.id,
                    str(e),
                    exc_info=True,
                )
                fail_count += 1
                details.append({
                    "event_id": event.id,
                    "result": {"status": "failed", "error": str(e)},
                })

        summary = {
            "status": "completed",
            "total": total,
            "success": success_count,
            "failed": fail_count,
            "skipped": skip_count,
        }

        logger.info(
            "批量告警通知发送完成: %s",
            json.dumps(summary, ensure_ascii=False),
        )

        return summary
