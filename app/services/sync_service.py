"""同步核心服务：将 B 站抓取结果写入本地数据库。"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from app.fetcher.models import FetchedVideo
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.models.creator import Creator
from app.models.sync_task import SyncTask
from app.models.tag_sync_config import TagSyncConfig
from app.models.video import Video
from app.models.video_status import VideoStatus
from app.store.store import DataStore
from app.utils.time import now_utc as _now_utc

logger = logging.getLogger(__name__)


def _uid_from_profile_url(profile_url: str) -> str:
    return profile_url.rstrip("/").split("/")[-1]


class SyncService:
    """同步服务：协调抓取与数据库写入，保持本地视频数据与 B 站同步。"""

    _HEARTBEAT_INTERVAL = 15
    _HEARTBEAT_DEAD_SEC = 45

    def __init__(self, fetcher: PlaywrightBilibiliFetcher | None = None) -> None:
        self._fetcher = fetcher if fetcher is not None else PlaywrightBilibiliFetcher()

    @staticmethod
    def _get_immediate_tag_ids(store: DataStore) -> set[int]:
        configs = store.tag_sync_configs.all()
        return {row.tag_id for row in configs}

    @staticmethod
    def _creator_has_immediate_tag(
        store: DataStore, creator_id: int, immediate_tag_ids: set[int]
    ) -> bool:
        if not immediate_tag_ids:
            return False
        creator_tag_ids = {
            row.tag_id
            for row in store.creator_tags.filter(creator_id=creator_id)
        }
        return bool(creator_tag_ids & immediate_tag_ids)

    async def sync_creator(self, store: DataStore, creator: Creator) -> int:
        """同步 UP 主的信息。"""
        if not creator.enabled:
            return 0

        immediate_tag_ids = self._get_immediate_tag_ids(store)
        if self._creator_has_immediate_tag(store, creator.id, immediate_tag_ids):
            if creator.last_synced_at and (
                _now_utc() - creator.last_synced_at
            ) < timedelta(minutes=5):
                return 0
        else:
            if creator.last_synced_at and (
                _now_utc() - creator.last_synced_at
            ) < timedelta(minutes=50):
                return 0

        uid = _uid_from_profile_url(creator.profile_url)

        try:
            info = await self._fetcher.fetch_creator_info(uid)
            if info.get("name"):
                creator.name = info["name"]
            if info.get("avatar_url"):
                creator.avatar_url = info["avatar_url"]
            if info.get("video_count") is not None:
                creator.video_count = info["video_count"]
        except Exception:
            pass

        fetched_list: list[FetchedVideo] = await self._fetcher.fetch_new_videos(uid)

        existing_videos_list = store.videos.filter(creator_id=creator.id)
        existing_videos: dict[str, Video] = {v.bvid: v for v in existing_videos_list}

        new_count = 0
        for fv in fetched_list:
            if fv.published_at is None:
                logger.warning("跳过无发布时间的视频 bvid=%s", fv.bvid)
                continue
            if fv.bvid in existing_videos:
                video = existing_videos[fv.bvid]
                await store.videos.update(
                    video.id,
                    title=fv.title,
                    video_url=fv.video_url,
                    published_at=fv.published_at,
                    duration_seconds=fv.duration_seconds,
                    cover_url=fv.cover_url,
                )
            else:
                video = Video(
                    bvid=fv.bvid,
                    creator_id=creator.id,
                    title=fv.title,
                    video_url=fv.video_url,
                    published_at=fv.published_at,
                    duration_seconds=fv.duration_seconds,
                    cover_url=fv.cover_url,
                )
                await store.videos.add(video)
                status = VideoStatus(video_id=video.id)
                await store.video_statuses.add(status)
                new_count += 1

        await store.creators.update(creator.id, last_synced_at=_now_utc())
        return new_count

    # ── 异步全量同步（后台协程） ──────────────────────────────────

    async def start_sync(self, store: DataStore) -> tuple[SyncTask, bool]:
        """创建全量同步任务并返回 (task, created)。

        已有 running 任务时：心跳超时则标记失败并新建；否则返回 (existing, False)，
        调用方不得再启动执行协程。
        """
        running = store.sync_tasks.filter(status="running")
        if running:
            existing = max(running, key=lambda t: t.started_at)
            if existing.heartbeat_at is not None:
                age_sec = (_now_utc() - existing.heartbeat_at).total_seconds()
                if age_sec >= self._HEARTBEAT_DEAD_SEC:
                    await store.sync_tasks.update(
                        existing.id,
                        status="failed",
                        error_message="任务进程崩溃，心跳超时未更新",
                        finished_at=_now_utc(),
                    )
                else:
                    return existing, False
            else:
                return existing, False

        total = len(store.creators.all())
        task = SyncTask(
            status="running",
            total_creators=total,
            completed_creators=0,
            new_videos=0,
            started_at=_now_utc(),
            heartbeat_at=_now_utc(),
        )
        await store.sync_tasks.add(task)
        return task, True

    async def _heartbeat_loop(
        self, task_id: int, store: DataStore, stop_event: asyncio.Event
    ) -> None:
        """独立心跳协程：每隔 _HEARTBEAT_INTERVAL 秒更新 heartbeat_at。"""
        while not stop_event.is_set():
            await asyncio.sleep(self._HEARTBEAT_INTERVAL)
            if stop_event.is_set():
                break
            await store.sync_tasks.update(task_id, heartbeat_at=_now_utc())

    async def run_sync_task(self, task_id: int, store: DataStore) -> None:
        """后台协程：逐个同步 UP 主，更新 SyncTask 进度。"""
        heartbeat_stop = asyncio.Event()
        hb_task = None
        try:
            task = store.sync_tasks.get(task_id)
            if task is None:
                return

            hb_task = asyncio.create_task(
                self._heartbeat_loop(task_id, store, heartbeat_stop)
            )

            creators = store.creators.all()
            await store.sync_tasks.update(task_id, total_creators=len(creators))

            total_new = 0
            errors: list[str] = []

            for idx, creator in enumerate(creators):
                if idx > 0:
                    await asyncio.sleep(1)

                task = store.sync_tasks.get(task_id)
                if task is None:
                    return
                await store.sync_tasks.update(task_id, current_creator_name=creator.name)

                try:
                    new_count = await self.sync_creator(store, creator)
                    total_new += new_count
                except Exception as exc:
                    errors.append(f"{creator.name}: {exc}")

                task = store.sync_tasks.get(task_id)
                if task is None:
                    return
                await store.sync_tasks.update(
                    task_id,
                    completed_creators=(task.completed_creators + 1),
                    new_videos=total_new,
                    current_creator_name=None,
                )

            task = store.sync_tasks.get(task_id)
            if task is None:
                return
            finished_at = _now_utc()
            if errors:
                await store.sync_tasks.update(
                    task_id,
                    status="failed",
                    current_creator_name=None,
                    new_videos=total_new,
                    finished_at=finished_at,
                    error_message="\n".join(errors),
                )
            else:
                await store.sync_tasks.update(
                    task_id,
                    status="completed",
                    current_creator_name=None,
                    new_videos=total_new,
                    finished_at=finished_at,
                )

        except Exception as exc:
            try:
                await store.sync_tasks.update(
                    task_id,
                    status="failed",
                    error_message=str(exc),
                    finished_at=_now_utc(),
                )
            except Exception:
                pass
        finally:
            heartbeat_stop.set()
            if hb_task is not None:
                hb_task.cancel()
                try:
                    await hb_task
                except asyncio.CancelledError:
                    pass

    # ── 立即同步标签管理 ──────────────────────────────────────────

    def list_immediate_tags(self, store: DataStore) -> list[TagSyncConfig]:
        """返回所有立即同步标签配置。"""
        return store.tag_sync_configs.all()

    async def add_immediate_tag(self, store: DataStore, tag_id: int) -> TagSyncConfig:
        """将指定标签设为立即同步模式；已配置时直接返回现有配置。"""
        if store.tags.get(tag_id) is None:
            raise ValueError(f"标签 id={tag_id} 不存在")
        existing = store.tag_sync_configs.filter(tag_id=tag_id)
        if existing:
            return existing[0]
        config = TagSyncConfig(tag_id=tag_id, sync_mode="immediate")
        await store.tag_sync_configs.add(config)
        return config

    async def remove_immediate_tag(self, store: DataStore, tag_id: int) -> bool:
        """移除标签的立即同步配置；未配置时返回 False。"""
        configs = store.tag_sync_configs.filter(tag_id=tag_id)
        if not configs:
            return False
        await store.tag_sync_configs.delete(configs[0].id)
        return True
