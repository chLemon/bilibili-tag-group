"""Task 1 模型测试：验证字段命名和业务语义符合规格。"""
from datetime import datetime, timezone

from app.models.creator import Creator
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_status import VideoStatus


def test_video_status_defaults_to_unwatched():
    """新建的 VideoStatus 默认 status=0。"""
    status = VideoStatus(id=1, video_id=1)
    assert status.status == 0
    assert status.watched_at is None


def test_creator_fields():
    """Creator 具备 id, name, profile_url, enabled 字段。"""
    creator = Creator(
        id=1,
        name="影视飓风",
        profile_url="https://space.bilibili.com/946974",
    )
    assert creator.id == 1
    assert creator.name == "影视飓风"
    assert creator.profile_url == "https://space.bilibili.com/946974"
    assert creator.enabled is True


def test_creator_can_be_disabled():
    """Creator 可以设置 enabled=False。"""
    creator = Creator(
        id=1,
        name="测试UP",
        profile_url="https://space.bilibili.com/3",
        enabled=False,
    )
    assert creator.enabled is False


def test_video_fields():
    """Video 具备规格要求的所有字段。"""
    published = datetime.fromisoformat("2026-04-18T12:00:00")
    video = Video(
        id=1,
        bvid="BV1abc12345",
        creator_id=10,
        title="测试视频",
        video_url="https://www.bilibili.com/video/BV1abc12345",
        published_at=published,
        duration_seconds=300,
    )
    assert video.id == 1
    assert video.bvid == "BV1abc12345"
    assert video.creator_id == 10
    assert video.title == "测试视频"
    assert video.video_url == "https://www.bilibili.com/video/BV1abc12345"
    assert video.published_at == published
    assert video.duration_seconds == 300


def test_video_status_no_notes_field():
    """VideoStatus 不应有 notes 字段（第一版不做笔记功能）。"""
    assert not hasattr(VideoStatus, "notes"), "VideoStatus 不应包含 notes 字段"


def test_tag_belongs_to_creator_not_video():
    """标签通过 Creator 关联，不直接关联 Video。"""
    assert not hasattr(Tag, "videos"), "Tag 不应直接关联 videos，标签属于 UP 主"
