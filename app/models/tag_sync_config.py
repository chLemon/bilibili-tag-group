"""标签同步配置：标记哪些标签下的 UP 主需要立即同步（绕过 TTL 缓存）。"""
from pydantic import BaseModel, Field


class TagSyncConfig(BaseModel):
    id: int = Field(default=0)
    tag_id: int
    sync_mode: str = "immediate"
