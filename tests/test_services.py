"""测试同步服务：SyncService.sync_creator 和 SyncService.sync_all。"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.fetcher.models import FetchedVideo
from app.models.creator import Creator
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.models.sync_log import SyncLog
from app.services.sync_service import SyncService


def _make_fetched_video(bvid: str, title: str = "默认标题", offset: int = 0) -> FetchedVideo:
    """辅助函数：构造一个 FetchedVideo 测试数据。"""
    return FetchedVideo(
        bvid=bvid,
        title=title,
        video_url=f"https://www.bilibili.com/video/{bvid}",
        published_at=datetime(2024, 1, 1 + offset, 12, 0, 0),
        duration_seconds=300 + offset * 10,
    )


def _make_creator(db_session, uid: str = "12345", enabled: bool = True) -> Creator:
    """辅助函数：在数据库中创建一个 Creator。"""
    creator = Creator(
        name="测试UP主",
        profile_url=f"https://space.bilibili.com/{uid}",
        enabled=enabled,
    )
    db_session.add(creator)
    db_session.flush()
    return creator


class TestSyncCreatorNewVideos:
    """测试 sync_creator 在新视频场景下的行为。"""

    def test_new_videos_are_created(self, db_session):
        """sync_creator 应为新视频创建 Video 记录。"""
        creator = _make_creator(db_session)
        fetched = [_make_fetched_video("BV1aa111a1aA"), _make_fetched_video("BV2bb222b2bB")]

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = fetched

        service = SyncService(fetcher=mock_fetcher)
        count = service.sync_creator(db_session, creator)

        assert count == 2
        videos = db_session.query(Video).filter_by(creator_id=creator.id).all()
        assert len(videos) == 2
        bvids = {v.bvid for v in videos}
        assert bvids == {"BV1aa111a1aA", "BV2bb222b2bB"}

    def test_new_videos_have_video_status_with_watched_false(self, db_session):
        """sync_creator 新增视频时应创建 VideoStatus，默认 watched=False。"""
        creator = _make_creator(db_session)
        fetched = [_make_fetched_video("BV1aa111a1aA")]

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = fetched

        service = SyncService(fetcher=mock_fetcher)
        service.sync_creator(db_session, creator)

        video = db_session.query(Video).filter_by(bvid="BV1aa111a1aA").one()
        assert video.status is not None
        assert video.status.watched is False
        assert video.status.watched_at is None

    def test_returns_count_of_new_videos(self, db_session):
        """sync_creator 返回新增视频数量。"""
        creator = _make_creator(db_session)
        fetched = [
            _make_fetched_video("BV1aa111a1aA"),
            _make_fetched_video("BV2bb222b2bB"),
            _make_fetched_video("BV3cc333c3cC"),
        ]
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = fetched

        service = SyncService(fetcher=mock_fetcher)
        count = service.sync_creator(db_session, creator)

        assert count == 3


class TestSyncCreatorExistingVideos:
    """测试 sync_creator 在重复同步场景下的行为。"""

    def test_existing_video_fields_are_updated(self, db_session):
        """重复同步时应更新视频的标题、链接、发布时间、时长。"""
        creator = _make_creator(db_session)
        # 先创建一个已存在的视频
        existing_video = Video(
            bvid="BV1aa111a1aA",
            creator_id=creator.id,
            title="旧标题",
            video_url="https://www.bilibili.com/video/BV1aa111a1aA",
            published_at=datetime(2023, 1, 1),
            duration_seconds=100,
        )
        db_session.add(existing_video)
        db_session.flush()

        # 新的抓取结果带有更新的信息
        fetched = [FetchedVideo(
            bvid="BV1aa111a1aA",
            title="新标题",
            video_url="https://www.bilibili.com/video/BV1aa111a1aA",
            published_at=datetime(2024, 6, 1),
            duration_seconds=999,
        )]
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = fetched

        service = SyncService(fetcher=mock_fetcher)
        service.sync_creator(db_session, creator)

        db_session.expire(existing_video)
        assert existing_video.title == "新标题"
        assert existing_video.duration_seconds == 999

    def test_duplicate_sync_does_not_reset_watched_status(self, db_session):
        """重复同步不会重置已看状态（watched 保持 True，watched_at 不被清除）。"""
        creator = _make_creator(db_session)
        existing_video = Video(
            bvid="BV1aa111a1aA",
            creator_id=creator.id,
            title="已看视频",
            video_url="https://www.bilibili.com/video/BV1aa111a1aA",
            published_at=datetime(2023, 1, 1),
            duration_seconds=600,
        )
        db_session.add(existing_video)
        db_session.flush()

        watched_time = datetime(2024, 3, 15, 10, 0, 0)
        existing_status = VideoStatus(
            video_id=existing_video.id,
            watched=True,
            watched_at=watched_time,
        )
        db_session.add(existing_status)
        db_session.flush()

        # 再次同步相同视频
        fetched = [_make_fetched_video("BV1aa111a1aA", title="已看视频更新标题")]
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = fetched

        service = SyncService(fetcher=mock_fetcher)
        count = service.sync_creator(db_session, creator)

        # 已存在视频不计入新增数
        assert count == 0

        db_session.expire(existing_status)
        assert existing_status.watched is True
        assert existing_status.watched_at == watched_time

    def test_no_duplicate_video_status_created(self, db_session):
        """重复同步不应创建重复的 VideoStatus。"""
        creator = _make_creator(db_session)
        existing_video = Video(
            bvid="BV1aa111a1aA",
            creator_id=creator.id,
            title="视频",
            video_url="https://www.bilibili.com/video/BV1aa111a1aA",
            published_at=datetime(2023, 1, 1),
            duration_seconds=300,
        )
        db_session.add(existing_video)
        db_session.flush()

        existing_status = VideoStatus(video_id=existing_video.id, watched=False)
        db_session.add(existing_status)
        db_session.flush()

        fetched = [_make_fetched_video("BV1aa111a1aA")]
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = fetched

        service = SyncService(fetcher=mock_fetcher)
        service.sync_creator(db_session, creator)

        statuses = db_session.query(VideoStatus).filter_by(video_id=existing_video.id).all()
        assert len(statuses) == 1


class TestSyncAll:
    """测试 SyncService.sync_all 方法。"""

    def test_sync_all_returns_sync_log(self, db_session):
        """sync_all 返回 SyncLog 对象。"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = []

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        assert isinstance(log, SyncLog)

    def test_sync_all_scope_is_all(self, db_session):
        """sync_all 创建的 SyncLog scope 为 'all'。"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = []

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        assert log.scope == "all"

    def test_sync_all_success_status(self, db_session):
        """成功时 SyncLog.status 为 'success'。"""
        creator = _make_creator(db_session, enabled=True)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = [_make_fetched_video("BV1aa111a1aA")]

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        assert log.status == "success"

    def test_sync_all_only_syncs_enabled_creators(self, db_session):
        """sync_all 只同步 enabled=True 的 Creator。"""
        enabled_creator = _make_creator(db_session, uid="111", enabled=True)
        disabled_creator = _make_creator(db_session, uid="222", enabled=False)
        db_session.flush()

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = []

        service = SyncService(fetcher=mock_fetcher)
        service.sync_all(db_session)

        # fetch_videos 只被调用一次（针对 enabled_creator）
        assert mock_fetcher.fetch_videos.call_count == 1
        call_arg = mock_fetcher.fetch_videos.call_args[0][0]
        # uid 从 profile_url 中提取
        assert "111" in call_arg

    def test_sync_all_counts_new_videos(self, db_session):
        """sync_all 的 SyncLog.new_videos 反映新增视频总数。"""
        _make_creator(db_session, enabled=True)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = [
            _make_fetched_video("BV1aa111a1aA"),
            _make_fetched_video("BV2bb222b2bB"),
        ]

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        assert log.new_videos == 2

    def test_sync_all_failure_status_and_error_message(self, db_session):
        """fetch_videos 抛出异常时 SyncLog 应有 status='failed' 且 error_message 有内容。"""
        _make_creator(db_session, enabled=True)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.side_effect = Exception("网络连接超时")

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        assert log.status == "failed"
        assert log.error_message is not None
        assert "网络连接超时" in log.error_message

    def test_sync_all_failure_sets_finished_at(self, db_session):
        """失败时 SyncLog.finished_at 仍应被设置（在 finally 中处理）。"""
        _make_creator(db_session, enabled=True)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.side_effect = Exception("超时错误")

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        assert log.finished_at is not None

    def test_sync_all_continues_when_one_creator_fails(self, db_session):
        """单个 creator 抓取失败时，sync_all 仍继续处理其他 enabled creator。"""
        _make_creator(db_session, uid="111", enabled=True)
        _make_creator(db_session, uid="222", enabled=True)

        def side_effect(uid: str, **kwargs):
            if uid == "111":
                raise Exception("第一个 creator 抓取失败")
            return [_make_fetched_video("BV2bb222b2bB")]

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.side_effect = side_effect

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        assert mock_fetcher.fetch_videos.call_count == 2
        assert log.status == "failed"
        assert log.new_videos == 1
        assert log.error_message is not None
        assert "creator_id=" in log.error_message
        assert "第一个 creator 抓取失败" in log.error_message

    def test_sync_all_success_sets_finished_at(self, db_session):
        """成功时 SyncLog.finished_at 也应被设置。"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = []

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        assert log.finished_at is not None

    def test_sync_all_log_persisted_to_db(self, db_session):
        """sync_all 创建的 SyncLog 应持久化到数据库中。"""
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_videos.return_value = []

        service = SyncService(fetcher=mock_fetcher)
        log = service.sync_all(db_session)

        db_log = db_session.query(SyncLog).filter_by(id=log.id).one()
        assert db_log is not None
        assert db_log.scope == "all"


# ──────────────────────────────────────────────
# CreatorService 测试
# ──────────────────────────────────────────────

from app.models.tag import Tag
from app.services.creator_service import CreatorService


class TestCreatorService:
    """测试 CreatorService 的 CRUD 功能。"""

    def test_create_creator(self, db_session):
        """create_creator 应返回带有正确字段的 Creator 对象。"""
        svc = CreatorService()
        creator = svc.create_creator(
            db_session,
            name="测试UP",
            profile_url="https://space.bilibili.com/12345",
            tag_ids=[],
        )
        assert creator.id is not None
        assert creator.name == "测试UP"
        assert creator.enabled is True

    def test_create_creator_with_tags(self, db_session):
        """create_creator 可同时关联标签。"""
        tag = Tag(name="技术")
        db_session.add(tag)
        db_session.flush()

        svc = CreatorService()
        creator = svc.create_creator(
            db_session,
            name="技术UP",
            profile_url="https://space.bilibili.com/99999",
            tag_ids=[tag.id],
        )
        assert len(creator.tags) == 1
        assert creator.tags[0].id == tag.id

    def test_list_creators_empty(self, db_session):
        svc = CreatorService()
        assert svc.list_creators(db_session) == []

    def test_list_creators_returns_all(self, db_session):
        svc = CreatorService()
        svc.create_creator(db_session, "A", "https://space.bilibili.com/1", [])
        svc.create_creator(db_session, "B", "https://space.bilibili.com/2", [])
        assert len(svc.list_creators(db_session)) == 2

    def test_update_creator_name(self, db_session):
        svc = CreatorService()
        creator = svc.create_creator(db_session, "旧名", "https://space.bilibili.com/7777", [])
        svc.update_creator(db_session, creator, name="新名", enabled=None, tag_ids=None)
        assert creator.name == "新名"

    def test_update_creator_enabled(self, db_session):
        svc = CreatorService()
        creator = svc.create_creator(db_session, "UP", "https://space.bilibili.com/8888", [])
        svc.update_creator(db_session, creator, name=None, enabled=False, tag_ids=None)
        assert creator.enabled is False

    def test_update_creator_replace_tags(self, db_session):
        """更新 tag_ids 应完整替换旧标签。"""
        tag1 = Tag(name="旧标签")
        tag2 = Tag(name="新标签")
        db_session.add_all([tag1, tag2])
        db_session.flush()

        svc = CreatorService()
        creator = svc.create_creator(
            db_session, "UP", "https://space.bilibili.com/6666", [tag1.id]
        )
        assert len(creator.tags) == 1

        svc.update_creator(db_session, creator, name=None, enabled=None, tag_ids=[tag2.id])
        assert len(creator.tags) == 1
        assert creator.tags[0].id == tag2.id

    def test_update_creator_clear_tags(self, db_session):
        """tag_ids=[] 时清空所有标签关联。"""
        tag = Tag(name="要移除的标签")
        db_session.add(tag)
        db_session.flush()

        svc = CreatorService()
        creator = svc.create_creator(
            db_session, "UP", "https://space.bilibili.com/5555", [tag.id]
        )
        svc.update_creator(db_session, creator, name=None, enabled=None, tag_ids=[])
        assert creator.tags == []


# ──────────────────────────────────────────────
# TagService 测试
# ──────────────────────────────────────────────

from app.services.tag_service import TagService


class TestTagService:
    """测试 TagService 的标签查询与未看视频查询。"""

    def _seed_creator_with_tag_and_video(self, db_session, watched: bool = False):
        """辅助：创建标签、UP 主、视频和状态，返回 (tag, video)。"""
        tag = Tag(name="精品")
        db_session.add(tag)
        db_session.flush()

        creator = Creator(name="精品UP", profile_url="https://space.bilibili.com/2222")
        creator.tags.append(tag)
        db_session.add(creator)
        db_session.flush()

        video = Video(
            bvid="BV_svc_001",
            creator_id=creator.id,
            title="服务层测试视频",
            video_url="https://www.bilibili.com/video/BV_svc_001",
            published_at=datetime(2026, 3, 1),
            duration_seconds=600,
        )
        db_session.add(video)
        db_session.flush()

        status = VideoStatus(video_id=video.id, watched=watched)
        db_session.add(status)
        db_session.flush()

        return tag, video

    def test_list_tags_empty(self, db_session):
        svc = TagService()
        assert svc.list_tags(db_session) == []

    def test_list_tags_returns_all(self, db_session):
        db_session.add_all([Tag(name="A"), Tag(name="B")])
        db_session.flush()
        svc = TagService()
        assert len(svc.list_tags(db_session)) == 2

    def test_list_unwatched_returns_unwatched_videos(self, db_session):
        """list_unwatched_videos_by_tag 返回未看视频。"""
        tag, video = self._seed_creator_with_tag_and_video(db_session, watched=False)
        svc = TagService()
        result = svc.list_unwatched_videos_by_tag(db_session, tag.id)
        assert len(result) == 1
        assert result[0].id == video.id
        assert result[0].creator_name == "精品UP"

    def test_list_unwatched_excludes_watched_videos(self, db_session):
        """list_unwatched_videos_by_tag 不返回已看视频。"""
        tag, _video = self._seed_creator_with_tag_and_video(db_session, watched=True)
        svc = TagService()
        result = svc.list_unwatched_videos_by_tag(db_session, tag.id)
        assert result == []

    def test_list_unwatched_empty_for_unknown_tag(self, db_session):
        svc = TagService()
        assert svc.list_unwatched_videos_by_tag(db_session, 99999) == []

    def test_list_unwatched_ordered_by_published_at_desc(self, db_session):
        """未看视频应按 published_at 倒序排列。"""
        tag = Tag(name="顺序测试")
        db_session.add(tag)
        db_session.flush()

        creator = Creator(name="时间UP", profile_url="https://space.bilibili.com/3333")
        creator.tags.append(tag)
        db_session.add(creator)
        db_session.flush()

        for i, dt in enumerate([
            datetime(2026, 1, 1),
            datetime(2026, 3, 1),
            datetime(2026, 2, 1),
        ]):
            v = Video(
                bvid=f"BV_order_{i}",
                creator_id=creator.id,
                title=f"视频{i}",
                video_url=f"https://www.bilibili.com/video/BV_order_{i}",
                published_at=dt,
                duration_seconds=100,
            )
            db_session.add(v)
            db_session.flush()
            db_session.add(VideoStatus(video_id=v.id, watched=False))
        db_session.flush()

        svc = TagService()
        result = svc.list_unwatched_videos_by_tag(db_session, tag.id)
        dates = [r.published_at for r in result]
        assert dates == sorted(dates, reverse=True)


# ──────────────────────────────────────────────
# VideoService 测试
# ──────────────────────────────────────────────

from app.services.video_service import VideoService


class TestVideoService:
    """测试 VideoService 的已看状态管理。"""

    def _seed_video_with_status(self, db_session, watched: bool = False):
        """辅助：创建视频和状态，返回 (video, status)。"""
        creator = Creator(name="UP", profile_url="https://space.bilibili.com/4444")
        db_session.add(creator)
        db_session.flush()

        video = Video(
            bvid="BV_vsvc_001",
            creator_id=creator.id,
            title="VideoService 测试",
            video_url="https://www.bilibili.com/video/BV_vsvc_001",
            published_at=datetime(2026, 1, 15),
            duration_seconds=400,
        )
        db_session.add(video)
        db_session.flush()

        status = VideoStatus(video_id=video.id, watched=watched)
        db_session.add(status)
        db_session.flush()

        return video, status

    def test_mark_watched_true(self, db_session):
        """mark_watched(watched=True) 应设置 watched=True 并写入 watched_at。"""
        video, status = self._seed_video_with_status(db_session, watched=False)
        svc = VideoService()
        result = svc.mark_watched(db_session, video.id, watched=True)
        assert result is not None
        assert result.watched is True
        assert result.watched_at is not None

    def test_mark_watched_false_clears_watched_at(self, db_session):
        """mark_watched(watched=False) 应清空 watched_at。"""
        video, status = self._seed_video_with_status(db_session, watched=True)
        svc = VideoService()
        svc.mark_watched(db_session, video.id, watched=True)  # 先设置 watched_at
        result = svc.mark_watched(db_session, video.id, watched=False)
        assert result.watched is False
        assert result.watched_at is None

    def test_mark_watched_not_found_returns_none(self, db_session):
        """不存在的 video_id 应返回 None。"""
        svc = VideoService()
        result = svc.mark_watched(db_session, video_id=99999, watched=True)
        assert result is None
