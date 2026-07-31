"""视频模型。时间字段统一为 naive UTC（见 app/utils/time.py）。"""

from datetime import datetime

from pydantic import BaseModel, Field


class Video(BaseModel):
    """B 站视频。观看状态单独存于 VideoStatus（一对一，按 video_id 关联）。"""

    id: int = Field(default=0)  # 0 表示未分配，由 JsonRepo.add 分配
    bvid: str
    creator_id: int
    title: str
    video_url: str
    published_at: datetime  # naive UTC
    duration_seconds: int
    cover_url: str | None = None
