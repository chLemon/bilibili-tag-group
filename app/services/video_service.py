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

    def set_status(self, db: Session, video_id: int, status_value: int) -> Optional[VideoStatus]:
        """更新视频状态（0=未看, 1=已看, 2=不看）。

        - status=1：同步写入 watched_at（当前 UTC 时间）
        - 其他状态：清空 watched_at
        """
        video_status = db.get(VideoStatus, video_id)
        if video_status is None:
            return None

        video_status.status = status_value
        if status_value == 1:
            video_status.watched_at = _now_utc()
        else:
            video_status.watched_at = None

        db.flush()
        return video_status
