"""泛型 JSON 文件仓库：按需 IO、写入加锁。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path


class JsonRepo[T]:
    """按需 IO 的 JSON 文件存储仓库。

    读操作不加锁，写操作使用 asyncio.Lock 保证 read-modify-write 原子性。
    """

    def __init__(self, model_class: type[T], file_path: Path) -> None:
        self._model = model_class
        self._file_path = file_path
        self._lock = asyncio.Lock()

    # ── 读（无锁） ──────────────────────────────────────────

    def _read(self) -> list[T]:
        if not self._file_path.exists():
            return []
        raw = json.loads(self._file_path.read_text("utf-8"))
        return [self._model.model_validate(item) for item in raw]

    def all(self) -> list[T]:
        return self._read()

    def get(self, id: int) -> T | None:
        items = self._read()
        return next((x for x in items if x.id == id), None)

    def filter(self, **kwargs: object) -> list[T]:
        items = self._read()
        for k, v in kwargs.items():
            items = [x for x in items if getattr(x, k) == v]
        return items

    # ── 写（加锁） ──────────────────────────────────────────

    def _write(self, items: list[T]) -> None:
        data = [item.model_dump(mode="json") for item in items]
        self._file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            "utf-8",
        )

    @staticmethod
    def _next_id(items: list[T]) -> int:
        return max((x.id for x in items), default=0) + 1

    async def add(self, item: T) -> T:
        async with self._lock:
            items = self._read()
            if item.id == 0:
                item.id = self._next_id(items)
            items.append(item)
            self._write(items)
            return item

    async def update(self, id: int, **kwargs: object) -> T | None:
        async with self._lock:
            items = self._read()
            for item in items:
                if item.id == id:
                    for k, v in kwargs.items():
                        setattr(item, k, v)
                    self._write(items)
                    return item
            return None

    async def delete(self, id: int) -> bool:
        async with self._lock:
            items = self._read()
            for i, item in enumerate(items):
                if item.id == id:
                    items.pop(i)
                    self._write(items)
                    return True
            return False
