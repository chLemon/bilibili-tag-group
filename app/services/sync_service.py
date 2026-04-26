"""同步核心服务：将 B 站抓取结果写入本地数据库。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.fetcher.bilibili_fetcher import BilibiliFetcher
from app.fetcher.models import FetchedVideo
from app.models.creator import Creator
from app.models.sync_log import SyncLog
from app.models.video import Video
from app.models.video_status import VideoStatus


def _now_utc() -> datetime:
    """返回当前 UTC 时间（naive datetime，不含时区信息）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uid_from_profile_url(profile_url: str) -> str:
    """从 B 站主页 URL 中提取 uid。

    例如：
    - "https://space.bilibili.com/12345" -> "12345"
    - "https://space.bilibili.com/12345/" -> "12345"
    """
    return profile_url.rstrip("/").split("/")[-1]


class SyncService:
    """同步服务：协调抓取与数据库写入，保持本地视频数据与 B 站同步。"""

    def __init__(self, fetcher: BilibiliFetcher | None = None) -> None:
        """初始化同步服务。

        参数：
            fetcher: 可注入自定义 fetcher，默认使用 BilibiliFetcher()
        """
        self._fetcher = fetcher if fetcher is not None else BilibiliFetcher()

    def sync_creator(self, db_session: Session, creator: Creator) -> int:
        """同步单个 Creator 的视频列表。

        对已存在的视频：更新标题/链接/发布时间/时长，但不修改观看状态。
        对新视频：创建 Video 记录和 watched=False 的 VideoStatus。

        参数：
            db_session: SQLAlchemy Session
            creator: 要同步的 Creator 对象

        返回：
            本次新增的视频数量
        """
        uid = _uid_from_profile_url(creator.profile_url)
        fetched_list: list[FetchedVideo] = self._fetcher.fetch_videos(uid)

        # 获取该 creator 已有视频的 bvid -> Video 映射
        existing_videos: dict[str, Video] = {
            v.bvid: v
            for v in db_session.query(Video).filter_by(creator_id=creator.id).all()
        }

        new_count = 0
        for fv in fetched_list:
            if fv.bvid in existing_videos:
                # 更新已有视频的元数据，但不触碰观看状态
                video = existing_videos[fv.bvid]
                video.title = fv.title
                video.video_url = fv.video_url
                video.published_at = fv.published_at
                video.duration_seconds = fv.duration_seconds
            else:
                # 新视频：创建 Video 并同步创建默认未看的 VideoStatus
                video = Video(
                    bvid=fv.bvid,
                    creator_id=creator.id,
                    title=fv.title,
                    video_url=fv.video_url,
                    published_at=fv.published_at,
                    duration_seconds=fv.duration_seconds,
                )
                db_session.add(video)
                db_session.flush()  # 获得 video.id

                # 通过 relationship 属性设置，确保 in-memory 状态一致
                status = VideoStatus(video_id=video.id, watched=False)
                video.status = status
                db_session.add(status)
                new_count += 1

        # 将所有变更（包括既有视频的字段更新）写入数据库
        db_session.flush()
        return new_count

    def sync_all(self, db_session: Session) -> SyncLog:
        """同步所有已启用（enabled=True）Creator 的视频列表。

        创建 scope="all" 的 SyncLog，记录同步结果：
        - 全部成功：status="success"
        - 任一 creator 失败：status="failed"，error_message 写入失败信息
        单个 creator 失败不会中断其余 creator 的同步。
        无论成败，均在 finally 中设置 finished_at。

        参数：
            db_session: SQLAlchemy Session

        返回：
            已持久化的 SyncLog 对象
        """
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
            for creator in creators:
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
