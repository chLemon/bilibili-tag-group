"""UP 主模型。时间字段统一为 naive UTC（见 app/utils/time.py）。"""
from datetime import datetime

from pydantic import BaseModel, Field


class Creator(BaseModel):
    """B 站 UP 主。标签通过 CreatorTag 关联，不直接挂在视频上。"""

    id: int = Field(default=0)  # 0 表示未分配，由 JsonRepo.add 分配
    name: str
    alias: str | None = None
    profile_url: str
    avatar_url: str | None = None
    enabled: bool = True
    video_count: int | None = None  # B 站侧视频总数，抓取时更新
    last_synced_at: datetime | None = None  # naive UTC
