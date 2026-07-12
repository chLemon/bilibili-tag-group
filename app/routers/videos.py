"""视频路由：标记视频状态。"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.video import VideoStatusUpdate
from app.services.video_service import VideoService

router = APIRouter(prefix="/api/videos", tags=["videos"])
_video_svc = VideoService()


@router.patch("/{video_id}/status")
def update_status(
    video_id: int,
    payload: VideoStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """更新视频状态。

    - status=0：标记为未看
    - status=1：标记为已看，同时写入 watched_at
    - status=2：标记为不看
    """
    result = _video_svc.set_status(db, video_id, payload.status)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频不存在")
    return {"video_id": video_id, "status": result.status}
