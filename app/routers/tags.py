"""标签路由：标签列表与标签下未看视频。"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.tag import TagCreate, TagRead
from app.schemas.video import VideoRead
from app.services.tag_service import TagService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tags", tags=["tags"])
_tag_svc = TagService()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TagRead)
def create_tag(
    payload: TagCreate,
    db: Annotated[Session, Depends(get_db)],
) -> TagRead:
    """创建新标签。"""
    tag = _tag_svc.create_tag(db, payload.name)
    return TagRead(id=tag.id, name=tag.name)


@router.get("", response_model=list[TagRead])
def list_tags(
    db: Annotated[Session, Depends(get_db)],
) -> list[TagRead]:
    """返回所有标签列表。"""
    tags = _tag_svc.list_tags(db)
    return [TagRead(id=t.id, name=t.name) for t in tags]


@router.get("/untagged/videos", response_model=list[VideoRead])
def list_untagged_videos(
    db: Annotated[Session, Depends(get_db)],
) -> list[VideoRead]:
    """返回所有无标签 UP 主的未看视频，按发布时间倒序。"""
    return _tag_svc.list_unwatched_videos_untagged(db)


@router.get("/{tag_id}/videos", response_model=list[VideoRead])
def list_tag_videos(
    tag_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> list[VideoRead]:
    """返回指定标签下所有 UP 主的未看视频，按发布时间倒序。

    只返回 watched=False 的视频，并包含 creator 名称。
    """
    return _tag_svc.list_unwatched_videos_by_tag(db, tag_id)
