from pydantic import BaseModel, Field


class CreatorTag(BaseModel):
    id: int = Field(default=0)
    creator_id: int
    tag_id: int
