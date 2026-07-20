from datetime import datetime

from pydantic import BaseModel, Field


class VideoStatus(BaseModel):
    id: int = Field(default=0)
    video_id: int
    status: int = 0
    watched_at: datetime | None = None
