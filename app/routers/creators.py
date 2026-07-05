"""UP 主管理路由。"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher, FetchError
from app.schemas.creator import CreatorCreate, CreatorRead, CreatorUpdate
from app.services.creator_service import CreatorService
from app.services.sync_service import SyncService

router = APIRouter(prefix="/api/creators", tags=["creators"])
_creator_svc = CreatorService()
_fetcher = PlaywrightBilibiliFetcher(cookie=settings.bilibili_cookie or None)
_sync_svc = SyncService(fetcher=_fetcher)


def _uid_from_profile_url(profile_url: str) -> str:
    """从 B 站主页 URL 中提取 uid。"""
    return profile_url.rstrip("/").split("/")[-1]


def _to_creator_read(creator) -> CreatorRead:
    """将 ORM Creator 对象转换为 CreatorRead schema。"""
    return CreatorRead(
        id=creator.id,
        name=creator.name,
        profile_url=creator.profile_url,
        avatar_url=creator.avatar_url,
        enabled=creator.enabled,
        tag_ids=[tag.id for tag in creator.tags],
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
    )
    return _to_creator_read(creator)


@router.get("/resolve-name", response_model=dict)
def resolve_creator_name(profile_url: str) -> dict:
    """根据主页 URL 从 B 站获取 UP 主昵称和头像。"""
    uid = _uid_from_profile_url(profile_url)
    try:
        info = _fetcher.fetch_creator_info(uid)
    except FetchError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    return {"name": info["name"], "avatar_url": info.get("avatar_url")}


@router.get("", response_model=list[CreatorRead])
def list_creators(
    db: Annotated[Session, Depends(get_db)],
) -> list[CreatorRead]:
    """返回所有 UP 主列表。"""
    creators = _creator_svc.list_creators(db)
    return [_to_creator_read(c) for c in creators]


@router.patch("/{creator_id}", response_model=CreatorRead)
def update_creator(
    creator_id: int,
    payload: CreatorUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CreatorRead:
    """编辑 UP 主（名称 / enabled / 标签关联）。"""
    creator = _creator_svc.get_creator(db, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    creator = _creator_svc.update_creator(
        db=db,
        creator=creator,
        name=payload.name,
        enabled=payload.enabled,
        tag_ids=payload.tag_ids,
    )
    return _to_creator_read(creator)


@router.post("/{creator_id}/sync", response_model=dict)
def sync_creator(
    creator_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """对单个 UP 主执行手动同步。"""
    creator = _creator_svc.get_creator(db, creator_id)
    if creator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creator 不存在")
    try:
        new_count = _sync_svc.sync_creator(db, creator)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"同步失败：{exc}",
        ) from exc
    return {"creator_id": creator_id, "new_videos": new_count}
