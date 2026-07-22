"""定时同步调度：使用 asyncio 循环替代 APScheduler。"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_sync_loop(sync_service, store, interval_minutes: int) -> None:
    """每隔 interval_minutes 分钟执行一次全量同步。

    通过 asyncio.sleep 实现周期调度，与 FastAPI 共用同一事件循环。
    异常不向上传播，保证循环持续运行。
    """
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            task, created = await sync_service.start_sync(store)
            if created:
                await sync_service.run_sync_task(task.id, store)
        except Exception:
            logger.exception("定时全量同步失败")
