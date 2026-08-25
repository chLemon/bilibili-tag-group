"""视频路由：标记视频状态。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_store
from app.domains.videos.schemas import VideoBatchStatusUpdate, VideoStatusUpdate
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


@router.patch("/batch/status")
async def batch_update_status(
    payload: VideoBatchStatusUpdate,
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    """按 video_ids 批量标记视频状态。

    供标签视图"一键已看/不看"按可见范围批量标记——隐藏充电视频时
    前端只传当前可见视频的 id，被过滤的充电视频不受影响。
    """
    count = await _video_svc.batch_set_status_by_ids(
        store, payload.video_ids, payload.status
    )
    return {"status": payload.status, "updated_count": count}
