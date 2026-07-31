"""视频服务：管理本地视频观看状态。"""
from __future__ import annotations

from app.models.creator import Creator
from app.models.video_status import VideoStatus
from app.schemas.video import VideoDetail
from app.store.store import DataStore
from app.utils.time import now_utc as _now_utc


class VideoService:
    """视频本地状态业务逻辑。"""

    def list_video_details_by_creator(
        self, store: DataStore, creator: Creator
    ) -> list[VideoDetail]:
        """返回指定 UP 主的所有视频（含已看状态），按发布时间倒序。"""
        videos_list = store.videos.filter(creator_id=creator.id)
        status_map = {s.video_id: s.status for s in store.video_statuses.all()}
        videos_list.sort(key=lambda v: v.published_at, reverse=True)
        return [
            VideoDetail(
                id=video.id,
                bvid=video.bvid,
                title=video.title,
                creator_id=video.creator_id,
                creator_name=creator.name,
                creator_alias=creator.alias,
                creator_avatar_url=creator.avatar_url,
                video_url=video.video_url,
                published_at=video.published_at,
                duration_seconds=video.duration_seconds,
                cover_url=video.cover_url,
                status=status_map.get(video.id, 0),
            )
            for video in videos_list
        ]

    async def set_status(
        self, store: DataStore, video_id: int, status_value: int
    ) -> VideoStatus | None:
        """更新视频状态（0=未看, 1=已看, 2=不看）。video_id 为 Video.id。"""
        matches = store.video_statuses.filter(video_id=video_id)
        if not matches:
            return None
        vs = matches[0]

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
        """批量将某个 UP 主的所有视频标记为指定状态，返回更新行数。

        对所有状态的视频生效（而非仅未看），否则"一键未看"对
        已看/不看的视频不生效，与前端按钮语义不符。
        """
        watched_at = _now_utc() if status_value == 1 else None
        creator_video_ids = {v.id for v in store.videos.filter(creator_id=creator_id)}
        target_ids = {
            vs.id
            for vs in store.video_statuses.all()
            if vs.video_id in creator_video_ids
        }
        return await store.video_statuses.bulk_update(
            target_ids, status=status_value, watched_at=watched_at
        )
