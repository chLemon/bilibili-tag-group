"""测试同步服务：SyncService.sync_creator 和 SyncService.sync_all。"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.fetcher.models import FetchedVideo
from app.models.creator import Creator
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.models.sync_task import SyncTask
from app.services.sync_service import SyncService


def _make_fetched_video(bvid: str, title: str = "默认标题", offset: int = 0) -> FetchedVideo:
    return FetchedVideo(
        bvid=bvid,
        title=title,
        video_url=f"https://www.bilibili.com/video/{bvid}",
        published_at=datetime(2024, 1, 1 + offset, 12, 0, 0),
        duration_seconds=300 + offset * 10,
    )


async def _make_creator_async(store, uid: str = "12345", enabled: bool = True) -> Creator:
    creator = Creator(
        name="测试UP主",
        profile_url=f"https://space.bilibili.com/{uid}",
        enabled=enabled,
    )
    await store.creators.add(creator)
    return creator


def _make_mock_fetcher(fetch_creator_info=None, fetch_new_videos=None):
    m = MagicMock()
    m.fetch_creator_info = AsyncMock(return_value=fetch_creator_info if fetch_creator_info is not None else {})
    m.fetch_new_videos = AsyncMock(return_value=fetch_new_videos if fetch_new_videos is not None else [])
    return m


class TestSyncCreatorNewVideos:
    async def test_new_videos_are_created(self, store):
        creator = await _make_creator_async(store)
        fetched = [_make_fetched_video("BV1aa111a1aA"), _make_fetched_video("BV2bb222b2bB")]
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=fetched)
        service = SyncService(fetcher=mock_fetcher)
        count = await service.sync_creator(store, creator)

        assert count == 2
        videos = store.videos.filter(creator_id=creator.id)
        assert len(videos) == 2

    async def test_new_videos_have_video_status_with_watched_false(self, store):
        creator = await _make_creator_async(store)
        fetched = [_make_fetched_video("BV1aa111a1aA")]
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=fetched)
        service = SyncService(fetcher=mock_fetcher)
        await service.sync_creator(store, creator)

        videos = store.videos.filter(creator_id=creator.id)
        for v in videos:
            statuses = store.video_statuses.filter(video_id=v.id)
            assert len(statuses) == 1
            assert statuses[0].status == 0

    async def test_returns_count_of_new_videos(self, store):
        creator = await _make_creator_async(store)
        fetched = [_make_fetched_video("BV1aa111a1aA")]
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=fetched)
        service = SyncService(fetcher=mock_fetcher)
        count = await service.sync_creator(store, creator)
        assert count == 1


class TestSyncCreatorExistingVideos:
    async def test_existing_video_fields_are_updated(self, store):
        creator = await _make_creator_async(store)
        video = Video(
            bvid="BV1aa111a1aA",
            creator_id=creator.id,
            title="旧标题",
            video_url="https://old.url",
            published_at=datetime(2024, 1, 1, 12, 0, 0),
            duration_seconds=200,
        )
        await store.videos.add(video)

        fetched = [
            _make_fetched_video("BV1aa111a1aA", title="新标题", offset=5),
        ]
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=fetched)
        service = SyncService(fetcher=mock_fetcher)
        await service.sync_creator(store, creator)

        updated = store.videos.get(video.id)
        assert updated is not None
        assert updated.title == "新标题"

    async def test_duplicate_sync_does_not_reset_watched_status(self, store):
        creator = await _make_creator_async(store)
        video = Video(
            bvid="BV1aa111a1aA",
            creator_id=creator.id,
            title="标题",
            video_url="https://example.com",
            published_at=datetime(2024, 1, 1, 12, 0, 0),
            duration_seconds=200,
        )
        await store.videos.add(video)
        status_obj = VideoStatus(video_id=video.id, status=1)
        await store.video_statuses.add(status_obj)

        fetched = [_make_fetched_video("BV1aa111a1aA")]
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=fetched)
        service = SyncService(fetcher=mock_fetcher)
        await service.sync_creator(store, creator)

        st = store.video_statuses.filter(video_id=video.id)
        assert len(st) == 1
        assert st[0].status == 1

    async def test_no_duplicate_video_status_created(self, store):
        creator = await _make_creator_async(store)
        existing_video = Video(
            bvid="BV1aa111a1aA",
            creator_id=creator.id,
            title="标题",
            video_url="https://example.com",
            published_at=datetime(2024, 1, 1, 12, 0, 0),
            duration_seconds=200,
        )
        await store.videos.add(existing_video)
        status_obj = VideoStatus(video_id=existing_video.id)
        await store.video_statuses.add(status_obj)

        fetched = [_make_fetched_video("BV1aa111a1aA")]
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=fetched)
        service = SyncService(fetcher=mock_fetcher)
        await service.sync_creator(store, creator)

        statuses = store.video_statuses.filter(video_id=existing_video.id)
        assert len(statuses) == 1


class TestSyncAll:
    async def test_sync_all_returns_sync_task(self, store):
        mock_fetcher = _make_mock_fetcher()
        service = SyncService(fetcher=mock_fetcher)
        task = await service.sync_all(store)

        assert isinstance(task, SyncTask)

    async def test_sync_all_scope_is_all(self, store):
        mock_fetcher = _make_mock_fetcher()
        service = SyncService(fetcher=mock_fetcher)
        task = await service.sync_all(store)

        assert task.scope == "all"

    async def test_sync_all_success_status(self, store):
        creator = await _make_creator_async(store)
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=[_make_fetched_video("BV1aa111a1aA")])
        service = SyncService(fetcher=mock_fetcher)
        task = await service.sync_all(store)

        assert task.status == "completed"

    async def test_sync_all_counts_new_videos(self, store):
        await _make_creator_async(store)
        fetched = [
            _make_fetched_video("BV1aa111a1aA"),
            _make_fetched_video("BV2bb222b2bB"),
        ]
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=fetched)
        service = SyncService(fetcher=mock_fetcher)
        task = await service.sync_all(store)

        assert task.new_videos == 2

    async def test_sync_all_failure_status_and_error_message(self, store):
        await _make_creator_async(store)
        mock_fetcher = _make_mock_fetcher()
        mock_fetcher.fetch_new_videos = AsyncMock(side_effect=Exception("网络连接超时"))
        service = SyncService(fetcher=mock_fetcher)
        task = await service.sync_all(store)

        assert task.status == "failed"
        assert task.error_message is not None
        assert "网络连接超时" in task.error_message

    async def test_sync_all_continues_when_one_creator_fails(self, store):
        await _make_creator_async(store, uid="111")
        await _make_creator_async(store, uid="222")

        mock_fetcher = _make_mock_fetcher()

        async def side_effect(uid: str, **kwargs):
            if uid == "111":
                raise Exception("第一个 creator 抓取失败")
            return [_make_fetched_video("BV2bb222b2bB")]

        mock_fetcher.fetch_new_videos = AsyncMock(side_effect=side_effect)
        service = SyncService(fetcher=mock_fetcher)
        task = await service.sync_all(store)

        assert task.status == "failed"
        assert task.new_videos == 1
        assert "第一个 creator 抓取失败" in (task.error_message or "")

    async def test_sync_all_task_persisted(self, store):
        mock_fetcher = _make_mock_fetcher()
        service = SyncService(fetcher=mock_fetcher)
        task = await service.sync_all(store)

        persisted = store.sync_tasks.get(task.id)
        assert persisted is not None
        assert persisted.scope == "all"


# ──────────────────────────────────────────────
# CreatorService 测试
# ──────────────────────────────────────────────

from app.models.tag import Tag
from app.services.creator_service import CreatorService


class TestCreatorService:
    async def test_create_creator(self, store):
        svc = CreatorService()
        creator = await svc.create_creator(
            store=store,
            name="测试UP",
            profile_url="https://space.bilibili.com/1",
            tag_ids=[],
        )
        assert creator.id > 0
        assert creator.name == "测试UP"
        persisted = store.creators.get(creator.id)
        assert persisted is not None

    async def test_create_creator_with_tags(self, store):
        tag = Tag(name="标签1")
        await store.tags.add(tag)

        svc = CreatorService()
        creator = await svc.create_creator(
            store=store,
            name="测试UP",
            profile_url="https://space.bilibili.com/2",
            tag_ids=[tag.id],
        )
        links = store.creator_tags.filter(creator_id=creator.id)
        assert len(links) == 1
        assert links[0].tag_id == tag.id

    def test_list_creators_empty(self, store):
        svc = CreatorService()
        creators = svc.list_creators(store)
        assert creators == []

    async def test_list_creators_returns_all(self, store):
        await _make_creator_async(store, uid="1")
        await _make_creator_async(store, uid="2")

        svc = CreatorService()
        creators = svc.list_creators(store)
        assert len(creators) == 2

    async def test_update_creator_name(self, store):
        creator = await _make_creator_async(store)
        svc = CreatorService()
        updated = await svc.update_creator(
            store=store, creator=creator,
            name="新名称", alias=None, tag_ids=None,
        )
        assert updated.name == "新名称"
        persisted = store.creators.get(creator.id)
        assert persisted is not None
        assert persisted.name == "新名称"

    async def test_update_creator_enabled(self, store):
        creator = await _make_creator_async(store)
        svc = CreatorService()
        updated = await svc.update_creator(
            store=store, creator=creator,
            name=None, alias=None, tag_ids=None, enabled=False,
        )
        assert updated.enabled is False

    async def test_update_creator_replace_tags(self, store):
        tag1 = Tag(name="A")
        tag2 = Tag(name="B")
        await store.tags.add(tag1)
        await store.tags.add(tag2)

        creator = await _make_creator_async(store)
        svc = CreatorService()
        await svc.update_creator(
            store=store, creator=creator,
            name=None, alias=None, tag_ids=[tag1.id, tag2.id],
        )
        links = store.creator_tags.filter(creator_id=creator.id)
        assert len(links) == 2

    async def test_update_creator_clear_tags(self, store):
        tag = Tag(name="A")
        await store.tags.add(tag)
        creator = await _make_creator_async(store)
        svc = CreatorService()
        await svc.update_creator(
            store=store, creator=creator,
            name=None, alias=None, tag_ids=[tag.id],
        )
        await svc.update_creator(
            store=store, creator=creator,
            name=None, alias=None, tag_ids=[],
        )
        links = store.creator_tags.filter(creator_id=creator.id)
        assert len(links) == 0


# ──────────────────────────────────────────────
# TagService 测试
# ──────────────────────────────────────────────

from app.services.tag_service import TagService


class TestTagService:
    def test_list_tags_empty(self, store):
        svc = TagService()
        assert svc.list_tags(store) == []

    async def test_list_tags_returns_all(self, store):
        svc = TagService()
        await svc.create_tag(store, "标签1")
        await svc.create_tag(store, "标签2")
        tags = svc.list_tags(store)
        assert len(tags) == 2

    def test_list_unwatched_returns_unwatched_videos(self, store, seeded_data):
        svc = TagService()
        videos = svc.list_unwatched_videos_by_tag(store, seeded_data.tag_id)
        assert len(videos) == 1
        assert videos[0].bvid == "BV_seed_001"

    async def test_list_unwatched_excludes_watched_videos(self, store, seeded_data):
        vs_list = store.video_statuses.filter(video_id=seeded_data.video_id)
        if vs_list:
            await store.video_statuses.update(vs_list[0].id, status=1)
        svc = TagService()
        videos = svc.list_unwatched_videos_by_tag(store, seeded_data.tag_id)
        assert len(videos) == 0

    def test_list_unwatched_empty_for_unknown_tag(self, store):
        svc = TagService()
        videos = svc.list_unwatched_videos_by_tag(store, 99999)
        assert videos == []

    async def test_list_unwatched_ordered_by_published_at_desc(self, store, seeded_data):
        video2 = Video(
            bvid="BV_later_001",
            creator_id=seeded_data.creator_id,
            title="更新的视频",
            video_url="https://www.bilibili.com/video/BV_later_001",
            published_at=datetime(2026, 2, 1, 12, 0, 0),
            duration_seconds=400,
        )
        await store.videos.add(video2)
        status2 = VideoStatus(video_id=video2.id)
        await store.video_statuses.add(status2)

        svc = TagService()
        videos = svc.list_unwatched_videos_by_tag(store, seeded_data.tag_id)
        assert len(videos) == 2
        assert videos[0].published_at > videos[1].published_at


# ──────────────────────────────────────────────
# VideoService 测试
# ──────────────────────────────────────────────

from app.services.video_service import VideoService


class TestVideoService:
    async def test_set_status_watched(self, store, seeded_data):
        svc = VideoService()
        vs_list = store.video_statuses.filter(video_id=seeded_data.video_id)
        assert len(vs_list) == 1
        result = await svc.set_status(store, vs_list[0].id, 1)
        assert result is not None
        assert result.status == 1
        assert result.watched_at is not None

    async def test_set_status_unwatched_clears_watched_at(self, store, seeded_data):
        svc = VideoService()
        vs_list = store.video_statuses.filter(video_id=seeded_data.video_id)
        assert len(vs_list) == 1
        await svc.set_status(store, vs_list[0].id, 1)
        result = await svc.set_status(store, vs_list[0].id, 0)
        assert result is not None
        assert result.status == 0
        assert result.watched_at is None

    async def test_set_status_ignored(self, store, seeded_data):
        svc = VideoService()
        vs_list = store.video_statuses.filter(video_id=seeded_data.video_id)
        assert len(vs_list) == 1
        result = await svc.set_status(store, vs_list[0].id, 2)
        assert result is not None
        assert result.status == 2

    async def test_set_status_not_found_returns_none(self, store):
        svc = VideoService()
        result = await svc.set_status(store, 99999, 1)
        assert result is None
