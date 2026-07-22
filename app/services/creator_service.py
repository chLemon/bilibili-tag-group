"""UP 主管理服务：负责创建、查询、编辑 UP 主及其标签关联。"""
from __future__ import annotations

import logging
import re

from app.fetcher.playwright_fetcher import FetchError, PlaywrightBilibiliFetcher
from app.models.creator import Creator
from app.models.creator_tag import CreatorTag
from app.models.tag import Tag
from app.schemas.creator import (
    BatchCreatorItem,
    BatchCreatorResponse,
    BatchCreatorResult,
    CreatorRead,
)
from app.store.store import DataStore

logger = logging.getLogger(__name__)

_UID_RE = re.compile(r"space\.bilibili\.com/(\d+)")


class CreatorService:
    """管理 UP 主与标签关联的业务逻辑。"""

    @staticmethod
    def uid_from_profile_url(profile_url: str) -> str:
        """从 B 站主页 URL 中提取 uid；若已是纯数字 uid 则直接返回。"""
        trimmed = profile_url.strip()
        if trimmed.isdigit():
            return trimmed
        m = _UID_RE.search(trimmed)
        if m:
            return m.group(1)
        raise ValueError(f"无法从 URL 中提取 UID：{profile_url}")

    def to_read(self, store: DataStore, creator: Creator) -> CreatorRead:
        """将 Creator 模型转换为 CreatorRead schema，附带视频统计数据。"""
        videos_list = store.videos.filter(creator_id=creator.id)
        status_map = {s.video_id: s for s in store.video_statuses.all()}
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

    async def resolve_creator_info(
        self, fetcher: PlaywrightBilibiliFetcher, profile_url: str
    ) -> dict:
        """根据主页 URL 从 B 站获取 UP 主昵称和头像。"""
        uid = self.uid_from_profile_url(profile_url)
        return await fetcher.fetch_creator_info(uid)

    async def batch_create(
        self,
        store: DataStore,
        fetcher: PlaywrightBilibiliFetcher,
        items: list[BatchCreatorItem],
    ) -> BatchCreatorResponse:
        """批量添加 UP 主：逐条抓取昵称、关联标签、创建记录，单条失败不影响整体。"""
        results: list[BatchCreatorResult] = []
        for item in items:
            try:
                profile_url = f"https://space.bilibili.com/{item.uid}"
                if item.name:
                    creator_name = item.name
                    avatar_url = None
                else:
                    try:
                        info = await fetcher.fetch_creator_info(item.uid)
                        creator_name = info["name"]
                        avatar_url = info.get("avatar_url")
                    except FetchError as exc:
                        logger.exception("批量添加-获取 UP 主信息失败 uid=%s", item.uid)
                        results.append(BatchCreatorResult(
                            uid=item.uid, success=False, error=f"获取 UP 主信息失败：{exc}"
                        ))
                        continue

                tags = await self.find_or_create_tags(store, item.tag_names)
                creator = await self.create_creator(
                    store=store,
                    name=creator_name,
                    profile_url=profile_url,
                    tag_ids=[t.id for t in tags],
                    avatar_url=avatar_url,
                )
                results.append(BatchCreatorResult(
                    uid=item.uid, success=True, creator=self.to_read(store, creator)
                ))
            except Exception as exc:
                logger.exception("批量添加 UP 主失败 uid=%s", item.uid)
                results.append(BatchCreatorResult(uid=item.uid, success=False, error=str(exc)))
        return BatchCreatorResponse(results=results)

    async def create_creator(
        self,
        store: DataStore,
        name: str,
        profile_url: str,
        tag_ids: list[int],
        avatar_url: str | None = None,
        alias: str | None = None,
    ) -> Creator:
        """创建新 UP 主，并可选择同时关联标签。"""
        creator = Creator(
            name=name,
            profile_url=profile_url,
            avatar_url=avatar_url,
            alias=alias,
        )
        await store.creators.add(creator)
        for tag_id in tag_ids:
            ct = CreatorTag(creator_id=creator.id, tag_id=tag_id)
            await store.creator_tags.add(ct)
        return creator

    async def find_or_create_tags(self, store: DataStore, names: list[str]) -> list[Tag]:
        """根据标签名称列表查找已有标签，不存在的自动创建。"""
        if not names:
            return []
        all_tags = store.tags.all()
        existing = [t for t in all_tags if t.name in names]
        existing_names = {t.name for t in existing}
        new_tags = [Tag(name=n) for n in names if n not in existing_names]
        for tag in new_tags:
            await store.tags.add(tag)
        return existing + new_tags

    def list_creators(self, store: DataStore) -> list[Creator]:
        """返回所有 UP 主列表（按 id 升序）。"""
        return sorted(store.creators.all(), key=lambda c: c.id)

    def get_creator(self, store: DataStore, creator_id: int) -> Creator | None:
        """根据 id 获取单个 UP 主，不存在时返回 None。"""
        return store.creators.get(creator_id)

    async def update_creator(
        self,
        store: DataStore,
        creator: Creator,
        name: str | None,
        alias: str | None,
        tag_ids: list[int] | None,
        enabled: bool | None = None,
    ) -> Creator:
        """更新 UP 主字段（只修改非 None 的字段）。

        tag_ids 不为 None 时，完整替换现有标签关联。
        """
        updates: dict[str, object] = {}
        if name is not None:
            updates["name"] = name
        if alias is not None:
            updates["alias"] = alias
        if enabled is not None:
            updates["enabled"] = enabled
        if updates:
            await store.creators.update(creator.id, **updates)

        if tag_ids is not None:
            old_links = store.creator_tags.filter(creator_id=creator.id)
            for link in old_links:
                await store.creator_tags.delete(link.id)
            for tag_id in tag_ids:
                ct = CreatorTag(creator_id=creator.id, tag_id=tag_id)
                await store.creator_tags.add(ct)

        return store.creators.get(creator.id) or creator

    def get_tag_ids(self, store: DataStore, creator_id: int) -> list[int]:
        """获取 UP 主关联的所有标签 ID。"""
        links = store.creator_tags.filter(creator_id=creator_id)
        return [link.tag_id for link in links]
