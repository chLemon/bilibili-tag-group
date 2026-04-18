"""UP 主相关的 Pydantic Schema。"""
from typing import Optional

from pydantic import BaseModel


class CreatorCreate(BaseModel):
    """创建 UP 主的请求体。"""

    name: str
    profile_url: str
    tag_ids: list[int] = []


class CreatorUpdate(BaseModel):
    """编辑 UP 主的请求体（PATCH，所有字段可选）。"""

    name: Optional[str] = None
    enabled: Optional[bool] = None
    tag_ids: Optional[list[int]] = None


class CreatorRead(BaseModel):
    """UP 主读取响应体。"""

    id: int
    name: str
    profile_url: str
    enabled: bool
    tag_ids: list[int] = []

    model_config = {"from_attributes": True}
