"""UP 主领域模型。时间字段统一为 naive UTC（见 app/shared/time.py）。"""

from datetime import datetime

from pydantic import BaseModel, Field


class Creator(BaseModel):
    """B 站 UP 主。标签通过 CreatorTag 关联，不直接挂在视频上。"""

    id: int = Field(default=0)  # 0 表示未分配，由 JsonRepo.add 分配
    name: str
    alias: str | None = None
    profile_url: str
    avatar_url: str
    enabled: bool = True  # False 时 sync_creator 顶部直接跳过，不抓取不写库
    video_count: int  # B 站侧视频总数，创建时由 resolve 拿到，同步时更新
    last_synced_at: datetime | None = None  # naive UTC


class CreatorTag(BaseModel):
    """UP 主与标签的多对多关联行。"""

    id: int = Field(default=0)  # 0 表示未分配，由 JsonRepo.add 分配
    creator_id: int
    tag_id: int
