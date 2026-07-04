"""Fetcher 本地缓存 ORM 模型。"""
from sqlalchemy import Column, String, Text
from app.database import Base


class Cache(Base):
    __tablename__ = "cache"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)
