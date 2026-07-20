from datetime import datetime

from pydantic import BaseModel, Field


class Video(BaseModel):
    id: int = Field(default=0)
    bvid: str
    creator_id: int
    title: str
    video_url: str
    published_at: datetime
    duration_seconds: int
    cover_url: str | None = None
