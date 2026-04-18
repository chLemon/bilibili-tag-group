"""测试夹具：内存数据库、db_session、FastAPI client 及种子数据。"""
from dataclasses import dataclass
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
# 导入所有模型，确保 Base.metadata 包含全部表定义
import app.models  # noqa: F401
from app.dependencies import get_db
from app.main import app
from app.models.creator import Creator
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_status import VideoStatus


@pytest.fixture
def db_session():
    """每个测试使用独立的内存数据库，测试结束后自动清理。

    使用 StaticPool + check_same_thread=False，允许 TestClient 在工作线程中访问同一连接。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    """提供绑定到内存数据库的 FastAPI TestClient。

    覆盖 get_db 依赖注入，使路由测试使用与 db_session 相同的 Session。
    """
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@dataclass
class SeededData:
    """种子数据引用，供测试用例读取 ID。"""

    tag_id: int
    creator_id: int
    video_id: int


@pytest.fixture
def seeded_data(db_session):
    """向数据库写入最小可用种子数据：一个标签、一个 UP 主、一条未看视频。"""
    tag = Tag(name="测试标签")
    db_session.add(tag)
    db_session.flush()

    creator = Creator(name="测试UP主", profile_url="https://space.bilibili.com/12345")
    creator.tags.append(tag)
    db_session.add(creator)
    db_session.flush()

    video = Video(
        bvid="BV_seed_001",
        creator_id=creator.id,
        title="种子视频",
        video_url="https://www.bilibili.com/video/BV_seed_001",
        published_at=datetime(2026, 1, 1, 12, 0, 0),
        duration_seconds=300,
    )
    db_session.add(video)
    db_session.flush()

    status = VideoStatus(video_id=video.id, watched=False)
    db_session.add(status)
    db_session.commit()

    return SeededData(tag_id=tag.id, creator_id=creator.id, video_id=video.id)
