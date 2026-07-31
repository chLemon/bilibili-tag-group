"""UP 主-标签关联模型。"""

from pydantic import BaseModel, Field


class CreatorTag(BaseModel):
    """UP 主与标签的多对多关联行。"""

    id: int = Field(default=0)  # 0 表示未分配，由 JsonRepo.add 分配
    creator_id: int
    tag_id: int
