"""同步任务模型：追踪异步全量同步的进度。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SyncTask(Base):
    __tablename__ = "sync_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="running", nullable=False)
    """running / completed / failed"""
    total_creators: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_creators: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_creator_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new_videos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    """每次同步完一个 UP 主时更新，用于前端探活"""
