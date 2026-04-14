# -*- coding: utf-8 -*-
"""
ERP 同步 Celery 任务

提供由 Celery Beat 定时调度或手动触发的 ERP 数据同步任务。
任务在独立 Worker 进程中执行，通过创建新的异步数据库会话来调用 ErpSyncService。
"""

import asyncio
import logging

from app.tasks import celery_app
from app.db.engine import async_session_factory
from app.services.erp_sync_service import ErpSyncService

logger = logging.getLogger(__name__)


async def _run_sync(sync_type: str) -> dict:
    """
    异步执行 ERP 同步的内部函数。

    创建独立的数据库会话，实例化 ErpSyncService 并执行同步操作。
    无论成功或失败都会正确关闭会话。

    Args:
        sync_type: 同步类型 ("full" 或 "incremental")

    Returns:
        同步结果字典
    """
    async with async_session_factory() as session:
        try:
            service = ErpSyncService(db=session)

            if sync_type == "full":
                result = await service.full_sync()
            elif sync_type == "incremental":
                result = await service.incremental_sync()
            else:
                raise ValueError(f"不支持的同步类型: {sync_type}")

            await session.commit()
            return result

        except Exception as exc:
            await session.rollback()
            logger.error("ERP 同步任务执行失败 [type=%s]: %s", sync_type, exc, exc_info=True)
            raise
        finally:
            await session.close()


@celery_app.task(
    name="app.tasks.erp_sync_tasks.run_erp_sync",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
)
def run_erp_sync(self, sync_type: str = "incremental") -> dict:
    """
    Celery 任务：执行 ERP 数据同步。

    此函数是 Celery 任务的入口点（必须是同步函数），
    内部通过 asyncio.run 调用异步同步逻辑。

    支持的同步类型：
    - "incremental": 增量同步（默认），仅拉取上次同步后的变更数据
    - "full": 全量同步，拉取 ERP 中的所有产品和库存数据

    Args:
        sync_type: 同步类型，"incremental" 或 "full"

    Returns:
        同步结果字典，包含 success, failed, total, sync_log_id, error 等字段

    Raises:
        ValueError: 传入不支持的同步类型
    """
    logger.info("Celery ERP 同步任务启动: sync_type=%s", sync_type)

    try:
        result = asyncio.run(_run_sync(sync_type))
        logger.info(
            "Celery ERP 同步任务完成: sync_type=%s, success=%d, failed=%d, total=%d",
            sync_type,
            result.get("success", 0),
            result.get("failed", 0),
            result.get("total", 0),
        )
        return result

    except ValueError:
        logger.error("Celery ERP 同步任务参数错误: sync_type=%s", sync_type)
        raise

    except Exception as exc:
        logger.error(
            "Celery ERP 同步任务异常: sync_type=%s, error=%s",
            sync_type, exc,
            exc_info=True,
        )
        # 返回错误信息而非抛出异常，避免 Celery 无限重试
        return {
            "success": 0,
            "failed": 0,
            "total": 0,
            "sync_log_id": None,
            "error": f"任务执行异常: {exc}",
        }
