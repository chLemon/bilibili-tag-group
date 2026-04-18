"""标签相关的 Pydantic Schema。"""
from pydantic import BaseModel


class TagRead(BaseModel):
    """标签读取响应体。"""

    id: int
    name: str

    model_config = {"from_attributes": True}
