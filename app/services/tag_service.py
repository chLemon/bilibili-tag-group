"""标签服务：查询标签列表及标签下的未看视频。"""
from __future__ import annotations

from app.models.creator import Creator
from app.models.creator_tag import CreatorTag
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_status import VideoStatus
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

    def list_unwatched_videos_by_tag(self, store: DataStore, tag_id: int) -> list[VideoRead]:
        """查询某个标签下所有 UP 主的未看视频，按发布时间倒序。"""
        creator_links = store.creator_tags.filter(tag_id=tag_id)
        creator_ids = {link.creator_id for link in creator_links}
        all_creators = {c.id: c for c in store.creators.all()}
        all_videos = store.videos.all()
        statuses = {s.video_id: s for s in store.video_statuses.filter(status=0)}

        results: list[VideoRead] = []
        for video in all_videos:
            if video.creator_id not in creator_ids:
                continue
            if video.id not in statuses:
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

    def list_unwatched_videos_untagged(self, store: DataStore) -> list[VideoRead]:
        """查询所有无标签 UP 主的未看视频，按发布时间倒序。"""
        all_creator_tags = store.creator_tags.all()
        tagged_ids = {link.creator_id for link in all_creator_tags}
        all_creators = {c.id: c for c in store.creators.all()}
        all_videos = store.videos.all()
        statuses = {s.video_id: s for s in store.video_statuses.filter(status=0)}

        results: list[VideoRead] = []
        for video in all_videos:
            if video.creator_id in tagged_ids:
                continue
            if video.id not in statuses:
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
