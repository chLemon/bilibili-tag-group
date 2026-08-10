"""标签同步配置：标记哪些标签下的 UP 主需要立即同步（同步间隔 5 分钟，普通 UP 主为 50 分钟）。"""

from pydantic import BaseModel, Field


class TagSyncConfig(BaseModel):
    id: int = Field(default=0)
    tag_id: int
    sync_mode: str = "immediate"
