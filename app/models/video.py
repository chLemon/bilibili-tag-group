from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    bvid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    video_url: Mapped[str] = mapped_column(String(512), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    creator = relationship("Creator", back_populates="videos")
    status = relationship("VideoStatus", back_populates="video", uselist=False)
