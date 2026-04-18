"""视频相关的 Pydantic Schema。"""
from datetime import datetime

from pydantic import BaseModel


class VideoWatchedUpdate(BaseModel):
    """更新视频已看状态的请求体。"""

    watched: bool


class VideoRead(BaseModel):
    """标签页视频列表中的视频响应体。

    包含视频基础信息以及所属 UP 主名称，供前端标签视图展示。
    """

    id: int
    bvid: str
    title: str
    creator_id: int
    creator_name: str
    video_url: str
    published_at: datetime
    duration_seconds: int

    model_config = {"from_attributes": True}
