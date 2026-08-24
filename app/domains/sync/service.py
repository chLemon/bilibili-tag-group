"""同步核心服务：将 B 站抓取结果写入本地数据库。"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from app.domains.creators.models import Creator
from app.domains.creators.service import CreatorService
from app.domains.sync.models import SyncTask
from app.domains.tags.models import TagSyncConfig
from app.domains.videos.models import Video, VideoStatus
from app.fetcher.models import FetchedVideo
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.shared.store import DataStore
from app.shared.time import now_utc as _now_utc

logger = logging.getLogger(__name__)


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
        creator_tag_ids = {row.tag_id for row in store.creator_tags.filter(creator_id=creator_id)}
        return bool(creator_tag_ids & immediate_tag_ids)

    async def sync_creator(
        self,
        store: DataStore,
        creator: Creator,
        task_id: int | None = None,
        force: bool = False,
    ) -> int:
        """同步 UP 主的信息。

        task_id 非空时，抓取过程中每完成一页把页码写入对应 SyncTask，
        供前端展示页级进度。

        force=True 时跳过 TTL 节流，用于手动触发的单 UP 主同步；
        enabled=False 仍然跳过（停用语义优先于手动触发）。
        """
        if not creator.enabled:
            return 0

        if not force:
            immediate_tag_ids = self._get_immediate_tag_ids(store)
            if self._creator_has_immediate_tag(store, creator.id, immediate_tag_ids):
                if creator.last_synced_at and (_now_utc() - creator.last_synced_at) < timedelta(
                    minutes=5
                ):
                    return 0
            else:
                if creator.last_synced_at and (_now_utc() - creator.last_synced_at) < timedelta(
                    minutes=50
                ):
                    return 0

        uid = CreatorService.uid_from_profile_url(creator.profile_url)

        info: dict | None = None
        try:
            info = await self._fetcher.fetch_creator_info(uid)
            await store.creators.update(
                creator.id,
                name=info["name"],
                avatar_url=info["avatar_url"],
                video_count=info["video_count"],
            )
        except Exception:
            # 信息更新失败不阻断视频同步，但必须留痕：风控时段若静默跳过，
            # 表象会误成"无新视频"
            logger.warning("获取 UP 主信息失败，跳过信息更新 uid=%s", uid, exc_info=True)

        # B 站侧视频总数为 0 时无投稿，fetch_new_videos 会等不到卡片抛 FetchError；
        # 信息更新成功且 video_count=0 时直接返回，跳过无意义的卡片抓取
        if info is not None and info.get("video_count") == 0:
            await store.creators.update(creator.id, last_synced_at=_now_utc())
            return 0

        existing_videos_list = store.videos.filter(creator_id=creator.id)
        existing_videos: dict[str, Video] = {v.bvid: v for v in existing_videos_list}
        # 传给 fetcher 用于早停判定；早停时 fetcher 会把本地已有但本次未抓到的补回返回值
        known = [
            FetchedVideo(
                bvid=v.bvid,
                title=v.title,
                video_url=v.video_url,
                published_at=v.published_at,
                duration_seconds=v.duration_seconds,
                cover_url=v.cover_url,
            )
            for v in existing_videos_list
        ]

        async def _on_page_progress(current: int, total: int) -> None:
            if task_id is not None:
                await store.sync_tasks.update(
                    task_id, current_creator_progress=f"已抓 {current}/{total} 页"
                )

        fetched_list: list[FetchedVideo] = await self._fetcher.fetch_new_videos(
            uid, known_videos=known, on_page_progress=_on_page_progress
        )

        new_count = 0
        for fv in fetched_list:
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

        全局只有一个同步任务能 running：
        - 已有全量 running：心跳超时则标记失败并新建；否则返回 (existing, False)，
          调用方不得再启动执行协程（幂等）。
        - 已有单 UP 主 running：抛 ValueError，调用方应返回 409。

        check-then-create 整体放在 sync_tasks 的跨进程临界区内，
        防止多实例同时通过 running 检查而各建一个任务。
        """
        async with store.sync_tasks.locked() as repo:
            running = [t for t in repo.all() if t.status == "running"]
            if running:
                existing = max(running, key=lambda t: t.started_at)
                if existing.scope == "creator":
                    raise ValueError(
                        f"已有单 UP 主同步任务在跑 (id={existing.id})，请等其完成后再触发全量同步"
                    )
                if existing.heartbeat_at is not None:
                    age_sec = (_now_utc() - existing.heartbeat_at).total_seconds()
                    if age_sec >= self._HEARTBEAT_DEAD_SEC:
                        repo.update_nolock(
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
            repo.add_nolock(task)
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

            hb_task = asyncio.create_task(self._heartbeat_loop(task_id, store, heartbeat_stop))

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
                await store.sync_tasks.update(
                    task_id,
                    current_creator_name=creator.name,
                    current_creator_progress=None,
                )

                try:
                    # 页级进度由 sync_creator 通过回调直接写 SyncTask，无需轮询
                    new_count = await self.sync_creator(store, creator, task_id=task_id)
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
                    current_creator_progress=None,
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

    # ── 单 UP 主同步（后台协程） ────────────────────────────────

    async def start_single_creator_sync(
        self, store: DataStore, creator: Creator
    ) -> tuple[SyncTask, bool]:
        """创建单 UP 主同步任务并返回 (task, created)。

        全局只有一个同步任务能 running：
        - 同 UP 主已有 running 的单 UP 主任务 → 返回 (existing, False)，幂等。
        - 其他任何 running 任务（全量或不同 UP 主的单 UP 主）→ 抛 ValueError，
          调用方应返回 409。
        """
        async with store.sync_tasks.locked() as repo:
            for t in repo.all():
                if t.status != "running":
                    continue
                if t.scope == "creator" and t.creator_id == creator.id:
                    return t, False
                raise ValueError(
                    f"已有同步任务在跑 (id={t.id}, scope={t.scope})，请等其完成后再触发"
                )

            task = SyncTask(
                scope="creator",
                creator_id=creator.id,
                status="running",
                total_creators=1,
                completed_creators=0,
                new_videos=0,
                started_at=_now_utc(),
                heartbeat_at=_now_utc(),
            )
            repo.add_nolock(task)
            return task, True

    async def run_single_creator_sync(
        self, task_id: int, store: DataStore, creator_id: int
    ) -> None:
        """后台协程：同步单个 UP 主并更新任务进度。"""
        heartbeat_stop = asyncio.Event()
        hb_task = None
        try:
            task = store.sync_tasks.get(task_id)
            if task is None:
                return

            creator = store.creators.get(creator_id)
            if creator is None:
                await store.sync_tasks.update(
                    task_id,
                    status="failed",
                    error_message=f"UP 主 id={creator_id} 不存在",
                    finished_at=_now_utc(),
                )
                return

            hb_task = asyncio.create_task(self._heartbeat_loop(task_id, store, heartbeat_stop))

            await store.sync_tasks.update(
                task_id,
                current_creator_name=creator.name,
                current_creator_progress=None,
            )

            try:
                new_count = await self.sync_creator(
                    store, creator, task_id=task_id, force=True
                )
            except Exception as exc:
                logger.exception(
                    "单 UP 主同步失败 task_id=%s creator_id=%s", task_id, creator_id
                )
                await store.sync_tasks.update(
                    task_id,
                    status="failed",
                    completed_creators=1,
                    current_creator_name=None,
                    current_creator_progress=None,
                    error_message=str(exc) or repr(exc),
                    finished_at=_now_utc(),
                )
                return

            await store.sync_tasks.update(
                task_id,
                status="completed",
                completed_creators=1,
                new_videos=new_count,
                current_creator_name=None,
                current_creator_progress=None,
                finished_at=_now_utc(),
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
