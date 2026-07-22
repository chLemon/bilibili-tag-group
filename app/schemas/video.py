"""视频相关的 Pydantic Schema。"""

from pydantic import BaseModel

from app.schemas._datetime import BeijingDateTime


class VideoStatusUpdate(BaseModel):
    """更新视频状态的请求体。"""

    status: int  # 0=未看, 1=已看, 2=不看


class VideoRead(BaseModel):
    """标签页视频列表中的视频响应体。

    包含视频基础信息以及所属 UP 主名称和别名，供前端标签视图展示。
    """

    id: int
    bvid: str
    title: str
    creator_id: int
    creator_name: str
    creator_alias: str | None = None
    creator_avatar_url: str | None = None
    video_url: str
    cover_url: str | None = None
    published_at: BeijingDateTime
    duration_seconds: int

    model_config = {"from_attributes": True}


class VideoDetail(BaseModel):
    """视频详情响应体，包含已看状态和所属 UP 主名称。"""

    id: int
    bvid: str
    title: str
    creator_id: int
    creator_name: str
    creator_alias: str | None = None
    creator_avatar_url: str | None = None
    video_url: str
    cover_url: str | None = None
    published_at: BeijingDateTime
    duration_seconds: int
    status: int = 0

    model_config = {"from_attributes": True}
