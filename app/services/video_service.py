"""视频服务：管理本地视频观看状态。"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.video_status import VideoStatus


def _now_utc() -> datetime:
    """返回当前 UTC 时间（naive datetime）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class VideoService:
    """视频本地状态业务逻辑。

    只负责 watched / watched_at 的读写，不修改视频公开信息。
    """

    def mark_watched(self, db: Session, video_id: int, watched: bool) -> Optional[VideoStatus]:
        """更新视频的已看状态。

        - watched=True：同步写入 watched_at（当前 UTC 时间）
        - watched=False：清空 watched_at

        参数：
            db: SQLAlchemy Session
            video_id: 视频 ID
            watched: 目标已看状态

        返回：
            更新后的 VideoStatus 对象，视频不存在时返回 None
        """
        status = db.get(VideoStatus, video_id)
        if status is None:
            return None

        status.watched = watched
        if watched:
            status.watched_at = _now_utc()
        else:
            status.watched_at = None

        db.flush()
        return status
