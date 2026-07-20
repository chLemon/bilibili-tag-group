"""标签路由：标签列表与标签下未看视频。"""
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import get_store
from app.schemas.tag import TagCreate, TagRead
from app.schemas.video import VideoRead
from app.services.tag_service import TagService
from app.store.store import DataStore

router = APIRouter(prefix="/api/tags", tags=["tags"])
_tag_svc = TagService()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TagRead)
async def create_tag(
    payload: TagCreate,
    store: Annotated[DataStore, Depends(get_store)],
) -> TagRead:
    """创建新标签。"""
    tag = await _tag_svc.create_tag(store, payload.name)
    return TagRead(id=tag.id, name=tag.name)


@router.get("", response_model=list[TagRead])
def list_tags(
    store: Annotated[DataStore, Depends(get_store)],
) -> list[TagRead]:
    """返回所有标签列表。"""
    tags = _tag_svc.list_tags(store)
    return [TagRead(id=t.id, name=t.name) for t in tags]


@router.get("/untagged/videos", response_model=list[VideoRead])
def list_untagged_videos(
    store: Annotated[DataStore, Depends(get_store)],
) -> list[VideoRead]:
    """返回所有无标签 UP 主的未看视频，按发布时间倒序。"""
    return _tag_svc.list_unwatched_videos_untagged(store)


@router.get("/{tag_id}/videos", response_model=list[VideoRead])
def list_tag_videos(
    tag_id: int,
    store: Annotated[DataStore, Depends(get_store)],
) -> list[VideoRead]:
    """返回指定标签下所有 UP 主的未看视频，按发布时间倒序。"""
    return _tag_svc.list_unwatched_videos_by_tag(store, tag_id)
