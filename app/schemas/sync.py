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
