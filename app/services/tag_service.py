"""标签服务：查询标签列表及标签下的未看视频。"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.creator import Creator
from app.models.creator_tag import CreatorTag
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.schemas.video import VideoRead


class TagService:
    """标签业务逻辑：聚合标签与未看视频信息。"""

    def list_tags(self, db: Session) -> list[Tag]:
        """返回所有标签（按 id 升序）。"""
        return db.query(Tag).order_by(Tag.id).all()

    def list_unwatched_videos_by_tag(self, db: Session, tag_id: int) -> list[VideoRead]:
        """查询某个标签下所有 UP 主的未看视频，按发布时间倒序。

        标签属于 Creator，视频通过 Creator 关联到标签。
        只返回 watched=False 的视频，并附带 creator 名称。

        参数：
            db: SQLAlchemy Session
            tag_id: 要查询的标签 ID

        返回：
            VideoRead 列表（已按 published_at 倒序排列）
        """
        rows = (
            db.query(Video, Creator.name.label("creator_name"))
            .join(Creator, Video.creator_id == Creator.id)
            .join(CreatorTag, CreatorTag.creator_id == Creator.id)
            .join(VideoStatus, VideoStatus.video_id == Video.id)
            .filter(CreatorTag.tag_id == tag_id)
            .filter(VideoStatus.watched.is_(False))
            .order_by(Video.published_at.desc())
            .all()
        )

        result: list[VideoRead] = []
        for video, creator_name in rows:
            result.append(
                VideoRead(
                    id=video.id,
                    bvid=video.bvid,
                    title=video.title,
                    creator_id=video.creator_id,
                    creator_name=creator_name,
                    video_url=video.video_url,
                    published_at=video.published_at,
                    duration_seconds=video.duration_seconds,
                )
            )
        return result
