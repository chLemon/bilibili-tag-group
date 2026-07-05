"""同步相关的 Pydantic Schema。"""
from typing import Optional

from app.schemas._datetime import BeijingDateTime

from pydantic import BaseModel


class SyncLogRead(BaseModel):
    """同步日志读取响应体（对应 SyncLog ORM 字段）。"""

    id: int
    scope: str
    status: str
    new_videos: int
    error_message: Optional[str]
    started_at: BeijingDateTime
    finished_at: Optional[BeijingDateTime]

    model_config = {"from_attributes": True}


class SyncTaskRead(BaseModel):
    """同步任务进度响应体。"""

    id: int
    status: str
    total_creators: int
    completed_creators: int
    current_creator_name: Optional[str] = None
    new_videos: int
    error_message: Optional[str] = None
    started_at: BeijingDateTime
    finished_at: Optional[BeijingDateTime] = None
    heartbeat_at: Optional[BeijingDateTime] = None

    model_config = {"from_attributes": True}
