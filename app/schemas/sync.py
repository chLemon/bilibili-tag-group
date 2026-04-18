"""同步相关的 Pydantic Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SyncLogRead(BaseModel):
    """同步日志读取响应体（对应 SyncLog ORM 字段）。"""

    id: int
    scope: str
    status: str
    new_videos: int
    error_message: Optional[str]
    started_at: datetime
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}
