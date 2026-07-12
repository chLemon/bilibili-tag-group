from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VideoStatus(Base):
    __tablename__ = "video_statuses"

    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), primary_key=True)
    status: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    watched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    video = relationship("Video", back_populates="status")
