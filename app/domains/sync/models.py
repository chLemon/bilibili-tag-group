"""同步任务模型：追踪异步全量同步的进度。"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.time import now_utc


class SyncTask(BaseModel):
    id: int = Field(default=0)
    scope: str = "all"
    status: str = "running"
    """running / completed / failed"""
    total_creators: int = 0
    completed_creators: int = 0
    current_creator_name: str | None = None
    current_creator_pages: int = 0
    """当前 UP 主已抓取的页码，用于前端展示页级进度"""
    current_creator_total_pages: int = 0
    """当前 UP 主投稿总页数，与 current_creator_pages 配对展示"""
    new_videos: int = 0
    error_message: str | None = None
    started_at: datetime = Field(default_factory=now_utc)
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None
    """每次同步完一个 UP 主时更新，用于前端探活"""
