"""FastAPI 依赖注入函数。"""
from __future__ import annotations

from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.services.sync_service import SyncService
from app.store.store import DataStore

_store: DataStore | None = None
_fetcher: PlaywrightBilibiliFetcher | None = None
_sync_service: SyncService | None = None


def init_app(
    store: DataStore,
    fetcher: PlaywrightBilibiliFetcher,
    sync_service: SyncService,
) -> None:
    """初始化全局应用实例（由 lifespan 调用）。"""
    global _store, _fetcher, _sync_service
    _store = store
    _fetcher = fetcher
    _sync_service = sync_service


def get_store() -> DataStore:
    """提供全局 DataStore 实例。"""
    if _store is None:
        raise RuntimeError("应用尚未初始化，请先调用 init_app()")
    return _store


def get_fetcher() -> PlaywrightBilibiliFetcher:
    """提供全局 B 站抓取器实例。"""
    if _fetcher is None:
        raise RuntimeError("应用尚未初始化，请先调用 init_app()")
    return _fetcher


def get_sync_service() -> SyncService:
    """提供全局 SyncService 实例。"""
    if _sync_service is None:
        raise RuntimeError("应用尚未初始化，请先调用 init_app()")
    return _sync_service
