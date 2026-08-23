"""标签领域模型。"""

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """UP 主分组标签。标签挂在 UP 主上（CreatorTag），不挂在视频上。"""

    id: int = Field(default=0)  # 0 表示未分配，由 JsonRepo.add 分配
    name: str


class TagSyncConfig(BaseModel):
    """标签同步配置：标记哪些标签下的 UP 主需要立即同步（同步间隔 5 分钟，普通 UP 主为 50 分钟）。"""

    id: int = Field(default=0)
    tag_id: int
    sync_mode: str = "immediate"
