"""数据中心：聚合所有 JsonRepo 实例。"""
from __future__ import annotations

from pathlib import Path

from app.models.creator import Creator
from app.models.creator_tag import CreatorTag
from app.models.sync_task import SyncTask
from app.models.tag import Tag
from app.models.tag_sync_config import TagSyncConfig
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.store.repo import JsonRepo


class DataStore:
    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)

        self.creators = JsonRepo[Creator](Creator, data_dir / "creators.json")
        self.tags = JsonRepo[Tag](Tag, data_dir / "tags.json")
        self.creator_tags = JsonRepo[CreatorTag](CreatorTag, data_dir / "creator_tags.json")
        self.videos = JsonRepo[Video](Video, data_dir / "videos.json")
        self.video_statuses = JsonRepo[VideoStatus](VideoStatus, data_dir / "video_statuses.json")
        self.sync_tasks = JsonRepo[SyncTask](SyncTask, data_dir / "sync_tasks.json")
        self.tag_sync_configs = JsonRepo[TagSyncConfig](
            TagSyncConfig, data_dir / "tag_sync_configs.json"
        )
