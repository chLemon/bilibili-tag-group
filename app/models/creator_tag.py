from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CreatorTag(Base):
    __tablename__ = "creator_tags"

    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)
