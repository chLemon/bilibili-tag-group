"""JsonRepo 存储层测试。"""
import asyncio

from app.models.tag import Tag
from app.store.repo import JsonRepo


async def test_concurrent_adds_have_unique_ids(tmp_path):
    """并发 add 不产生重复 id、不丢数据（写路径有 asyncio.Lock 保护）。"""
    repo = JsonRepo[Tag](Tag, tmp_path / "tags.json")
    await asyncio.gather(*(repo.add(Tag(name=f"tag{i}")) for i in range(50)))
    tags = repo.all()
    assert len(tags) == 50
    assert len({t.id for t in tags}) == 50


async def test_get_and_filter(tmp_path):
    repo = JsonRepo[Tag](Tag, tmp_path / "tags.json")
    await repo.add(Tag(name="a"))
    await repo.add(Tag(name="b"))
    assert repo.get(1).name == "a"
    assert repo.get(999) is None
    assert [t.name for t in repo.filter(name="b")] == ["b"]


async def test_update_and_delete(tmp_path):
    repo = JsonRepo[Tag](Tag, tmp_path / "tags.json")
    await repo.add(Tag(name="a"))
    updated = await repo.update(1, name="a2")
    assert updated is not None and updated.name == "a2"
    assert await repo.update(999, name="x") is None
    assert await repo.delete(1) is True
    assert await repo.delete(1) is False
    assert repo.all() == []
