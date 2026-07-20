from datetime import datetime

from pydantic import BaseModel, Field


class Creator(BaseModel):
    id: int = Field(default=0)
    name: str
    alias: str | None = None
    profile_url: str
    avatar_url: str | None = None
    enabled: bool = True
    video_count: int | None = None
    last_synced_at: datetime | None = None
