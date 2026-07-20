"""同步路由：查询最近同步状态、手动触发全量同步、查询调度配置、管理立即同步标签。"""
import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.dependencies import get_store
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.models.sync_task import SyncTask
from app.models.tag import Tag
from app.models.tag_sync_config import TagSyncConfig
from app.services.sync_service import SyncService
from app.store.store import DataStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])
_sync_svc = SyncService(fetcher=PlaywrightBilibiliFetcher(cookie=settings.bilibili_cookie or None))

_sync_loop_running: bool = False
_sync_interval_minutes: int = 60


def set_sync_context(loop_running: bool, interval_minutes: int) -> None:
    """由 lifespan 调用，将同步循环状态与间隔配置注入路由模块。"""
    global _sync_loop_running, _sync_interval_minutes
    _sync_loop_running = loop_running
    _sync_interval_minutes = interval_minutes


@router.get("/latest", response_model=SyncTask | None)
def get_latest_sync(
    store: Annotated[DataStore, Depends(get_store)],
) -> SyncTask | None:
    """查询最近一次全量同步任务。"""
    tasks = store.sync_tasks.filter(scope="all")
    if not tasks:
        return None
    return max(tasks, key=lambda t: t.started_at)


@router.post("/run", response_model=SyncTask)
async def run_sync(
    store: Annotated[DataStore, Depends(get_store)],
) -> SyncTask:
    """手动触发全量同步：创建同步任务，后台协程执行，立即返回任务进度。"""
    task = await _sync_svc.start_async_sync(store)
    asyncio.create_task(_sync_svc._run_async_sync(task.id, store))
    return task


@router.get("/task/current", response_model=SyncTask | None)
def get_current_task(
    store: Annotated[DataStore, Depends(get_store)],
) -> SyncTask | None:
    """查询当前（或最近一次）同步任务的进度。"""
    tasks = store.sync_tasks.all()
    if not tasks:
        return None
    return max(tasks, key=lambda t: t.started_at)


@router.get("/settings", response_model=dict[str, Any])
def get_sync_settings() -> dict[str, Any]:
    """查询定时同步的调度配置与状态。"""
    return {
        "enabled": _sync_loop_running,
        "interval_minutes": _sync_interval_minutes,
        "job_id": "sync-all",
    }


# ── 立即同步标签管理 ─────────────────────────────────────────────


@router.get("/immediate-tags", response_model=list[dict])
def list_immediate_tags(
    store: Annotated[DataStore, Depends(get_store)],
) -> list[dict]:
    """查询所有配置了"立即同步"的标签列表。"""
    rows = store.tag_sync_configs.all()
    return [
        {"id": row.id, "tag_id": row.tag_id, "sync_mode": row.sync_mode}
        for row in rows
    ]


@router.post("/immediate-tags", status_code=status.HTTP_201_CREATED, response_model=dict)
async def add_immediate_tag(
    tag_id: int,
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    """将指定标签设为"立即同步"模式。"""
    tag = store.tags.get(tag_id)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"标签 id={tag_id} 不存在"
        )

    existing_list = store.tag_sync_configs.filter(tag_id=tag_id)
    if existing_list:
        existing = existing_list[0]
        return {"id": existing.id, "tag_id": existing.tag_id, "sync_mode": existing.sync_mode}

    config = TagSyncConfig(tag_id=tag_id, sync_mode="immediate")
    await store.tag_sync_configs.add(config)
    return {"id": config.id, "tag_id": config.tag_id, "sync_mode": config.sync_mode}


@router.delete("/immediate-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_immediate_tag(
    tag_id: int,
    store: Annotated[DataStore, Depends(get_store)],
) -> None:
    """将指定标签从"立即同步"中移除（恢复为默认 TTL 模式）。"""
    configs = store.tag_sync_configs.filter(tag_id=tag_id)
    if not configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"标签 id={tag_id} 未配置为立即同步",
        )
    await store.tag_sync_configs.delete(configs[0].id)
