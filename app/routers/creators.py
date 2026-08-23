"""UP 主管理路由。"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_fetcher, get_store
from app.domains.creators.schemas import (
    BatchCreatorRequest,
    BatchCreatorResponse,
    CreatorCreate,
    CreatorRead,
    CreatorUpdate,
)
from app.domains.creators.service import CreatorService
from app.domains.videos.schemas import VideoDetail, VideoStatusUpdate
from app.domains.videos.service import VideoService
from app.fetcher.playwright_fetcher import FetchError, PlaywrightBilibiliFetcher
from app.shared.store import DataStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/creators", tags=["creators"])
_creator_svc = CreatorService()
_video_svc = VideoService()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatorRead)
async def create_creator(
    payload: CreatorCreate,
    store: Annotated[DataStore, Depends(get_store)],
    fetcher: Annotated[PlaywrightBilibiliFetcher, Depends(get_fetcher)],
) -> CreatorRead:
    """添加新 UP 主（可同时关联标签）。

    avatar_url 缺失或 video_count 缺失时走 resolve 拿到；resolve 失败返回 502。
    """
    try:
        info = await _creator_svc.resolve_creator_info(fetcher, payload.profile_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FetchError as exc:
        logger.exception("创建 UP 主-获取信息失败 url=%s", payload.profile_url)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    creator = await _creator_svc.create_creator(
        store=store,
        name=payload.name,
        profile_url=payload.profile_url,
        tag_ids=payload.tag_ids,
        avatar_url=payload.avatar_url or info["avatar_url"],
        video_count=info["video_count"],
        alias=payload.alias,
    )
    return _creator_svc.to_read(store, creator)


@router.post("/batch", status_code=status.HTTP_200_OK, response_model=BatchCreatorResponse)
async def batch_create_creators(
    payload: BatchCreatorRequest,
    store: Annotated[DataStore, Depends(get_store)],
    fetcher: Annotated[PlaywrightBilibiliFetcher, Depends(get_fetcher)],
) -> BatchCreatorResponse:
    """批量添加 UP 主。"""
    return await _creator_svc.batch_create(store, fetcher, payload.items)


@router.get("/resolve-name", response_model=dict)
async def resolve_creator_name(
    profile_url: str,
    fetcher: Annotated[PlaywrightBilibiliFetcher, Depends(get_fetcher)],
) -> dict:
    """根据主页 URL 从 B 站获取 UP 主昵称和头像。"""
    try:
        info = await _creator_svc.resolve_creator_info(fetcher, profile_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FetchError as exc:
        logger.exception("解析 UP 主名称失败 url=%s", profile_url)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"name": info["name"], "avatar_url": info.get("avatar_url")}


@router.get("", response_model=list[CreatorRead])
def list_creators(
    store: Annotated[DataStore, Depends(get_store)],
) -> list[CreatorRead]:
    """返回所有 UP 主列表。"""
    creators = _creator_svc.list_creators(store)
    return _creator_svc.to_read_many(store, creators)


@router.get("/{creator_id}", response_model=CreatorRead)
def get_creator(
    creator_id: int,
    store: Annotated[DataStore, Depends(get_store)],
) -> CreatorRead:
    """获取单个 UP 主详情。"""
    creator = _creator_svc.get_creator(store, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    return _creator_svc.to_read(store, creator)


@router.get("/{creator_id}/videos", response_model=list[VideoDetail])
def list_creator_videos(
    creator_id: int,
    store: Annotated[DataStore, Depends(get_store)],
) -> list[VideoDetail]:
    """返回指定 UP 主的所有视频（含已看状态），按发布时间倒序。"""
    creator = _creator_svc.get_creator(store, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    return _video_svc.list_video_details_by_creator(store, creator)


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
    return _creator_svc.to_read(store, creator)


@router.delete("/{creator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creator(
    creator_id: int,
    store: Annotated[DataStore, Depends(get_store)],
) -> None:
    """删除 UP 主，级联删除其标签关联、视频与观看状态。"""
    if not await _creator_svc.delete_creator(store, creator_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")


@router.patch("/{creator_id}/videos/status")
async def batch_update_video_status(
    creator_id: int,
    payload: VideoStatusUpdate,
    store: Annotated[DataStore, Depends(get_store)],
) -> dict:
    """批量将某个 UP 主的所有视频标记为指定状态。"""
    creator = _creator_svc.get_creator(store, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    count = await _video_svc.batch_set_status_by_creator(store, creator_id, payload.status)
    return {"creator_id": creator_id, "status": payload.status, "updated_count": count}
