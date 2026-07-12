"""同步核心服务：将 B 站抓取结果写入本地数据库。"""
from __future__ import annotations

import threading as _threading
import time as _time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.fetcher.models import FetchedVideo
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.models.creator import Creator
from app.models.sync_log import SyncLog
from app.models.sync_task import SyncTask
from app.models.video import Video
from app.models.video_status import VideoStatus


def _now_utc() -> datetime:
    """返回当前 UTC 时间（naive datetime，不含时区信息）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uid_from_profile_url(profile_url: str) -> str:
    """从 B 站主页 URL 中提取 uid。"""
    return profile_url.rstrip("/").split("/")[-1]


class SyncService:
    """同步服务：协调抓取与数据库写入，保持本地视频数据与 B 站同步。"""

    def __init__(self, fetcher: PlaywrightBilibiliFetcher | None = None) -> None:
        self._fetcher = fetcher if fetcher is not None else PlaywrightBilibiliFetcher()

    @staticmethod
    def _get_immediate_tag_ids(db_session: Session) -> set[int]:
        from app.models.tag_sync_config import TagSyncConfig
        return {
            row[0] for row in db_session.query(TagSyncConfig.tag_id).all()
        }

    @staticmethod
    def _creator_has_immediate_tag(
        db_session: Session, creator_id: int, immediate_tag_ids: set[int]
    ) -> bool:
        if not immediate_tag_ids:
            return False
        from app.models.creator_tag import CreatorTag
        creator_tag_ids = {
            row[0]
            for row in db_session.query(CreatorTag.tag_id).filter_by(
                creator_id=creator_id
            ).all()
        }
        return bool(creator_tag_ids & immediate_tag_ids)

    def sync_creator(self, db_session: Session, creator: Creator) -> int:
        """同步单个 Creator 的视频列表。

        - 拥有"立即同步"标签 → 绕过 TTL 缓存
        - 其余 → 使用 TTL 缓存
        - 同时更新 Creator 的名称/头像、视频的封面

        返回：本次新增的视频数量
        """
        uid = _uid_from_profile_url(creator.profile_url)

        # 更新 UP 主元数据（名称、头像）
        try:
            info = self._fetcher.fetch_creator_info(uid, ttl_cache=False)
            if info.get("name"):
                creator.name = info["name"]
            if info.get("avatar_url"):
                creator.avatar_url = info["avatar_url"]
            if info.get("video_count") is not None:
                creator.video_count = info["video_count"]
        except Exception:
            pass  # 元数据更新失败不影响视频同步

        immediate_tag_ids = self._get_immediate_tag_ids(db_session)
        use_ttl = not self._creator_has_immediate_tag(
            db_session, creator.id, immediate_tag_ids
        )
        fetched_list: list[FetchedVideo] = self._fetcher.fetch_videos(uid, ttl_cache=use_ttl)

        existing_videos: dict[str, Video] = {
            v.bvid: v
            for v in db_session.query(Video).filter_by(creator_id=creator.id).all()
        }

        new_count = 0
        for fv in fetched_list:
            if fv.bvid in existing_videos:
                video = existing_videos[fv.bvid]
                video.title = fv.title
                video.video_url = fv.video_url
                video.published_at = fv.published_at
                video.duration_seconds = fv.duration_seconds
                if fv.cover_url:
                    video.cover_url = fv.cover_url
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
                db_session.add(video)
                db_session.flush()
                status = VideoStatus(video_id=video.id)
                video.status = status
                db_session.add(status)
                new_count += 1

        creator.last_synced_at = _now_utc()
        db_session.flush()
        return new_count

    # ── 异步全量同步 ──────────────────────────────────────────────

    # 心跳更新间隔（独立心跳线程），对应前端轮询周期
    _HEARTBEAT_INTERVAL = 15
    # 心跳超过此秒数视为进程已崩溃，与前端 DEAD_THRESHOLD_SEC 保持一致
    _HEARTBEAT_DEAD_SEC = 45

    def start_async_sync(self, request_db: Session) -> SyncTask:
        """启动异步全量同步：创建 SyncTask 并启动后台线程，立即返回。

        如果已有正在运行且心跳正常的任务，直接返回该任务（幂等）。
        如果旧任务心跳已超时（进程崩溃），将其标记为 failed 并创建新任务。
        """
        from app.database import SessionLocal

        existing = (
            request_db.query(SyncTask)
            .filter_by(status="running")
            .order_by(SyncTask.started_at.desc())
            .first()
        )
        if existing is not None:
            # 检查旧任务是否已是僵尸（心跳超时意味着进程已崩溃）
            if existing.heartbeat_at is not None:
                age_sec = (_now_utc() - existing.heartbeat_at).total_seconds()
                if age_sec >= self._HEARTBEAT_DEAD_SEC:
                    existing.status = "failed"
                    existing.error_message = "任务进程崩溃，心跳超时未更新"
                    existing.finished_at = _now_utc()
                    request_db.flush()
                else:
                    # 心跳正常，真正的幂等返回
                    return existing
            else:
                # 无心跳记录，视为正常 running（刚创建）
                return existing

        # 计算 total_creators
        total = request_db.query(Creator).count()

        task = SyncTask(
            status="running",
            total_creators=total,
            completed_creators=0,
            new_videos=0,
            started_at=_now_utc(),
            heartbeat_at=_now_utc(),
        )
        request_db.add(task)
        request_db.flush()
        task_id = task.id

        # 必须在启动线程之前提交，否则后台线程的独立连接看不到这条新记录
        request_db.commit()

        # 启动后台线程执行同步
        thread = _threading.Thread(
            target=self._run_async_sync,
            args=(task_id, SessionLocal),
            daemon=True,
        )
        thread.start()

        return task

    @staticmethod
    def _heartbeat_loop(task_id: int, SessionLocal, stop_event: _threading.Event) -> None:
        """独立心跳线程：每隔 _HEARTBEAT_INTERVAL 秒更新 heartbeat_at。

        与同步耗时解耦——即使 sync_creator 卡在网络请求上，心跳仍正常推进。
        stop_event 由主同步线程在 finally 中设置，保证同步线程结束时心跳线程一定退出。
        """
        db = SessionLocal()
        try:
            while not stop_event.wait(SyncService._HEARTBEAT_INTERVAL):
                try:
                    task = db.query(SyncTask).filter_by(id=task_id).first()
                    if task is None:
                        return
                    task.heartbeat_at = _now_utc()
                    db.commit()
                except Exception:
                    db.rollback()
        finally:
            db.close()

    def _run_async_sync(self, task_id: int, SessionLocal) -> None:
        """后台线程：逐个同步 UP 主，更新 SyncTask 进度。

        启动独立心跳线程保证 heartbeat_at 持续更新，
        不因 sync_creator 网络耗时而中断。finally 确保心跳线程随主线程退出。
        """
        db = SessionLocal()
        heartbeat_stop = _threading.Event()
        hb_thread = None
        try:
            task = db.query(SyncTask).filter_by(id=task_id).first()
            if task is None:
                return

            # 启动独立心跳线程，与同步耗时解耦
            hb_thread = _threading.Thread(
                target=self._heartbeat_loop,
                args=(task_id, SessionLocal, heartbeat_stop),
                daemon=True,
            )
            hb_thread.start()

            creators = db.query(Creator).all()
            task.total_creators = len(creators)
            db.commit()

            total_new = 0
            errors: list[str] = []

            for idx, creator in enumerate(creators):
                if idx > 0:
                    _time.sleep(1)

                task = db.query(SyncTask).filter_by(id=task_id).first()
                if task is None:
                    return
                task.current_creator_name = creator.name
                db.commit()

                try:
                    new_count = self.sync_creator(db, creator)
                    total_new += new_count
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    errors.append(f"{creator.name}: {exc}")

                task = db.query(SyncTask).filter_by(id=task_id).first()
                if task is None:
                    return
                task.completed_creators += 1
                task.new_videos = total_new
                task.current_creator_name = None
                db.commit()

            # 全部完成
            task = db.query(SyncTask).filter_by(id=task_id).first()
            if task is None:
                return
            task.current_creator_name = None
            task.new_videos = total_new
            task.finished_at = _now_utc()
            if errors:
                task.status = "failed"
                task.error_message = "\n".join(errors)
            else:
                task.status = "completed"
            db.commit()

            # 同时写一条 SyncLog 保留历史
            log = SyncLog(
                scope="all",
                status="success" if not errors else "failed",
                new_videos=total_new,
                error_message="\n".join(errors) if errors else None,
                started_at=task.started_at,
                finished_at=task.finished_at,
            )
            db.add(log)
            db.commit()

        except Exception as exc:
            db.rollback()
            try:
                task = db.query(SyncTask).filter_by(id=task_id).first()
                if task is not None:
                    task.status = "failed"
                    task.error_message = str(exc)
                    task.finished_at = _now_utc()
                    db.commit()
            except Exception:
                pass
        finally:
            heartbeat_stop.set()
            if hb_thread is not None:
                hb_thread.join(timeout=5)
            db.close()

    # ── 调度器用的同步（同步执行，阻塞返回） ──────────────────────

    def sync_all(self, db_session: Session) -> SyncLog:
        """供 APScheduler 定时任务使用：同步阻塞执行，完成后返回 SyncLog。"""
        log = SyncLog(
            scope="all",
            status="failed",
            new_videos=0,
            started_at=_now_utc(),
        )
        db_session.add(log)
        db_session.flush()

        try:
            creators = db_session.query(Creator).all()
            total_new = 0
            errors: list[str] = []
            for idx, creator in enumerate(creators):
                if idx > 0:
                    _time.sleep(1)
                try:
                    total_new += self.sync_creator(db_session, creator)
                except Exception as exc:
                    errors.append(f"creator_id={creator.id}: {exc}")

            log.new_videos = total_new
            if errors:
                log.status = "failed"
                log.error_message = "\n".join(errors)
            else:
                log.status = "success"

        except Exception as exc:
            log.status = "failed"
            log.error_message = str(exc)

        finally:
            log.finished_at = _now_utc()

        db_session.flush()
        return log
