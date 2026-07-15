"""UP 主管理路由。"""
import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.config import settings
from app.dependencies import get_db
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher, FetchError
from app.models.creator import Creator
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.schemas.creator import (
    BatchCreatorRequest,
    BatchCreatorResponse,
    BatchCreatorResult,
    CreatorCreate,
    CreatorRead,
    CreatorUpdate,
)
from app.schemas.video import VideoDetail, VideoStatusUpdate
from app.services.creator_service import CreatorService
from app.services.video_service import VideoService

router = APIRouter(prefix="/api/creators", tags=["creators"])
_creator_svc = CreatorService()
_video_svc = VideoService()
_fetcher = PlaywrightBilibiliFetcher(cookie=settings.bilibili_cookie or None)


_UID_RE = re.compile(r"space\.bilibili\.com/(\d+)")


def _uid_from_profile_url(profile_url: str) -> str:
    """从 B 站主页 URL 中提取 uid；若已是纯数字 uid 则直接返回。"""
    trimmed = profile_url.strip()
    if trimmed.isdigit():
        return trimmed
    m = _UID_RE.search(trimmed)
    if m:
        return m.group(1)
    raise ValueError(f"无法从 URL 中提取 UID：{profile_url}")


def _to_creator_read(creator) -> CreatorRead:
    """将 ORM Creator 对象转换为 CreatorRead schema，附带视频统计数据。"""
    videos = creator.videos or []
    unwatched = sum(1 for v in videos if v.status is None or v.status.status == 0)
    return CreatorRead(
        id=creator.id,
        name=creator.name,
        alias=creator.alias,
        profile_url=creator.profile_url,
        avatar_url=creator.avatar_url,
        tag_ids=[tag.id for tag in creator.tags],
        video_count=creator.video_count or 0,
        synced_video_count=len(videos),
        unwatched_count=unwatched,
        last_synced_at=creator.last_synced_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatorRead)
def create_creator(
    payload: CreatorCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CreatorRead:
    """添加新 UP 主（可同时关联标签）。"""
    creator = _creator_svc.create_creator(
        db=db,
        name=payload.name,
        profile_url=payload.profile_url,
        tag_ids=payload.tag_ids,
        avatar_url=payload.avatar_url,
        alias=payload.alias,
    )
    return _to_creator_read(creator)


@router.post("/batch", status_code=status.HTTP_200_OK, response_model=BatchCreatorResponse)
def batch_create_creators(
    payload: BatchCreatorRequest,
    db: Annotated[Session, Depends(get_db)],
) -> BatchCreatorResponse:
    """批量添加 UP 主。

    每行格式：uid,标签1,标签2
    前端解析后传入 JSON，后端逐条解析名称、匹配/创建标签并入库。
    """
    results: list[BatchCreatorResult] = []
    for item in payload.items:
        try:
            profile_url = f"https://space.bilibili.com/{item.uid}"
            if item.name:
                creator_name = item.name
                avatar_url = None
            else:
                try:
                    info = _fetcher.fetch_creator_info(item.uid)
                    creator_name = info["name"]
                    avatar_url = info.get("avatar_url")
                except FetchError as exc:
                    logger.exception("批量添加-获取 UP 主信息失败 uid=%s", item.uid)
                    results.append(BatchCreatorResult(
                        uid=item.uid, success=False, error=f"获取 UP 主信息失败：{exc}"
                    ))
                    continue

            tags = _creator_svc.find_or_create_tags(db, item.tag_names)
            tag_ids = [t.id for t in tags]

            creator = _creator_svc.create_creator(
                db=db,
                name=creator_name,
                profile_url=profile_url,
                tag_ids=tag_ids,
                avatar_url=avatar_url,
            )
            results.append(BatchCreatorResult(
                uid=item.uid, success=True, creator=_to_creator_read(creator)
            ))
        except Exception as exc:
            logger.exception("批量添加 UP 主失败 uid=%s", item.uid)
            results.append(BatchCreatorResult(
                uid=item.uid, success=False, error=str(exc)
            ))
    return BatchCreatorResponse(results=results)


@router.get("/resolve-name", response_model=dict)
def resolve_creator_name(profile_url: str) -> dict:
    """根据主页 URL 从 B 站获取 UP 主昵称和头像。"""
    uid = _uid_from_profile_url(profile_url)
    try:
        info = _fetcher.fetch_creator_info(uid)
    except FetchError as exc:
        logger.exception("解析 UP 主名称失败 uid=%s", uid)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("解析 UP 主名称失败 uid=%s", uid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析失败，请确认已运行 playwright install chromium：{exc}",
        ) from exc
    return {"name": info["name"], "avatar_url": info.get("avatar_url")}


@router.get("", response_model=list[CreatorRead])
def list_creators(
    db: Annotated[Session, Depends(get_db)],
) -> list[CreatorRead]:
    """返回所有 UP 主列表。"""
    creators = _creator_svc.list_creators(db)
    return [_to_creator_read(c) for c in creators]


@router.get("/{creator_id}", response_model=CreatorRead)
def get_creator(
    creator_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> CreatorRead:
    """获取单个 UP 主详情。"""
    creator = _creator_svc.get_creator(db, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    return _to_creator_read(creator)


@router.get("/{creator_id}/videos", response_model=list[VideoDetail])
def list_creator_videos(
    creator_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> list[VideoDetail]:
    """返回指定 UP 主的所有视频（含已看状态），按发布时间倒序。"""
    creator = _creator_svc.get_creator(db, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")

    rows = (
        db.query(Video, VideoStatus.status, Creator.name.label("creator_name"), Creator.alias.label("creator_alias"), Creator.avatar_url.label("creator_avatar_url"))
        .join(Creator, Video.creator_id == Creator.id)
        .outerjoin(VideoStatus, VideoStatus.video_id == Video.id)
        .filter(Video.creator_id == creator_id)
        .order_by(Video.published_at.desc())
        .all()
    )

    return [
        VideoDetail(
            id=video.id,
            bvid=video.bvid,
            title=video.title,
            creator_id=video.creator_id,
            creator_name=creator_name,
            creator_alias=creator_alias,
            creator_avatar_url=creator_avatar_url,
            video_url=video.video_url,
            published_at=video.published_at,
            duration_seconds=video.duration_seconds,
            cover_url=video.cover_url,
            status=status_value if status_value is not None else 0,
        )
        for video, status_value, creator_name, creator_alias, creator_avatar_url in rows
    ]


@router.patch("/{creator_id}", response_model=CreatorRead)
def update_creator(
    creator_id: int,
    payload: CreatorUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CreatorRead:
    """编辑 UP 主（名称 / 别名 / 标签关联）。"""
    creator = _creator_svc.get_creator(db, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    creator = _creator_svc.update_creator(
        db=db,
        creator=creator,
        name=payload.name,
        alias=payload.alias,
        tag_ids=payload.tag_ids,
    )
    return _to_creator_read(creator)


@router.patch("/{creator_id}/videos/status")
def batch_update_video_status(
    creator_id: int,
    payload: VideoStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """批量将某个 UP 主的所有未看视频标记为指定状态。

    - status=1：一键已看
    - status=2：一键不看
    """
    creator = _creator_svc.get_creator(db, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    count = _video_svc.batch_set_status_by_creator(db, creator_id, payload.status)
    return {"creator_id": creator_id, "status": payload.status, "updated_count": count}
