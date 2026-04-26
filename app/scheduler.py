"""定时同步调度器：使用 APScheduler 注册周期性全量同步任务。"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# 调度器内 sync-all job 的固定 id
SYNC_JOB_ID = "sync-all"


def _noop() -> None:
    """空操作占位 callable，供 sync_callable=None 时使用。"""


def build_scheduler(
    sync_interval_minutes: int,
    sync_callable: Callable[[], Any] | None = None,
) -> BackgroundScheduler:
    """构造并配置 BackgroundScheduler，注册 sync-all 定时 job。

    只负责构造与注册，不启动调度器（调用方负责 start/shutdown）。

    参数：
        sync_interval_minutes: 同步间隔分钟数
        sync_callable: 定时触发时执行的函数；为 None 时使用空操作占位符

    返回：
        已注册 sync-all job、尚未启动的 BackgroundScheduler
    """
    func = sync_callable if sync_callable is not None else _noop
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func,
        trigger=IntervalTrigger(minutes=sync_interval_minutes),
        id=SYNC_JOB_ID,
        replace_existing=True,
    )
    return scheduler


def get_sync_job_info(
    scheduler: BackgroundScheduler,
    sync_interval_minutes: int,
) -> dict[str, Any]:
    """查询 sync-all job 的调度状态，用于向前端暴露调度配置。

    参数：
        scheduler: 当前运行（或已构造）的调度器实例
        sync_interval_minutes: 配置文件中读取到的间隔分钟数（用于回填响应）

    返回：
        包含以下字段的字典：
        - enabled: bool，sync-all job 是否存在
        - interval_minutes: int，配置的同步间隔分钟数
        - job_id: str，固定为 'sync-all'
    """
    job = scheduler.get_job(SYNC_JOB_ID)
    return {
        "enabled": job is not None,
        "interval_minutes": sync_interval_minutes,
        "job_id": SYNC_JOB_ID,
    }
