"""UP 主管理服务：负责创建、查询、编辑 UP 主及其标签关联。"""
from __future__ import annotations

from app.models.creator import Creator
from app.models.creator_tag import CreatorTag
from app.models.tag import Tag
from app.store.store import DataStore


class CreatorService:
    """管理 UP 主与标签关联的业务逻辑。"""

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
