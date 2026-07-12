"""Task 1 模型测试：验证字段命名和业务语义符合规格。"""
from datetime import datetime, timezone

from app.models.creator import Creator
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.models.sync_log import SyncLog


def test_video_status_defaults_to_unwatched(db_session):
    """新建的 VideoStatus 默认 status=0。"""
    creator = Creator(name="测试UP", profile_url="https://space.bilibili.com/1")
    db_session.add(creator)
    db_session.flush()

    video = Video(
        bvid="BV1xx411c7mD",
        creator_id=creator.id,
        title="视频 1",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        published_at=datetime.fromisoformat("2026-04-18T10:00:00"),
        duration_seconds=600,
    )
    db_session.add(video)
    db_session.flush()

    status = VideoStatus(video_id=video.id)
    db_session.add(status)
    db_session.commit()

    assert status.status == 0
    assert status.watched_at is None


def test_creator_can_have_multiple_tags(db_session):
    """一个 Creator 可以关联多个标签。"""
    creator = Creator(name="测试UP", profile_url="https://space.bilibili.com/2")
    tag1 = Tag(name="must-watch")
    tag2 = Tag(name="deep-study")
    creator.tags.extend([tag1, tag2])
    db_session.add(creator)
    db_session.commit()

    assert {tag.name for tag in creator.tags} == {"must-watch", "deep-study"}


def test_creator_fields(db_session):
    """Creator 具备 id, name, profile_url, enabled 字段。"""
    creator = Creator(name="影视飓风", profile_url="https://space.bilibili.com/946974")
    db_session.add(creator)
    db_session.commit()

    assert creator.id is not None
    assert creator.name == "影视飓风"
    assert creator.profile_url == "https://space.bilibili.com/946974"
    assert creator.enabled is True  # 默认启用


def test_creator_can_be_disabled(db_session):
    """Creator 可以设置 enabled=False 停用同步。"""
    creator = Creator(
        name="测试UP",
        profile_url="https://space.bilibili.com/3",
        enabled=False,
    )
    db_session.add(creator)
    db_session.commit()

    assert creator.enabled is False


def test_video_fields(db_session):
    """Video 具备规格要求的所有字段。"""
    creator = Creator(name="测试UP", profile_url="https://space.bilibili.com/4")
    db_session.add(creator)
    db_session.flush()

    published = datetime.fromisoformat("2026-04-18T12:00:00")
    video = Video(
        bvid="BV1abc12345",
        creator_id=creator.id,
        title="测试视频",
        video_url="https://www.bilibili.com/video/BV1abc12345",
        published_at=published,
        duration_seconds=300,
    )
    db_session.add(video)
    db_session.commit()

    assert video.id is not None
    assert video.bvid == "BV1abc12345"
    assert video.creator_id == creator.id
    assert video.title == "测试视频"
    assert video.video_url == "https://www.bilibili.com/video/BV1abc12345"
    assert video.published_at == published
    assert video.duration_seconds == 300


def test_sync_log_fields(db_session):
    """SyncLog 使用 scope/new_videos/finished_at 命名。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    log = SyncLog(
        scope="all",
        status="success",
        new_videos=5,
        error_message=None,
        started_at=now,
        finished_at=now,
    )
    db_session.add(log)
    db_session.commit()

    assert log.id is not None
    assert log.scope == "all"
    assert log.status == "success"
    assert log.new_videos == 5
    assert log.error_message is None
    assert log.started_at == now
    assert log.finished_at == now


def test_sync_log_error_message(db_session):
    """SyncLog 可以存储错误信息，finished_at 可为空。"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    log = SyncLog(
        scope="creator:123",
        status="failed",
        new_videos=0,
        error_message="连接超时",
        started_at=now,
        finished_at=None,
    )
    db_session.add(log)
    db_session.commit()

    assert log.error_message == "连接超时"
    assert log.finished_at is None


def test_video_status_no_notes_field(db_session):
    """VideoStatus 不应有 notes 字段（第一版不做笔记功能）。"""
    assert not hasattr(VideoStatus, "notes"), "VideoStatus 不应包含 notes 字段"


def test_tag_belongs_to_creator_not_video(db_session):
    """标签通过 Creator 关联，不直接关联 Video。"""
    # Tag 没有直接连接 Video 的关系
    assert not hasattr(Tag, "videos"), "Tag 不应直接关联 videos，标签属于 UP 主"
