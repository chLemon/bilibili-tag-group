"""视频服务：管理本地视频观看状态。"""
from __future__ import annotations

from datetime import datetime, timezone

from app.models.video_status import VideoStatus
from app.store.store import DataStore


def _now_utc() -> datetime:
    """返回当前 UTC 时间（naive datetime）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class VideoService:
    """视频本地状态业务逻辑。"""

    async def set_status(self, store: DataStore, video_id: int, status_value: int) -> VideoStatus | None:
        """更新视频状态（0=未看, 1=已看, 2=不看）。"""
        vs = store.video_statuses.get(video_id)
        if vs is None:
            return None

        updates: dict[str, object] = {"status": status_value}
        if status_value == 1:
            updates["watched_at"] = _now_utc()
        else:
            updates["watched_at"] = None
        await store.video_statuses.update(vs.id, **updates)
        return store.video_statuses.get(vs.id)

    async def batch_set_status_by_creator(
        self, store: DataStore, creator_id: int, status_value: int
    ) -> int:
        """批量将某个 UP 主的所有未看视频标记为指定状态，返回更新行数。"""
        watched_at = _now_utc() if status_value == 1 else None
        all_video_statuses = store.video_statuses.all()
        all_videos = store.videos.filter(creator_id=creator_id)
        creator_video_ids = {v.id for v in all_videos}

        count = 0
        for vs in all_video_statuses:
            if vs.video_id not in creator_video_ids:
                continue
            if vs.status != 0:
                continue
            updates: dict[str, object] = {"status": status_value, "watched_at": watched_at}
            await store.video_statuses.update(vs.id, **updates)
            count += 1
        return count
