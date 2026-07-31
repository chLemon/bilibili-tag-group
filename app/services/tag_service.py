"""标签服务：查询标签列表及标签下的未看视频。"""
from __future__ import annotations

from collections.abc import Callable

from app.models.tag import Tag
from app.schemas.video import VideoRead
from app.store.store import DataStore


class TagService:
    """标签业务逻辑：聚合标签与未看视频信息。"""

    async def create_tag(self, store: DataStore, name: str) -> Tag:
        """创建新标签。"""
        tag = Tag(name=name.strip())
        await store.tags.add(tag)
        return tag

    def list_tags(self, store: DataStore) -> list[Tag]:
        """返回所有标签（按 id 升序）。"""
        return sorted(store.tags.all(), key=lambda t: t.id)

    def unwatched_count_by_tag(self, store: DataStore) -> dict[int, int]:
        """统计每个标签下的未看视频数（tag_id -> count）。"""
        unwatched_video_ids = {s.video_id for s in store.video_statuses.filter(status=0)}
        count_by_creator: dict[int, int] = {}
        for v in store.videos.all():
            if v.id in unwatched_video_ids:
                count_by_creator[v.creator_id] = count_by_creator.get(v.creator_id, 0) + 1
        counts: dict[int, int] = {}
        for link in store.creator_tags.all():
            n = count_by_creator.get(link.creator_id, 0)
            if n:
                counts[link.tag_id] = counts.get(link.tag_id, 0) + n
        return counts

    def list_unwatched_videos_by_tag(self, store: DataStore, tag_id: int) -> list[VideoRead]:
        """查询某个标签下所有 UP 主的未看视频，按发布时间倒序。"""
        creator_ids = {link.creator_id for link in store.creator_tags.filter(tag_id=tag_id)}
        return self._list_unwatched(store, lambda cid: cid in creator_ids)

    def list_unwatched_videos_untagged(self, store: DataStore) -> list[VideoRead]:
        """查询所有无标签 UP 主的未看视频，按发布时间倒序。"""
        tagged_ids = {link.creator_id for link in store.creator_tags.all()}
        return self._list_unwatched(store, lambda cid: cid not in tagged_ids)

    def _list_unwatched(
        self, store: DataStore, creator_pred: Callable[[int], bool]
    ) -> list[VideoRead]:
        """按 UP 主谓词筛选未看视频，按发布时间倒序。"""
        all_creators = {c.id: c for c in store.creators.all()}
        unwatched_ids = {s.video_id for s in store.video_statuses.filter(status=0)}

        results: list[VideoRead] = []
        for video in store.videos.all():
            if not creator_pred(video.creator_id):
                continue
            if video.id not in unwatched_ids:
                continue
            creator = all_creators.get(video.creator_id)
            results.append(VideoRead(
                id=video.id,
                bvid=video.bvid,
                title=video.title,
                creator_id=video.creator_id,
                creator_name=creator.name if creator else "",
                creator_alias=creator.alias if creator else None,
                creator_avatar_url=creator.avatar_url if creator else None,
                video_url=video.video_url,
                cover_url=video.cover_url,
                published_at=video.published_at,
                duration_seconds=video.duration_seconds,
            ))

        results.sort(key=lambda v: v.published_at, reverse=True)
        return results
