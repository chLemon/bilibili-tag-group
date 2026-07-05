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
        不会更新 Creator 的名称/头像等元数据。

        返回：本次新增的视频数量
        """
        uid = _uid_from_profile_url(creator.profile_url)

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
            else:
                video = Video(
                    bvid=fv.bvid,
                    creator_id=creator.id,
                    title=fv.title,
                    video_url=fv.video_url,
                    published_at=fv.published_at,
                    duration_seconds=fv.duration_seconds,
                )
                db_session.add(video)
                db_session.flush()
                status = VideoStatus(video_id=video.id, watched=False)
                video.status = status
                db_session.add(status)
                new_count += 1

        creator.last_synced_at = _now_utc()
        db_session.flush()
        return new_count

    # ── 异步全量同步 ──────────────────────────────────────────────

    def start_async_sync(self, request_db: Session) -> SyncTask:
        """启动异步全量同步：创建 SyncTask 并启动后台线程，立即返回。

        如果已有正在运行的同步任务，直接返回该任务（幂等）。
        """
        from app.database import SessionLocal

        # 检查是否有正在运行的任务
        existing = (
            request_db.query(SyncTask)
            .filter_by(status="running")
            .order_by(SyncTask.started_at.desc())
            .first()
        )
        if existing is not None:
            return existing

        # 计算 total_creators
        total = request_db.query(Creator).filter_by(enabled=True).count()

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

        # 启动后台线程执行同步
        thread = _threading.Thread(
            target=self._run_async_sync,
            args=(task_id, SessionLocal),
            daemon=True,
        )
        thread.start()

        return task

    def _run_async_sync(self, task_id: int, SessionLocal) -> None:
        """后台线程：逐个同步 UP 主，更新 SyncTask 进度。"""
        db = SessionLocal()
        try:
            task = db.query(SyncTask).filter_by(id=task_id).first()
            if task is None:
                return

            creators = db.query(Creator).filter_by(enabled=True).all()
            task.total_creators = len(creators)
            task.heartbeat_at = _now_utc()
            db.commit()

            total_new = 0
            errors: list[str] = []

            for idx, creator in enumerate(creators):
                if idx > 0:
                    _time.sleep(1)

                # 更新当前正在处理的 UP 主
                task = db.query(SyncTask).filter_by(id=task_id).first()
                if task is None:
                    return
                task.current_creator_name = creator.name
                task.heartbeat_at = _now_utc()
                db.commit()

                try:
                    new_count = self.sync_creator(db, creator)
                    total_new += new_count
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    errors.append(f"{creator.name}: {exc}")

                # 更新完成数
                task = db.query(SyncTask).filter_by(id=task_id).first()
                if task is None:
                    return
                task.completed_creators += 1
                task.new_videos = total_new
                task.current_creator_name = None
                task.heartbeat_at = _now_utc()
                db.commit()

            # 全部完成
            task = db.query(SyncTask).filter_by(id=task_id).first()
            if task is None:
                return
            task.current_creator_name = None
            task.new_videos = total_new
            task.finished_at = _now_utc()
            task.heartbeat_at = _now_utc()
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
                    task.heartbeat_at = _now_utc()
                    db.commit()
            except Exception:
                pass
        finally:
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
            creators = db_session.query(Creator).filter_by(enabled=True).all()
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
