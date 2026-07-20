"""UP 主管理路由。"""
import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger(__name__)

from app.config import settings
from app.dependencies import get_store
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher, FetchError
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
from app.store.store import DataStore

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


def _to_creator_read(creator, store: DataStore) -> CreatorRead:
    """将 Creator 模型转换为 CreatorRead schema，附带视频统计数据。"""
    videos_list = store.videos.filter(creator_id=creator.id)
    video_statuses = store.video_statuses.all()
    status_map = {s.video_id: s for s in video_statuses}
    unwatched = sum(
        1 for v in videos_list
        if v.id not in status_map or status_map[v.id].status == 0
    )
    tag_ids = [link.tag_id for link in store.creator_tags.filter(creator_id=creator.id)]
    return CreatorRead(
        id=creator.id,
        name=creator.name,
        alias=creator.alias,
        profile_url=creator.profile_url,
        avatar_url=creator.avatar_url,
        tag_ids=tag_ids,
        enabled=creator.enabled,
        video_count=creator.video_count or 0,
        synced_video_count=len(videos_list),
        unwatched_count=unwatched,
        last_synced_at=creator.last_synced_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatorRead)
async def create_creator(
    payload: CreatorCreate,
    store: Annotated[DataStore, Depends(get_store)],
) -> CreatorRead:
    """添加新 UP 主（可同时关联标签）。"""
    creator = await _creator_svc.create_creator(
        store=store,
        name=payload.name,
        profile_url=payload.profile_url,
        tag_ids=payload.tag_ids,
        avatar_url=payload.avatar_url,
        alias=payload.alias,
    )
    return _to_creator_read(creator, store)


@router.post("/batch", status_code=status.HTTP_200_OK, response_model=BatchCreatorResponse)
async def batch_create_creators(
    payload: BatchCreatorRequest,
    store: Annotated[DataStore, Depends(get_store)],
) -> BatchCreatorResponse:
    """批量添加 UP 主。"""
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

            tags = await _creator_svc.find_or_create_tags(store, item.tag_names)
            tag_ids = [t.id for t in tags]

            creator = await _creator_svc.create_creator(
                store=store,
                name=creator_name,
                profile_url=profile_url,
                tag_ids=tag_ids,
                avatar_url=avatar_url,
            )
            results.append(BatchCreatorResult(
                uid=item.uid, success=True, creator=_to_creator_read(creator, store)
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
    store: Annotated[DataStore, Depends(get_store)],
) -> list[CreatorRead]:
    """返回所有 UP 主列表。"""
    creators = _creator_svc.list_creators(store)
    return [_to_creator_read(c, store) for c in creators]


@router.get("/{creator_id}", response_model=CreatorRead)
def get_creator(
    creator_id: int,
    store: Annotated[DataStore, Depends(get_store)],
) -> CreatorRead:
    """获取单个 UP 主详情。"""
    creator = _creator_svc.get_creator(store, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    return _to_creator_read(creator, store)


@router.get("/{creator_id}/videos", response_model=list[VideoDetail])
def list_creator_videos(
    creator_id: int,
    store: Annotated[DataStore, Depends(get_store)],
) -> list[VideoDetail]:
    """返回指定 UP 主的所有视频（含已看状态），按发布时间倒序。"""
    creator = _creator_svc.get_creator(store, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")

    videos_list = store.videos.filter(creator_id=creator_id)
    all_statuses = {s.video_id: s for s in store.video_statuses.all()}
    videos_list.sort(key=lambda v: v.published_at, reverse=True)

    return [
        VideoDetail(
            id=video.id,
            bvid=video.bvid,
            title=video.title,
            creator_id=video.creator_id,
            creator_name=creator.name,
            creator_alias=creator.alias,
            creator_avatar_url=creator.avatar_url,
            video_url=video.video_url,
            published_at=video.published_at,
            duration_seconds=video.duration_seconds,
            cover_url=video.cover_url,
            status=all_statuses[video.id].status if video.id in all_statuses else 0,
        )
        for video in videos_list
    ]


@router.patch("/{creator_id}", response_model=CreatorRead)
async def update_creator(
    creator_id: int,
    payload: CreatorUpdate,
    store: Annotated[DataStore, Depends(get_store)],
) -> CreatorRead:
    """编辑 UP 主（名称 / 别名 / 标签关联）。"""
    creator = _creator_svc.get_creator(store, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    creator = await _creator_svc.update_creator(
        store=store,
        creator=creator,
        name=payload.name,
        alias=payload.alias,
        enabled=payload.enabled,
        tag_ids=payload.tag_ids,
    )
    return _to_creator_read(creator, store)


@router.patch("/{creator_id}/videos/status")
async def batch_update_video_status(
    creator_id: int,
    payload: VideoStatusUpdate,
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    """批量将某个 UP 主的所有未看视频标记为指定状态。"""
    creator = _creator_svc.get_creator(store, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    count = await _video_svc.batch_set_status_by_creator(store, creator_id, payload.status)
    return {"creator_id": creator_id, "status": payload.status, "updated_count": count}
