"""视频相关的 Pydantic Schema。"""

from pydantic import BaseModel, Field

from app.shared.time import BeijingDateTime


class VideoStatusUpdate(BaseModel):
    """更新视频状态的请求体。"""

    status: int = Field(ge=0, le=2)  # 0=未看, 1=已看, 2=不看


class VideoBatchStatusUpdate(BaseModel):
    """按 video_ids 批量更新视频状态的请求体。

    用于"一键已看/不看"按可见范围批量标记——不传 video_ids 时按
    creator 全量（走 /api/creators/{id}/videos/status），传 video_ids 时
    仅作用于这些视频（如标签视图隐藏充电视频时只标记非充电视频）。
    """

    video_ids: list[int]
    status: int = Field(ge=0, le=2)


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
    mark: str = ""

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
    mark: str = ""
    status: int = 0

    model_config = {"from_attributes": True}
