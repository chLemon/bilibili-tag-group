"""测试夹具：临时 DataStore、FastAPI client 及种子数据。"""
import tempfile
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.dependencies import get_store
from app.main import app
from app.store.store import DataStore
from app.models.creator import Creator
from app.models.creator_tag import CreatorTag
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_status import VideoStatus


@pytest.fixture
def data_dir():
    """每个测试使用独立的临时目录，测试结束后自动清理。"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def store(data_dir):
    """提供绑定到临时目录的 DataStore。"""
    return DataStore(data_dir)


@dataclass
class SeededData:
    """种子数据引用，供测试用例读取 ID。"""

    tag_id: int
    creator_id: int
    video_id: int


@pytest_asyncio.fixture
async def seeded_data(store) -> SeededData:
    """向 store 写入最小可用种子数据：一个标签、一个 UP 主、一条未看视频。"""
    tag = Tag(name="测试标签")
    await store.tags.add(tag)

    creator = Creator(name="测试UP主", profile_url="https://space.bilibili.com/12345")
    await store.creators.add(creator)

    ct = CreatorTag(creator_id=creator.id, tag_id=tag.id)
    await store.creator_tags.add(ct)

    video = Video(
        bvid="BV_seed_001",
        creator_id=creator.id,
        title="种子视频",
        video_url="https://www.bilibili.com/video/BV_seed_001",
        published_at=datetime(2026, 1, 1, 12, 0, 0),
        duration_seconds=300,
    )
    await store.videos.add(video)

    status = VideoStatus(video_id=video.id)
    await store.video_statuses.add(status)

    return SeededData(tag_id=tag.id, creator_id=creator.id, video_id=video.id)


@pytest.fixture
def client(store):
    """提供绑定到临时 DataStore 的 FastAPI TestClient。"""
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
