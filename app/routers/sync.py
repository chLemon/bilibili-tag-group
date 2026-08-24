"""同步路由：查询最近同步状态、手动触发全量同步、查询调度配置、管理立即同步标签。"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_store, get_sync_service
from app.domains.sync.schemas import SyncTaskRead
from app.domains.sync.service import SyncService
from app.shared.store import DataStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])

_sync_loop_running: bool = False
_sync_interval_minutes: int = 60

# 持有后台任务引用：create_task 的任务若无人引用，可能被 GC 提前取消；
# 完成回调里统一取出异常，避免"任务静默死亡"
_background_tasks: set[asyncio.Task] = set()


def _spawn_background(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _background_tasks.discard(t)
        if not t.cancelled() and (exc := t.exception()) is not None:
            logger.error("后台同步任务异常退出：%s", exc, exc_info=exc)

    task.add_done_callback(_on_done)


def set_sync_context(loop_running: bool, interval_minutes: int) -> None:
    """由 lifespan 调用，将同步循环状态与间隔配置注入路由模块。"""
    global _sync_loop_running, _sync_interval_minutes
    _sync_loop_running = loop_running
    _sync_interval_minutes = interval_minutes


@router.get("/latest", response_model=list[SyncTaskRead])
def get_latest_sync(
    store: Annotated[DataStore, Depends(get_store)],
    limit: int = 3,
) -> list[SyncTaskRead]:
    """查询最近若干条同步任务（不限 scope，按开始时间倒序）。

    默认返回 3 条，包含全量与单 UP 主任务。limit 上限 20。
    单 UP 主任务 (scope=creator) 会附带 creator_name 便于前端展示。
    """
    limit = max(1, min(limit, 20))
    tasks = sorted(store.sync_tasks.all(), key=lambda t: t.started_at, reverse=True)
    result: list[SyncTaskRead] = []
    for t in tasks[:limit]:
        read = SyncTaskRead.model_validate(t)
        if read.scope == "creator" and read.creator_id is not None:
            creator = store.creators.get(read.creator_id)
            if creator is not None:
                read.creator_name = creator.name
        result.append(read)
    return result


@router.post("/run", response_model=SyncTaskRead)
async def run_sync(
    store: Annotated[DataStore, Depends(get_store)],
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> SyncTaskRead:
    """手动触发全量同步：幂等创建任务，后台协程执行，立即返回任务进度。

    已有全量任务在跑时返回现有任务（幂等）；已有单 UP 主任务在跑时返回 409。
    """
    try:
        task, created = await sync_svc.start_sync(store)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if created:
        _spawn_background(sync_svc.run_sync_task(task.id, store))
    return task


@router.post("/creators/{creator_id}", response_model=SyncTaskRead)
async def sync_single_creator(
    creator_id: int,
    store: Annotated[DataStore, Depends(get_store)],
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> SyncTaskRead:
    """手动触发单个 UP 主同步：绕过 TTL 节流，后台协程执行。

    同 UP 主已有 running 的单 UP 主任务时返回现有任务（幂等）；
    其他任何同步任务在跑时返回 409；enabled=False 的 UP 主返回 400，需先启用。
    """
    creator = store.creators.get(creator_id)
    if creator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"UP 主 id={creator_id} 不存在",
        )
    if not creator.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="UP 主已停用，请先启用再同步",
        )
    try:
        task, created = await sync_svc.start_single_creator_sync(store, creator)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if created:
        _spawn_background(sync_svc.run_single_creator_sync(task.id, store, creator_id))
    return task


@router.get("/task/current", response_model=SyncTaskRead | None)
def get_current_task(
    store: Annotated[DataStore, Depends(get_store)],
) -> SyncTaskRead | None:
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
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> list[dict]:
    """查询所有配置了"立即同步"的标签列表。"""
    return [
        {"id": c.id, "tag_id": c.tag_id, "sync_mode": c.sync_mode}
        for c in sync_svc.list_immediate_tags(store)
    ]


@router.post("/immediate-tags", status_code=status.HTTP_201_CREATED, response_model=dict)
async def add_immediate_tag(
    tag_id: int,
    store: Annotated[DataStore, Depends(get_store)],
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> dict:
    """将指定标签设为"立即同步"模式。"""
    try:
        config = await sync_svc.add_immediate_tag(store, tag_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"id": config.id, "tag_id": config.tag_id, "sync_mode": config.sync_mode}


@router.delete("/immediate-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_immediate_tag(
    tag_id: int,
    store: Annotated[DataStore, Depends(get_store)],
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> None:
    """将指定标签从"立即同步"中移除（恢复为默认 TTL 模式）。"""
    if not await sync_svc.remove_immediate_tag(store, tag_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"标签 id={tag_id} 未配置为立即同步",
        )
