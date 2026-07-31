"""视频观看状态模型。时间字段统一为 naive UTC（见 app/utils/time.py）。"""
from datetime import datetime

from pydantic import BaseModel, Field


class VideoStatus(BaseModel):
    """视频观看状态，与 Video 一对一（按 video_id 关联）。

    status: 0=未看, 1=已看, 2=不看。watched_at 仅在标记已看时写入，
    切回未看/不看时清空。
    """

    id: int = Field(default=0)  # 0 表示未分配，由 JsonRepo.add 分配
    video_id: int
    status: int = 0
    watched_at: datetime | None = None  # naive UTC
