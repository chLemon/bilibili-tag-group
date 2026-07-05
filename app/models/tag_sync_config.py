"""标签同步配置：标记哪些标签下的 UP 主需要立即同步（绕过 TTL 缓存）。"""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TagSyncConfig(Base):
    __tablename__ = "tag_sync_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), unique=True, nullable=False)
    sync_mode: Mapped[str] = mapped_column(
        String(16), default="immediate", server_default="immediate", nullable=False
    )

    tag = relationship("Tag")
