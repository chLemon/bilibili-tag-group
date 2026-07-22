"""测试夹具：临时 DataStore、FastAPI client 及种子数据。"""
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.dependencies import get_fetcher, get_store, get_sync_service
from app.main import app
from app.models.creator import Creator
from app.models.creator_tag import CreatorTag
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.services.sync_service import SyncService
from app.store.store import DataStore


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
def mock_fetcher():
    """默认 mock 抓取器：昵称/头像固定返回，视频列表为空。"""
    m = MagicMock()
    m.fetch_creator_info = AsyncMock(
        return_value={"name": "测试UP主", "avatar_url": None, "video_count": 0}
    )
    m.fetch_new_videos = AsyncMock(return_value=[])
    return m


@pytest.fixture
def client(store, mock_fetcher):
    """提供绑定到临时 DataStore 与 mock 抓取器的 FastAPI TestClient。"""
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_fetcher] = lambda: mock_fetcher
    app.dependency_overrides[get_sync_service] = lambda: SyncService(fetcher=mock_fetcher)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
