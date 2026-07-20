from pydantic import BaseModel, Field


class Tag(BaseModel):
    id: int = Field(default=0)
    name: str
