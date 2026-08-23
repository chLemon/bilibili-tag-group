"""视频路由：标记视频状态。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_store
from app.domains.videos.schemas import VideoStatusUpdate
from app.domains.videos.service import VideoService
from app.shared.store import DataStore

router = APIRouter(prefix="/api/videos", tags=["videos"])
_video_svc = VideoService()


@router.patch("/{video_id}/status")
async def update_status(
    video_id: int,
    payload: VideoStatusUpdate,
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    """更新视频状态。"""
    result = await _video_svc.set_status(store, video_id, payload.status)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频不存在")
    return {"video_id": video_id, "status": result.status}
