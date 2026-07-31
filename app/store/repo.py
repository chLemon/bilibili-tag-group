"""泛型 JSON 文件仓库：按需 IO、写入加锁。"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


class JsonRepoError(RuntimeError):
    """JSON 数据文件损坏（无法解析）时抛出。

    不允许回退为空列表：写路径基于读结果做 read-modify-write，
    损坏时静默返回 [] 会导致下一次写入覆盖丢失全部数据。
    """


@contextmanager
def _cross_process_lock(lock_path: Path) -> Iterator[None]:
    """跨进程文件锁：保护多进程下的读-改-写临界区。

    asyncio.Lock 只约束单进程；多个 uvicorn/脚本进程同时写同一 JSON 时
    需要 OS 级文件锁（POSIX flock / Windows msvcrt）。锁为建议锁，
    只对同样走 JsonRepo 写路径的进程生效。
    """
    f = open(lock_path, "a+b")
    try:
        if sys.platform == "win32":
            # msvcrt 要求锁定区域真实存在，先保证文件至少 1 字节
            if f.seek(0, os.SEEK_END) == 0:
                f.write(b"\0")
                f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if sys.platform == "win32":
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        finally:
            f.close()


class JsonRepo[T]:
    """按需 IO 的 JSON 文件存储仓库。

    读操作不加锁，可能读到上一次已完成的写入（os.replace 保证不会读到
    写一半的中间态）；写操作持进程内 asyncio.Lock + 跨进程文件锁，
    落盘用临时文件 + fsync + os.replace 原子替换。
    """

    def __init__(self, model_class: type[T], file_path: Path) -> None:
        self._model = model_class
        self._file_path = file_path
        self._lock_path = file_path.with_name(file_path.name + ".lock")
        self._lock = asyncio.Lock()

    # ── 读（无锁） ──────────────────────────────────────────

    def _read(self) -> list[T]:
        if not self._file_path.exists():
            return []
        text = self._file_path.read_text("utf-8")
        if not text.strip():
            return []
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise JsonRepoError(
                f"数据文件损坏，无法解析：{self._file_path}（{exc}）。"
                "请从备份或 git 历史恢复后再继续，避免写入覆盖丢失数据。"
            ) from exc
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

    @asynccontextmanager
    async def locked(self) -> AsyncIterator[JsonRepo[T]]:
        """把多步读-改-写包进同一临界区（进程内锁 + 跨进程文件锁）。

        用于 check-then-act 场景（如 start_sync 先查 running 再新建），
        防止另一进程/协程在检查与写入之间插入变更。

        锁不可重入：临界区内只能调用 *_nolock 原语，调用 add/update 等
        加锁方法会死锁。yield 本仓库实例便于直接使用这些原语。
        """
        async with self._lock:
            with _cross_process_lock(self._lock_path):
                yield self

    def _write(self, items: list[T]) -> None:
        data = [item.model_dump(mode="json") for item in items]
        text = json.dumps(data, ensure_ascii=False, indent=2)
        fd, tmp = tempfile.mkstemp(
            dir=self._file_path.parent,
            prefix=self._file_path.name + ".",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._file_path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    @staticmethod
    def _next_id(items: list[T]) -> int:
        return max((x.id for x in items), default=0) + 1

    # ── 无锁原语（仅限 locked() 临界区内调用） ────────────────

    def add_nolock(self, item: T) -> T:
        items = self._read()
        if item.id == 0:
            item.id = self._next_id(items)
        items.append(item)
        self._write(items)
        return item

    def update_nolock(self, id: int, **kwargs: object) -> T | None:
        items = self._read()
        for item in items:
            if item.id == id:
                for k, v in kwargs.items():
                    setattr(item, k, v)
                self._write(items)
                return item
        return None

    def bulk_update_nolock(self, ids: set[int], **kwargs: object) -> int:
        items = self._read()
        changed = 0
        for item in items:
            if item.id in ids:
                for k, v in kwargs.items():
                    setattr(item, k, v)
                changed += 1
        if changed:
            self._write(items)
        return changed

    def delete_nolock(self, id: int) -> bool:
        items = self._read()
        for i, item in enumerate(items):
            if item.id == id:
                items.pop(i)
                self._write(items)
                return True
        return False

    # ── 加锁写接口（常规调用入口） ────────────────────────────

    async def add(self, item: T) -> T:
        async with self.locked():
            return self.add_nolock(item)

    async def update(self, id: int, **kwargs: object) -> T | None:
        async with self.locked():
            return self.update_nolock(id, **kwargs)

    async def bulk_update(self, ids: set[int], **kwargs: object) -> int:
        """对 id 在 ids 内的所有记录应用同一组字段更新，一次读、一次写。

        返回实际更新的条数。用于批量场景（如一键已看）替代逐条 update
        造成的 N 次全量读写。
        """
        if not ids:
            return 0
        async with self.locked():
            return self.bulk_update_nolock(ids, **kwargs)

    async def delete(self, id: int) -> bool:
        async with self.locked():
            return self.delete_nolock(id)
