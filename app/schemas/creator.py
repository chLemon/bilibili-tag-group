"""UP 主相关的 Pydantic Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


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


class BatchCreatorItem(BaseModel):
    """批量添加的单个 UP 主条目。"""

    uid: str
    tag_names: list[str] = []
    name: str | None = None

    @field_validator("uid")
    @classmethod
    def validate_uid(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("uid 不能为空")
        return value

    @field_validator("tag_names")
    @classmethod
    def validate_tag_names(cls, value: list[str]) -> list[str]:
        return [t.strip() for t in value if t.strip()]


class BatchCreatorRequest(BaseModel):
    """批量添加 UP 主的请求体。"""

    items: list[BatchCreatorItem]


class BatchCreatorResult(BaseModel):
    """单条批量添加结果。"""

    uid: str
    success: bool
    creator: CreatorRead | None = None
    error: str | None = None


class BatchCreatorResponse(BaseModel):
    """批量添加 UP 主的响应体。"""

    results: list[BatchCreatorResult]
