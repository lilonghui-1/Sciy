# -*- coding: utf-8 -*-
"""
WebSocket 连接管理器

管理所有活跃的 WebSocket 连接，支持：
- 按用户 ID 维护连接集合（同一用户可有多端连接）
- 向指定用户发送消息
- 全局广播消息
- 向指定用户列表发送告警通知
- 在线用户统计
"""

import asyncio
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocket 连接管理器

    维护 user_id -> Set[WebSocket] 的映射关系，支持同一用户
    在多个设备/浏览器上同时保持 WebSocket 连接。

    所有对 WebSocket 的发送操作均捕获异常，自动清理已断开的连接，
    确保单个连接异常不会影响其他连接的正常工作。
    """

    def __init__(self) -> None:
        """初始化连接管理器，创建空的连接映射表。"""
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        """
        接受 WebSocket 连接并将其存储到管理器中。

        Args:
            websocket: WebSocket 连接实例
            user_id: 用户ID
        """
        await websocket.accept()
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        logger.info(
            "WebSocket 连接建立: user_id=%d, 当前该用户连接数=%d",
            user_id,
            len(self.active_connections.get(user_id, set())),
        )

    def disconnect(self, websocket: WebSocket, user_id: int) -> None:
        """
        断开并移除 WebSocket 连接。

        如果该用户已无其他活跃连接，则从映射表中移除该用户条目。

        Args:
            websocket: 要移除的 WebSocket 连接实例
            user_id: 用户ID
        """
        connections = self.active_connections.get(user_id)
        if connections is None:
            logger.warning(
                "断开连接时未找到用户: user_id=%d，可能已被清理", user_id
            )
            return

        connections.discard(websocket)
        if not connections:
            self.active_connections.pop(user_id, None)
            logger.info(
                "用户所有 WebSocket 连接已断开，已清理: user_id=%d", user_id
            )
        else:
            logger.info(
                "WebSocket 连接断开: user_id=%d, 剩余连接数=%d",
                user_id,
                len(connections),
            )

    async def send_to_user(self, user_id: int, message: dict) -> int:
        """
        向指定用户的所有活跃 WebSocket 连接发送 JSON 消息。

        自动处理已断开的连接，将其从连接池中移除。
        如果发送过程中出现异常，记录日志并跳过该连接。

        Args:
            user_id: 目标用户ID
            message: 要发送的消息字典，将被序列化为 JSON

        Returns:
            成功发送的连接数量
        """
        connections = self.active_connections.get(user_id)
        if not connections:
            logger.debug("用户无活跃 WebSocket 连接，跳过发送: user_id=%d", user_id)
            return 0

        success_count = 0
        failed_connections: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(message)
                success_count += 1
            except Exception as e:
                logger.warning(
                    "向用户发送 WebSocket 消息失败: user_id=%d, 错误=%s",
                    user_id,
                    str(e),
                )
                failed_connections.append(websocket)

        # 清理已失败的连接
        if failed_connections:
            async with self._lock:
                for ws in failed_connections:
                    self.disconnect(ws, user_id)

        return success_count

    async def broadcast(self, message: dict) -> int:
        """
        向所有已连接用户广播消息。

        遍历所有活跃连接并发送消息，自动处理发送失败的连接。

        Args:
            message: 要广播的消息字典

        Returns:
            成功发送的连接总数
        """
        if not self.active_connections:
            logger.debug("无活跃 WebSocket 连接，跳过广播")
            return 0

        total_success = 0
        # 复制一份 user_ids 列表，避免迭代过程中字典被修改
        user_ids = list(self.active_connections.keys())

        for user_id in user_ids:
            count = await self.send_to_user(user_id, message)
            total_success += count

        logger.info(
            "WebSocket 广播完成: 目标用户数=%d, 成功发送连接数=%d",
            len(user_ids),
            total_success,
        )
        return total_success

    async def send_alert(self, user_ids: list[int], alert_data: dict) -> dict:
        """
        向指定用户列表发送告警通知。

        对每个用户尝试通过 WebSocket 推送告警数据，并汇总发送结果。

        Args:
            user_ids: 目标用户ID列表
            alert_data: 告警数据字典，应包含 type, severity, title, message 等字段

        Returns:
            发送结果摘要，包含成功和失败的用户ID列表
        """
        if not user_ids:
            logger.warning("send_alert 收到空的 user_ids 列表，跳过")
            return {"sent": [], "failed": []}

        sent_users: list[int] = []
        failed_users: list[int] = []

        for user_id in user_ids:
            try:
                count = await self.send_to_user(user_id, alert_data)
                if count > 0:
                    sent_users.append(user_id)
                else:
                    failed_users.append(user_id)
            except Exception as e:
                logger.error(
                    "向用户发送告警失败: user_id=%d, 错误=%s",
                    user_id,
                    str(e),
                )
                failed_users.append(user_id)

        logger.info(
            "告警推送完成: 成功=%d, 失败=%d, 总计=%d",
            len(sent_users),
            len(failed_users),
            len(user_ids),
        )

        return {"sent": sent_users, "failed": failed_users}

    def get_online_count(self) -> int:
        """
        获取当前在线用户数量。

        Returns:
            当前有活跃 WebSocket 连接的用户数量
        """
        return len(self.active_connections)

    def get_connection_count(self) -> int:
        """
        获取当前所有活跃 WebSocket 连接总数（包含同一用户的多端连接）。

        Returns:
            活跃连接总数
        """
        return sum(len(conns) for conns in self.active_connections.values())


# ==================== 模块级单例 ====================
ws_manager = WebSocketManager()
