"""FastAPI 依赖注入函数。"""
from __future__ import annotations

from app.store.store import DataStore

_store: DataStore | None = None


def init_store(data_store: DataStore) -> None:
    """初始化全局 DataStore 实例（由 lifespan 调用）。"""
    global _store
    _store = data_store


def get_store() -> DataStore:
    """提供全局 DataStore 实例。"""
    if _store is None:
        raise RuntimeError("DataStore 尚未初始化，请先调用 init_store()")
    return _store
