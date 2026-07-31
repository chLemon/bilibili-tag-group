"""标签模型。"""
from pydantic import BaseModel, Field


class Tag(BaseModel):
    """UP 主分组标签。标签挂在 UP 主上（CreatorTag），不挂在视频上。"""

    id: int = Field(default=0)  # 0 表示未分配，由 JsonRepo.add 分配
    name: str
