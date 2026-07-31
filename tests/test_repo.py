"""JsonRepo 存储层测试。"""
import asyncio
import multiprocessing
from pathlib import Path

import pytest

from app.models.tag import Tag
from app.store.repo import JsonRepo, JsonRepoError


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


async def _add_tags(repo: JsonRepo[Tag], count: int) -> None:
    await asyncio.gather(*(repo.add(Tag(name="t")) for _ in range(count)))


def _add_tags_in_process(file_path: str, count: int) -> None:
    """子进程入口：独立事件循环里向同一文件并发 add。"""
    repo = JsonRepo[Tag](Tag, Path(file_path))
    asyncio.run(_add_tags(repo, count))


def test_multiprocess_adds_have_unique_ids(tmp_path):
    """多进程并发 add 不产生重复 id、不丢数据（文件锁保护读-改-写）。

    复现此前 videos.json 重复 1302 条的根因：asyncio.Lock 只管进程内。
    """
    file_path = tmp_path / "tags.json"
    procs = [
        multiprocessing.Process(target=_add_tags_in_process, args=(str(file_path), 10))
        for _ in range(5)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=60)
        assert p.exitcode == 0

    tags = JsonRepo[Tag](Tag, file_path).all()
    assert len(tags) == 50
    assert len({t.id for t in tags}) == 50


async def test_bulk_update(tmp_path):
    repo = JsonRepo[Tag](Tag, tmp_path / "tags.json")
    for i in range(5):
        await repo.add(Tag(name=f"tag{i}"))
    changed = await repo.bulk_update({1, 3, 99}, name="hit")
    assert changed == 2  # id=99 不存在
    assert [t.name for t in repo.all()] == ["hit", "tag1", "hit", "tag3", "tag4"]
    assert await repo.bulk_update(set(), name="x") == 0


async def test_corrupt_file_raises_clear_error(tmp_path):
    """损坏的 JSON 必须抛 JsonRepoError，而不是静默返回空导致写覆盖丢数据。"""
    file_path = tmp_path / "tags.json"
    file_path.write_text('{"不是合法JSON"', "utf-8")
    repo = JsonRepo[Tag](Tag, file_path)
    with pytest.raises(JsonRepoError, match="数据文件损坏"):
        repo.all()


async def test_empty_file_reads_as_empty(tmp_path):
    file_path = tmp_path / "tags.json"
    file_path.write_text("", "utf-8")
    assert JsonRepo[Tag](Tag, file_path).all() == []


async def test_locked_check_then_act_is_atomic(tmp_path):
    """locked() 临界区内的 check-then-act 不被其他协程插入。"""
    repo = JsonRepo[Tag](Tag, tmp_path / "tags.json")
    created = 0

    async def create_if_absent(name: str) -> None:
        nonlocal created
        async with repo.locked() as r:
            if not any(t.name == name for t in r.all()):
                await asyncio.sleep(0)  # 让出事件循环，模拟交错
                r.add_nolock(Tag(name=name))
                created += 1

    await asyncio.gather(*(create_if_absent("same") for _ in range(10)))
    assert created == 1
    assert len(repo.all()) == 1
