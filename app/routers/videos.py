"""视频路由：标记已看状态。"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.video import VideoWatchedUpdate
from app.services.video_service import VideoService

router = APIRouter(prefix="/api/videos", tags=["videos"])
_video_svc = VideoService()


@router.patch("/{video_id}/watched")
def mark_watched(
    video_id: int,
    payload: VideoWatchedUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """标记或取消标记视频已看状态。

    - watched=True：记录为已看，同时写入 watched_at
    - watched=False：标记回未看，清空 watched_at
    """
    result = _video_svc.mark_watched(db, video_id, payload.watched)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频不存在")
    return {"video_id": video_id, "watched": result.watched}
