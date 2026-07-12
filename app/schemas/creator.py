"""UP 主相关的 Pydantic Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CreatorCreate(BaseModel):
    """创建 UP 主的请求体。"""

    name: str
    profile_url: str
    avatar_url: Optional[str] = None
    alias: Optional[str] = None
    tag_ids: list[int] = []


class CreatorUpdate(BaseModel):
    """编辑 UP 主的请求体（PATCH，所有字段可选）。"""

    name: Optional[str] = None
    alias: Optional[str] = None
    tag_ids: Optional[list[int]] = None


class CreatorRead(BaseModel):
    """UP 主读取响应体。"""

    id: int
    name: str
    alias: Optional[str] = None
    profile_url: str
    avatar_url: Optional[str] = None
    tag_ids: list[int] = []
    video_count: int = 0
    synced_video_count: int = 0
    unwatched_count: int = 0
    last_synced_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
