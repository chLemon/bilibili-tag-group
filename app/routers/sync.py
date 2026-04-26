"""同步路由：查询最近同步状态、手动触发全量同步、查询调度配置。"""
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.sync_log import SyncLog
from app.schemas.sync import SyncLogRead
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/sync", tags=["sync"])
_sync_svc = SyncService()

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


@router.post("/run", response_model=SyncLogRead)
def run_sync(
    db: Annotated[Session, Depends(get_db)],
) -> SyncLogRead:
    """手动触发全量同步（对所有 enabled=True 的 UP 主执行同步）。"""
    log = _sync_svc.sync_all(db)
    return _to_sync_log_read(log)


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
