"""标签相关的 Pydantic Schema。"""
from pydantic import BaseModel, field_validator


class TagCreate(BaseModel):
    """创建标签的请求体。"""

    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("标签名不能为空")
        return value


class TagRead(BaseModel):
    """标签读取响应体。"""

    id: int
    name: str

    model_config = {"from_attributes": True}
