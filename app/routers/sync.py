"""同步路由：查询最近同步状态、手动触发全量同步、查询调度配置、管理立即同步标签。"""
import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.models.sync_log import SyncLog
from app.models.sync_task import SyncTask
from app.models.tag_sync_config import TagSyncConfig
from app.schemas.sync import SyncLogRead, SyncTaskRead
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])
_sync_svc = SyncService(fetcher=PlaywrightBilibiliFetcher(cookie=settings.bilibili_cookie or None))

# 由 main.py 的 lifespan 在应用启动后注入，供 /settings 接口读取
_scheduler: Any = None
_sync_interval_minutes: int = 60


def set_scheduler_context(scheduler: Any, interval_minutes: int) -> None:
    """由 lifespan 调用，将调度器实例与间隔配置注入路由模块。

    参数：
        scheduler: 已构造（可能已启动）的 BackgroundScheduler
        interval_minutes: 配置的同步间隔分钟数
    """
    global _scheduler, _sync_interval_minutes
    _scheduler = scheduler
    _sync_interval_minutes = interval_minutes


def _to_sync_log_read(log: SyncLog) -> SyncLogRead:
    """将 ORM SyncLog 对象转换为 SyncLogRead schema。"""
    return SyncLogRead(
        id=log.id,
        scope=log.scope,
        status=log.status,
        new_videos=log.new_videos,
        error_message=log.error_message,
        started_at=log.started_at,
        finished_at=log.finished_at,
    )


@router.get("/latest", response_model=Optional[SyncLogRead])
def get_latest_sync(
    db: Annotated[Session, Depends(get_db)],
) -> Optional[SyncLogRead]:
    """查询最近一次全量同步的 SyncLog。

    尚无同步记录时返回 null。
    """
    log = (
        db.query(SyncLog)
        .filter(SyncLog.scope == "all")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if log is None:
        return None
    return _to_sync_log_read(log)


@router.post("/run", response_model=SyncTaskRead)
def run_sync(
    db: Annotated[Session, Depends(get_db)],
) -> SyncTaskRead:
    """手动触发全量同步：创建同步任务，后台执行，立即返回任务进度。"""
    task = _sync_svc.start_async_sync(db)
    return SyncTaskRead(
        id=task.id,
        status=task.status,
        total_creators=task.total_creators,
        completed_creators=task.completed_creators,
        current_creator_name=task.current_creator_name,
        new_videos=task.new_videos,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
        heartbeat_at=task.heartbeat_at,
    )


@router.get("/task/current", response_model=Optional[SyncTaskRead])
def get_current_task(
    db: Annotated[Session, Depends(get_db)],
) -> Optional[SyncTaskRead]:
    """查询当前（或最近一次）同步任务的进度。

    前端每 3 秒轮询此接口以更新进度条。
    """
    task = (
        db.query(SyncTask)
        .order_by(SyncTask.started_at.desc())
        .first()
    )
    if task is None:
        return None
    return SyncTaskRead(
        id=task.id,
        status=task.status,
        total_creators=task.total_creators,
        completed_creators=task.completed_creators,
        current_creator_name=task.current_creator_name,
        new_videos=task.new_videos,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
        heartbeat_at=task.heartbeat_at,
    )


@router.get("/settings", response_model=dict[str, Any])
def get_sync_settings() -> dict[str, Any]:
    """查询定时同步的调度配置与状态。

    返回字段：
    - enabled: bool，sync-all job 是否已注册
    - interval_minutes: int，配置的同步间隔分钟数
    - job_id: str，固定为 'sync-all'
    """
    from app.scheduler import SYNC_JOB_ID, get_sync_job_info

    # 测试环境或 lifespan 未执行时 _scheduler 可能为 None，返回 enabled=False 兜底
    if _scheduler is None:
        return {
            "enabled": False,
            "interval_minutes": _sync_interval_minutes,
            "job_id": SYNC_JOB_ID,
        }
    return get_sync_job_info(_scheduler, _sync_interval_minutes)


# ── 立即同步标签管理 ─────────────────────────────────────────────


@router.get("/immediate-tags", response_model=list[dict])
def list_immediate_tags(
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    """查询所有配置了"立即同步"的标签列表。"""
    rows = db.query(TagSyncConfig).all()
    return [
        {"id": row.id, "tag_id": row.tag_id, "sync_mode": row.sync_mode}
        for row in rows
    ]


@router.post("/immediate-tags", status_code=status.HTTP_201_CREATED, response_model=dict)
def add_immediate_tag(
    tag_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """将指定标签设为"立即同步"模式。

    已存在的标签幂等返回；tag_id 不存在的标签返回 404。
    """
    from app.models.tag import Tag

    tag = db.query(Tag).filter_by(id=tag_id).first()
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"标签 id={tag_id} 不存在"
        )

    existing = db.query(TagSyncConfig).filter_by(tag_id=tag_id).first()
    if existing is not None:
        return {"id": existing.id, "tag_id": existing.tag_id, "sync_mode": existing.sync_mode}

    config = TagSyncConfig(tag_id=tag_id, sync_mode="immediate")
    db.add(config)
    db.flush()
    return {"id": config.id, "tag_id": config.tag_id, "sync_mode": config.sync_mode}


@router.delete("/immediate-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_immediate_tag(
    tag_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """将指定标签从"立即同步"中移除（恢复为默认 TTL 模式）。"""
    config = db.query(TagSyncConfig).filter_by(tag_id=tag_id).first()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"标签 id={tag_id} 未配置为立即同步",
        )
    db.delete(config)
    db.flush()
