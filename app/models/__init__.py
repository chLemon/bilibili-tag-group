# 导出所有 ORM 模型，确保 Base.metadata 包含全部表定义
from app.models.creator import Creator
from app.models.tag import Tag
from app.models.creator_tag import CreatorTag
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.models.sync_log import SyncLog
from app.models.tag_sync_config import TagSyncConfig
from app.models.sync_task import SyncTask

__all__ = [
    "Creator",
    "Tag",
    "CreatorTag",
    "Video",
    "VideoStatus",
    "SyncLog",
    "SyncTask",
    "TagSyncConfig",
]
