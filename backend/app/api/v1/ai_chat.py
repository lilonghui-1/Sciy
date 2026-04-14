# -*- coding: utf-8 -*-
"""
AI 智能助手路由

处理基于自然语言的库存查询与分析，使用 SSE 流式响应。
集成 LangChain Tool-Calling Agent，提供真实的 AI 对话能力。
"""

import logging
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.ai import ChatRequest
from app.services.ai_agent_service import AIAgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-chat", tags=["AI 智能助手"])


async def generate_chat_stream(
    message: str,
    history: list[dict] | None = None,
    db: AsyncSession = None,
) -> AsyncGenerator[str, None]:
    """
    生成 AI 聊天响应流（SSE 格式）

    使用 AIAgentService 进行真实的 AI 对话，通过 SSE 流式返回响应。

    Args:
        message: 用户消息
        history: 对话历史
        db: 数据库会话

    Yields:
        SSE 格式的数据块
    """
    try:
        # 创建 AI Agent 服务实例
        agent_service = AIAgentService(db)

        # 检查服务是否可用
        if not agent_service.is_available:
            error_data = {
                "type": "error",
                "content": agent_service._error_message or "AI 助手服务暂不可用",
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 流式获取 AI 响应
        async for chunk in agent_service.chat(message=message, history=history):
            if chunk:
                data = {
                    "type": "content",
                    "content": chunk,
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        # 发送结束标记
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error("AI 聊天流生成出错: %s", e, exc_info=True)
        error_data = {
            "type": "error",
            "content": f"处理消息时出现错误: {str(e)}",
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/chat", summary="AI 对话（SSE 流式响应）")
async def chat(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    向 AI 助手发送消息，获取库存相关的智能回复

    使用 Server-Sent Events (SSE) 进行流式响应，
    实现打字机效果的实时输出。

    请求体：
    - message: 用户消息（必填，1-2000字符）
    - conversation_id: 会话ID（可选）
    - history: 对话历史（可选），格式 [{"role": "user/assistant", "content": "..."}]

    响应格式（SSE）：
    - data: {"type": "content", "content": "文本片段"}
    - data: {"type": "error", "content": "错误信息"}
    - data: [DONE]
    """
    logger.info(
        "AI 聊天请求: 用户ID=%s, 消息长度=%d, 会话ID=%s",
        current_user.id,
        len(chat_request.message),
        chat_request.conversation_id,
    )

    # 从请求中提取对话历史
    history = chat_request.context.get("history", []) if chat_request.context else []

    return StreamingResponse(
        generate_chat_stream(
            message=chat_request.message,
            history=history,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
