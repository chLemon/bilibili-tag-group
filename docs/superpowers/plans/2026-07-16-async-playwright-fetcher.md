# PlaywrightBilibiliFetcher 异步化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `PlaywrightBilibiliFetcher` 及其调用链路从 Playwright 同步 API 迁移到异步 API。

**Architecture:** fetcher → sync_service → scheduler/router 全链路异步。移除 threading.local、threading.Thread、APScheduler，统一用 asyncio。浏览器实例直接存储在 fetcher 实例上，调度用 `asyncio.create_task` 管理。

**Tech Stack:** Playwright async_api, asyncio, FastAPI (async endpoints), pytest-asyncio

## Global Constraints

- Python >= 3.12
- 所有文档和注释用中文
- 时间字段使用 naive UTC
- 不引入新的第三方依赖（除 pytest-asyncio 替代 pytest-anyio）

---

### Task 1: 更新测试依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 替换依赖**

将 `pyproject.toml` 中 `[project.optional-dependencies]` 的 dev 列表里的 `pytest-anyio>=0.0.0` 替换为 `pytest-asyncio>=0.24,<1.0`，同时移除 `apscheduler>=3.10,<4.0`：

```toml
[project]
name = "my-bilibili"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1.0",
  "uvicorn>=0.30,<1.0",
  "sqlalchemy>=2.0,<3.0",
  "alembic>=1.13,<2.0",
  "pydantic-settings>=2.2,<3.0",
  "playwright>=1.48,<2.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0,<9.0",
  "pytest-asyncio>=0.24,<1.0",
  "ruff>=0.4,<1.0",
]
```

- [ ] **Step 2: 安装更新的依赖**

```bash
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 3: 验证 pytest-asyncio 可用**

```bash
.venv/bin/pytest --co 2>&1 | Select-String "asyncio"
```
Expected: 应看到 `asyncio_mode` 相关配置项。

- [ ] **Step 4: 配置 pytest asyncio mode**

在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 中添加 asyncio 模式：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore: 替换 pytest-anyio / apscheduler 为 pytest-asyncio，添加 asyncio_mode=auto"
```

---

### Task 2: 将 playwright_fetcher.py 改为异步

**Files:**
- Modify: `app/fetcher/playwright_fetcher.py`

**Interfaces:**
- Consumes: `async_playwright` from Playwright, `asyncio`
- Produces: `PlaywrightBilibiliFetcher` 类，实例方法均为 async（缓存方法除外）

- [ ] **Step 1: 重写 playwright_fetcher.py**

```python
"""使用 Playwright 无头浏览器抓取 B 站视频数据。

打开 UP 主投稿视频页面，通过 DOM 提取视频卡片数据并逐页翻页，
绕过 WBI API 签名风控。

浏览器实例存储在 fetcher 实例上，在单个事件循环内复用。
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta, timezone

from playwright.async_api import Browser, BrowserContext, async_playwright
from sqlalchemy import text

from app.database import SessionLocal
from app.fetcher.models import FetchedVideo


_logger = logging.getLogger(__name__)


class FetchError(Exception):
    """抓取失败时抛出此异常。"""


# ── CSS 选择器 ────────────────────────────────────────────────────

_CARD_CLASS = ".bili-video-card"
_TITLE_CLASS = ".bili-video-card__title"
_SUBTITLE_CLASS = ".bili-video-card__subtitle"
_DURATION_CLASS = ".bili-cover-card__stat"
_NEXT_PAGE_SELECTOR = ".vui_pagenation--btn-side"
_VIDEO_COUNT_SELECTOR = ".side-nav__item.active .side-nav__item__sub-text"

# ── 时间与重试配置 ────────────────────────────────────────────────

_DELAY_MIN = 1.0
_DELAY_MAX = 2.5
_PAGE_TIMEOUT = 30_000
_CARD_WAIT_TIMEOUT = 10_000
_MAX_PAGES = 300
_RETRY_COUNT = 4
_RETRY_BACKOFF = 2

# ── 缓存 TTL ──────────────────────────────────────────────────────

_NAME_CACHE_TTL = timedelta(hours=24)
_VIDEOS_CACHE_TTL = timedelta(hours=1)

# ── 浏览器启动参数 ────────────────────────────────────────────────

_BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-sandbox",
    "--disable-setuid-sandbox",
]

# ── 提取正则 ──────────────────────────────────────────────────────

_BVID_RE = re.compile(r"/video/(BV\w+)")
_RELATIVE_RE = re.compile(r"(\d+)\s*(分钟|小时|天|个月)前")


class PlaywrightBilibiliFetcher:
    """使用 Playwright 无头浏览器从 B 站空间页抓取视频列表和 UP 主信息。

    内部通过 SessionLocal 管理 SQLite 缓存，TTL 内命中缓存则跳过远程请求。
    浏览器实例存储在实例变量上，通过 close_browser() 释放资源。
    """

    def __init__(self, cookie: str | None = None, headless: bool = True) -> None:
        self._cookie = cookie
        self._headless = headless
        self._playwright = None
        self._browser = None

    # ── 浏览器生命周期 ──────────────────────────────────────────

    async def _get_browser(self) -> Browser:
        """获取浏览器实例，断开时自动重连。"""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless, args=_BROWSER_ARGS
            )
        elif not self._browser.is_connected():
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless, args=_BROWSER_ARGS
            )
        return self._browser

    async def close_browser(self) -> None:
        """关闭浏览器实例，释放资源。"""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    # ── 浏览器上下文 ────────────────────────────────────────────

    async def _create_context(self) -> BrowserContext:
        """创建带反检测配置和 Cookie 注入的浏览器上下文。"""
        browser = await self._get_browser()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)
        if self._cookie:
            cookies = []
            for part in self._cookie.split(";"):
                part = part.strip()
                if "=" in part:
                    name, _, value = part.partition("=")
                    cookies.append({
                        "name": name.strip(),
                        "value": value.strip(),
                        "domain": ".bilibili.com",
                        "path": "/",
                    })
            if cookies:
                await context.add_cookies(cookies)
        return context

    # ── 缓存读写 ────────────────────────────────────────────────

    @staticmethod
    def _cache_key(uid: str, kind: str) -> str:
        return f"fetcher:{uid}:{kind}"

    def _get_cached(self, uid: str, kind: str) -> dict | None:
        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT value FROM cache WHERE key = :key"),
                {"key": self._cache_key(uid, kind)},
            ).fetchone()
            if row is None:
                return None
            data = json.loads(row[0])
            ts = datetime.fromisoformat(data["ts"])
            ttl = _NAME_CACHE_TTL if kind == "name" else _VIDEOS_CACHE_TTL
            if datetime.now(timezone.utc).replace(tzinfo=None) - ts > ttl:
                return None
            return data["payload"]
        except Exception:
            return None
        finally:
            db.close()

    def _set_cache(self, uid: str, kind: str, payload) -> None:
        db = SessionLocal()
        try:
            data = json.dumps(
                {
                    "ts": datetime.now(timezone.utc)
                    .replace(tzinfo=None)
                    .isoformat(),
                    "payload": payload,
                },
                ensure_ascii=False,
            )
            db.execute(
                text(
                    "INSERT OR REPLACE INTO cache (key, value) "
                    "VALUES (:key, :value)"
                ),
                {"key": self._cache_key(uid, kind), "value": data},
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    # ── 公开抓取方法 ────────────────────────────────────────────

    async def fetch_videos(
        self, uid: str, ttl_cache: bool = True
    ) -> list[FetchedVideo]:
        if ttl_cache:
            cached = self._get_cached(uid, "videos")
            if cached is not None:
                return [
                    FetchedVideo(
                        bvid=v["bvid"],
                        title=v["title"],
                        video_url=v["video_url"],
                        published_at=datetime.fromisoformat(v["published_at"])
                        if v.get("published_at")
                        else None,
                        duration_seconds=v["duration_seconds"],
                        cover_url=v.get("cover_url"),
                    )
                    for v in cached
                ]

        last_error: Exception | None = None

        for attempt in range(_RETRY_COUNT + 1):
            if attempt > 0:
                await asyncio.sleep(_RETRY_BACKOFF * attempt)

            context = await self._create_context()
            page = await context.new_page()
            try:
                await page.goto(
                    f"https://space.bilibili.com/{uid}/upload/video",
                    wait_until="networkidle",
                    timeout=_PAGE_TIMEOUT,
                )
                if not await self._wait_for_cards(page):
                    last_error = FetchError(
                        f"未能从页面提取到视频数据，uid={uid}"
                    )
                    continue

                videos = await self._extract_all_pages(page)
                if videos:
                    self._set_cache(
                        uid,
                        "videos",
                        [
                            {
                                "bvid": v.bvid,
                                "title": v.title,
                                "video_url": v.video_url,
                                "published_at": v.published_at.isoformat()
                                if v.published_at
                                else None,
                                "duration_seconds": v.duration_seconds,
                            }
                            for v in videos
                        ],
                    )
                    return videos

                last_error = FetchError(
                    f"未能从页面提取到视频数据，uid={uid}"
                )
            except Exception as exc:
                last_error = FetchError(
                    f"页面加载失败，uid={uid}: {exc}"
                )
            finally:
                await page.close()
                await context.close()

        raise last_error  # type: ignore[return-value]

    async def fetch_creator_info(
        self, uid: str, ttl_cache: bool = True
    ) -> dict:
        if ttl_cache:
            cached = self._get_cached(uid, "name")
            if cached is not None:
                return cached

        context = await self._create_context()
        page = await context.new_page()
        try:
            await page.goto(
                f"https://space.bilibili.com/{uid}/upload/video",
                wait_until="networkidle",
                timeout=_PAGE_TIMEOUT,
            )
            name_el = page.locator(".nickname").first
            name = await name_el.text_content()
            if not name or not name.strip():
                raise FetchError(f"未能提取到 UP 主昵称，uid={uid}")
            name = name.strip()

            avatar_url: str | None = None
            try:
                avatar_img = page.locator("#h-avatar img, .avatar img, .b-avatar img").first
                if await avatar_img.count() > 0:
                    raw = await avatar_img.get_attribute("src") or ""
                    if raw:
                        avatar_url = f"https:{raw}" if raw.startswith("//") else raw
            except Exception:
                pass

            video_count: int | None = None
            try:
                nav_items = page.locator(".side-nav__item")
                count = await nav_items.count()
                for i in range(count):
                    item = nav_items.nth(i)
                    text_el = item.locator(".side-nav__item__main-text")
                    if await text_el.count() > 0 and "视频" in (await text_el.text_content() or ""):
                        count_el = item.locator(".side-nav__item__sub-text")
                        if await count_el.count() > 0:
                            count_text = (await count_el.text_content() or "").strip()
                            video_count = int(count_text)
                        break
            except Exception:
                pass

            result = {"name": name, "avatar_url": avatar_url, "video_count": video_count}
            self._set_cache(uid, "name", result)
            return result
        except FetchError:
            raise
        except Exception as exc:
            raise FetchError(
                f"获取 UP 主信息失败，uid={uid}: {exc}"
            ) from exc
        finally:
            await page.close()
            await context.close()

    async def fetch_creator_name(
        self, uid: str, ttl_cache: bool = True
    ) -> str:
        info = await self.fetch_creator_info(uid, ttl_cache)
        return info["name"]

    # ── 页面交互 ────────────────────────────────────────────────

    async def _wait_for_cards(self, page, max_refresh: int = 4) -> bool:
        for refresh in range(max_refresh + 1):
            try:
                await page.wait_for_selector(
                    _TITLE_CLASS, timeout=_CARD_WAIT_TIMEOUT
                )
                return True
            except Exception:
                if refresh < max_refresh:
                    await asyncio.sleep(random.uniform(_DELAY_MIN, _DELAY_MAX))
                    await page.reload(
                        wait_until="networkidle", timeout=_PAGE_TIMEOUT
                    )
        return False

    async def _extract_all_pages(self, page) -> list[FetchedVideo]:
        seen: set[str] = set()
        videos: list[FetchedVideo] = []

        count_el = page.locator(_VIDEO_COUNT_SELECTOR).first
        count_text = (await count_el.text_content() or "")
        total_count = int(count_text.strip())

        for page_num in range(_MAX_PAGES):
            await asyncio.sleep(random.uniform(_DELAY_MIN, _DELAY_MAX))

            page_bvids: set[str] = set()
            for video in await self._extract_videos_from_page(page):
                if video.bvid not in seen:
                    seen.add(video.bvid)
                    videos.append(video)
                page_bvids.add(video.bvid)

            _logger.info("第 %d 页，当页 %d 个视频，累计 %d 个", page_num + 1, len(page_bvids), len(videos))

            if total_count and len(videos) >= total_count:
                break

            if page_bvids and self._any_known(page_bvids):
                break

            next_btn = page.locator(_NEXT_PAGE_SELECTOR).last
            btn_class = await next_btn.get_attribute("class") or ""
            if "disabled" in btn_class:
                break

            await next_btn.click()
            if not await self._wait_for_cards(page):
                break
            await asyncio.sleep(
                random.uniform(_DELAY_MIN + 1, _DELAY_MAX + 1)
            )

        return videos

    # ── 数据提取 ────────────────────────────────────────────────

    @staticmethod
    async def _extract_videos_from_page(page) -> list[FetchedVideo]:
        videos: list[FetchedVideo] = []
        cards = page.locator(_CARD_CLASS)
        count = await cards.count()
        for i in range(count):
            try:
                video = await _parse_card(cards.nth(i))
                if video is not None:
                    videos.append(video)
            except Exception:
                continue
        return videos

    @staticmethod
    def _any_known(bvids: set[str]) -> bool:
        db = SessionLocal()
        try:
            placeholders = ",".join(
                f":b{i}" for i in range(len(bvids))
            )
            params = {f"b{i}": b for i, b in enumerate(bvids)}
            row = db.execute(
                text(
                    f"SELECT COUNT(*) FROM videos "
                    f"WHERE bvid IN ({placeholders})"
                ),
                params,
            ).fetchone()
            return row is not None and row[0] > 0
        except Exception:
            return False
        finally:
            db.close()


# ── 模块级解析函数 ──────────────────────────────────────────────────


async def _parse_card(card) -> FetchedVideo | None:
    cover_link = card.locator("a").first
    href = await cover_link.get_attribute("href") or ""
    m = _BVID_RE.search(href)
    if not m:
        return None
    bvid = m.group(1)

    title_el = card.locator(_TITLE_CLASS)
    title = (await title_el.text_content() or "").strip()

    subtitle_el = card.locator(_SUBTITLE_CLASS + " span")
    date_str = (await subtitle_el.text_content() or "").strip()

    stat_spans = card.locator(_DURATION_CLASS + " span")
    stat_count = await stat_spans.count()
    duration_str = ""
    if stat_count > 0:
        duration_str = (
            await stat_spans.nth(stat_count - 1).text_content() or ""
        ).strip()

    cover_url: str | None = None
    cover_area = card.locator(".bili-video-card__cover")
    if await cover_area.count() > 0:
        cover_img = cover_area.locator("img").first
        if await cover_img.count() > 0:
            raw = await cover_img.get_attribute("src") or ""
            if raw:
                cover_url = f"https:{raw}" if raw.startswith("//") else raw

    published_at = _parse_date(date_str) if date_str else None
    duration_seconds = _parse_duration(duration_str) if duration_str else 0

    return FetchedVideo(
        bvid=bvid,
        title=title,
        video_url=f"https://www.bilibili.com/video/{bvid}",
        published_at=published_at,
        duration_seconds=duration_seconds,
        cover_url=cover_url,
    )


def _parse_date(date_str: str) -> datetime | None:
    date_str = date_str.strip()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass

    try:
        parsed = datetime.strptime(date_str, "%m-%d")
        result = parsed.replace(year=now.year)
        if result > now:
            result = result.replace(year=now.year - 1)
        return result
    except ValueError:
        pass

    m = _RELATIVE_RE.match(date_str)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "分钟":
            delta_seconds = num * 60
        elif unit == "小时":
            delta_seconds = num * 3600
        elif unit == "天":
            delta_seconds = num * 86400
        elif unit == "个月":
            delta_seconds = num * 30 * 86400
        else:
            return None
        return (
            now - timedelta(seconds=delta_seconds)
        ).replace(hour=0, minute=0, second=0, microsecond=0)

    return None


def _parse_duration(length: str) -> int:
    parts = length.split(":")
    if len(parts) == 1:
        return int(parts[0])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
```

- [ ] **Step 2: 验证语法正确**

```bash
.venv/bin/python -c "from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add app/fetcher/playwright_fetcher.py
git commit -m "refactor: 将 PlaywrightBilibiliFetcher 从同步 API 迁移到异步 API"
```

---

### Task 3: 将 sync_service.py 改为异步

**Files:**
- Modify: `app/services/sync_service.py`

**Interfaces:**
- Consumes: `PlaywrightBilibiliFetcher` (async methods)
- Produces: `SyncService` 类，`sync_creator` 和 `sync_all` 改为 `async`；`start_async_sync` 保持同步（仅创建 DB 记录）；`_run_async_sync` 和 `_heartbeat_loop` 改为 `async`

- [ ] **Step 1: 重写 sync_service.py**

```python
"""同步核心服务：将 B 站抓取结果写入本地数据库。"""
from __future__ import annotations

import asyncio
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
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _uid_from_profile_url(profile_url: str) -> str:
    return profile_url.rstrip("/").split("/")[-1]


class SyncService:
    """同步服务：协调抓取与数据库写入，保持本地视频数据与 B 站同步。"""

    # 心跳更新间隔，对应前端轮询周期
    _HEARTBEAT_INTERVAL = 15
    # 心跳超过此秒数视为进程已崩溃
    _HEARTBEAT_DEAD_SEC = 45

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

    async def sync_creator(self, db_session: Session, creator: Creator) -> int:
        uid = _uid_from_profile_url(creator.profile_url)

        try:
            info = await self._fetcher.fetch_creator_info(uid, ttl_cache=False)
            if info.get("name"):
                creator.name = info["name"]
            if info.get("avatar_url"):
                creator.avatar_url = info["avatar_url"]
            if info.get("video_count") is not None:
                creator.video_count = info["video_count"]
        except Exception:
            pass

        immediate_tag_ids = self._get_immediate_tag_ids(db_session)
        use_ttl = not self._creator_has_immediate_tag(
            db_session, creator.id, immediate_tag_ids
        )
        fetched_list: list[FetchedVideo] = await self._fetcher.fetch_videos(uid, ttl_cache=use_ttl)

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

    # ── 异步全量同步（后台协程） ──────────────────────────────────

    def start_async_sync(self, request_db: Session) -> SyncTask:
        """创建 SyncTask 记录并提交，返回 task（协程由调用方启动）。

        如果已有正在运行且心跳正常的任务，直接返回该任务（幂等）。
        如果旧任务心跳已超时（进程崩溃），将其标记为 failed 并创建新任务。
        """
        existing = (
            request_db.query(SyncTask)
            .filter_by(status="running")
            .order_by(SyncTask.started_at.desc())
            .first()
        )
        if existing is not None:
            if existing.heartbeat_at is not None:
                age_sec = (_now_utc() - existing.heartbeat_at).total_seconds()
                if age_sec >= self._HEARTBEAT_DEAD_SEC:
                    existing.status = "failed"
                    existing.error_message = "任务进程崩溃，心跳超时未更新"
                    existing.finished_at = _now_utc()
                    request_db.flush()
                else:
                    return existing
            else:
                return existing

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
        request_db.commit()
        return task

    async def _heartbeat_loop(self, task_id: int, SessionLocal, stop_event: asyncio.Event) -> None:
        """独立心跳协程：每隔 _HEARTBEAT_INTERVAL 秒更新 heartbeat_at。"""
        db = SessionLocal()
        try:
            while not stop_event.is_set():
                await asyncio.sleep(self._HEARTBEAT_INTERVAL)
                if stop_event.is_set():
                    break
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

    async def _run_async_sync(self, task_id: int, SessionLocal) -> None:
        """后台协程：逐个同步 UP 主，更新 SyncTask 进度。"""
        db = SessionLocal()
        heartbeat_stop = asyncio.Event()
        hb_task = None
        try:
            task = db.query(SyncTask).filter_by(id=task_id).first()
            if task is None:
                return

            hb_task = asyncio.create_task(
                self._heartbeat_loop(task_id, SessionLocal, heartbeat_stop)
            )

            creators = db.query(Creator).all()
            task.total_creators = len(creators)
            db.commit()

            total_new = 0
            errors: list[str] = []

            for idx, creator in enumerate(creators):
                if idx > 0:
                    await asyncio.sleep(1)

                task = db.query(SyncTask).filter_by(id=task_id).first()
                if task is None:
                    return
                task.current_creator_name = creator.name
                db.commit()

                try:
                    new_count = await self.sync_creator(db, creator)
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
            if hb_task is not None:
                hb_task.cancel()
                try:
                    await hb_task
                except asyncio.CancelledError:
                    pass
            db.close()

    # ── 调度器用同步方法 ──────────────────────────────────────

    async def sync_all(self, db_session: Session) -> SyncLog:
        """供调度器使用：异步执行全量同步，完成后返回 SyncLog。"""
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
                    await asyncio.sleep(1)
                try:
                    total_new += await self.sync_creator(db_session, creator)
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
```

- [ ] **Step 2: 验证语法正确**

```bash
.venv/bin/python -c "from app.services.sync_service import SyncService; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/sync_service.py
git commit -m "refactor: 将 SyncService 改为异步，用 asyncio 替代 threading"
```

---

### Task 4: 替换调度层 — scheduler.py + main.py

**Files:**
- Modify: `app/scheduler.py`
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `SyncService.sync_all` (async), `PlaywrightBilibiliFetcher.close_browser` (async)
- Produces: `run_sync_loop` async function, `set_sync_context` for router injection

- [ ] **Step 1: 重写 scheduler.py**

```python
"""定时同步调度：使用 asyncio 循环替代 APScheduler。"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_sync_loop(sync_service, session_factory, interval_minutes: int) -> None:
    """每隔 interval_minutes 分钟执行一次全量同步。

    通过 asyncio.sleep 实现周期调度，与 FastAPI 共用同一事件循环。
    异常不向上传播，保证循环持续运行。
    """
    while True:
        await asyncio.sleep(interval_minutes * 60)
        db = session_factory()
        try:
            await sync_service.sync_all(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("定时全量同步失败")
        finally:
            db.close()
```

旧的 `build_scheduler()` 和 `get_sync_job_info()` 及 `SYNC_JOB_ID` 常量全部移除。

- [ ] **Step 2: 更新 main.py**

```python
"""FastAPI 应用入口：注册路由，通过 lifespan 管理定时同步调度器生命周期。"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import SessionLocal, run_migrations
from app.routers.creators import router as creators_router
from app.routers.sync import router as sync_router, set_sync_context
from app.routers.tags import router as tags_router
from app.routers.videos import router as videos_router
from app.scheduler import run_sync_loop
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.services.sync_service import SyncService

# ── 日志配置 ──────────────────────────────────────────────────────

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_file_handler = RotatingFileHandler(
    LOG_DIR / "app.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr),
        _file_handler,
    ],
)

logger = logging.getLogger(__name__)

_fetcher = PlaywrightBilibiliFetcher(
    cookie=settings.bilibili_cookie if settings.bilibili_cookie else None
)
_sync_svc = SyncService(fetcher=_fetcher)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    run_migrations()
    sync_loop_task = asyncio.create_task(
        run_sync_loop(_sync_svc, SessionLocal, settings.sync_interval_minutes)
    )
    set_sync_context(True, settings.sync_interval_minutes)
    try:
        yield
    finally:
        sync_loop_task.cancel()
        try:
            await sync_loop_task
        except asyncio.CancelledError:
            pass
        await _fetcher.close_browser()


app = FastAPI(title="my_bilibili", lifespan=lifespan)

app.include_router(creators_router)
app.include_router(tags_router)
app.include_router(videos_router)
app.include_router(sync_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "未捕获的异常: %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请查看日志"},
    )


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 3: 验证语法正确**

```bash
.venv/bin/python -c "from app.main import app; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 4: Commit**

```bash
git add app/scheduler.py app/main.py
git commit -m "refactor: 用 asyncio 循环替代 APScheduler 定时调度"
```

---

### Task 5: 更新同步路由

**Files:**
- Modify: `app/routers/sync.py`

- [ ] **Step 1: 更新 sync.py**

将 `POST /api/sync/run` 改为 `async def`，更新 `set_scheduler_context` 为 `set_sync_context`。

```python
"""同步路由：查询最近同步状态、手动触发全量同步、查询调度配置、管理立即同步标签。"""
import asyncio
import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.dependencies import get_db
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.models.sync_log import SyncLog
from app.models.sync_task import SyncTask
from app.models.tag_sync_config import TagSyncConfig
from app.schemas.sync import SyncLogRead, SyncTaskRead
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])
_sync_svc = SyncService(fetcher=PlaywrightBilibiliFetcher(cookie=settings.bilibili_cookie or None))

# 由 main.py 的 lifespan 在应用启动后注入
_sync_loop_running: bool = False
_sync_interval_minutes: int = 60


def set_sync_context(loop_running: bool, interval_minutes: int) -> None:
    global _sync_loop_running, _sync_interval_minutes
    _sync_loop_running = loop_running
    _sync_interval_minutes = interval_minutes


def _to_sync_log_read(log: SyncLog) -> SyncLogRead:
    return SyncLogRead(
        id=log.id,
        scope=log.scope,
        status=log.status,
        new_videos=log.new_videos,
        error_message=log.error_message,
        started_at=log.started_at,
        finished_at=log.finished_at,
    )


@router.get("/latest", response_model=Optional[SyncLogRead])
def get_latest_sync(
    db: Annotated[Session, Depends(get_db)],
) -> Optional[SyncLogRead]:
    log = (
        db.query(SyncLog)
        .filter(SyncLog.scope == "all")
        .order_by(SyncLog.started_at.desc())
        .first()
    )
    if log is None:
        return None
    return _to_sync_log_read(log)


@router.post("/run", response_model=SyncTaskRead)
async def run_sync(
    db: Annotated[Session, Depends(get_db)],
) -> SyncTaskRead:
    """手动触发全量同步：创建同步任务，后台协程执行，立即返回任务进度。"""
    task = _sync_svc.start_async_sync(db)
    asyncio.create_task(_sync_svc._run_async_sync(task.id, SessionLocal))
    return SyncTaskRead(
        id=task.id,
        status=task.status,
        total_creators=task.total_creators,
        completed_creators=task.completed_creators,
        current_creator_name=task.current_creator_name,
        new_videos=task.new_videos,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
        heartbeat_at=task.heartbeat_at,
    )


@router.get("/task/current", response_model=Optional[SyncTaskRead])
def get_current_task(
    db: Annotated[Session, Depends(get_db)],
) -> Optional[SyncTaskRead]:
    task = (
        db.query(SyncTask)
        .order_by(SyncTask.started_at.desc())
        .first()
    )
    if task is None:
        return None
    return SyncTaskRead(
        id=task.id,
        status=task.status,
        total_creators=task.total_creators,
        completed_creators=task.completed_creators,
        current_creator_name=task.current_creator_name,
        new_videos=task.new_videos,
        error_message=task.error_message,
        started_at=task.started_at,
        finished_at=task.finished_at,
        heartbeat_at=task.heartbeat_at,
    )


@router.get("/settings", response_model=dict[str, Any])
def get_sync_settings() -> dict[str, Any]:
    return {
        "enabled": _sync_loop_running,
        "interval_minutes": _sync_interval_minutes,
        "job_id": "sync-all",
    }


# ── 立即同步标签管理 ─────────────────────────────────────────────


@router.get("/immediate-tags", response_model=list[dict])
def list_immediate_tags(
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    rows = db.query(TagSyncConfig).all()
    return [
        {"id": row.id, "tag_id": row.tag_id, "sync_mode": row.sync_mode}
        for row in rows
    ]


@router.post("/immediate-tags", status_code=status.HTTP_201_CREATED, response_model=dict)
def add_immediate_tag(
    tag_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    from app.models.tag import Tag

    tag = db.query(Tag).filter_by(id=tag_id).first()
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"标签 id={tag_id} 不存在"
        )

    existing = db.query(TagSyncConfig).filter_by(tag_id=tag_id).first()
    if existing is not None:
        return {"id": existing.id, "tag_id": existing.tag_id, "sync_mode": existing.sync_mode}

    config = TagSyncConfig(tag_id=tag_id, sync_mode="immediate")
    db.add(config)
    db.flush()
    return {"id": config.id, "tag_id": config.tag_id, "sync_mode": config.sync_mode}


@router.delete("/immediate-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_immediate_tag(
    tag_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    config = db.query(TagSyncConfig).filter_by(tag_id=tag_id).first()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"标签 id={tag_id} 未配置为立即同步",
        )
    db.delete(config)
    db.flush()
```

- [ ] **Step 2: 验证语法正确**

```bash
.venv/bin/python -c "from app.routers.sync import router; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add app/routers/sync.py
git commit -m "refactor: 同步路由适配异步 fetcher，移除 APScheduler 依赖"
```

---

### Task 6: 更新测试

**Files:**
- Modify: `tests/test_fetcher.py`

- [ ] **Step 1: 重写测试为异步版本**

关键变更：`_parse_card` 改为 `async`，所有对 fetcher 的调用加 `await`，测试函数改为 `async def`。

```python
"""测试抓取层：PlaywrightBilibiliFetcher 与 FetchedVideo 标准化逻辑。"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.fetcher.models import FetchedVideo
from app.fetcher.playwright_fetcher import (
    PlaywrightBilibiliFetcher,
    FetchError,
    _parse_card,
    _parse_date,
    _parse_duration,
)


class TestParseDuration:
    def test_seconds_only(self):
        assert _parse_duration("45") == 45

    def test_mm_ss(self):
        assert _parse_duration("10:30") == 630

    def test_hh_mm_ss(self):
        assert _parse_duration("01:05:20") == 3920


class TestParseDate:
    def test_valid_full_date(self):
        result = _parse_date("2023-11-15")
        assert result == datetime(2023, 11, 15)

    def test_mm_dd_format(self):
        from datetime import datetime as dt, timezone
        result = _parse_date("01-01")
        assert result is not None
        assert result.month == 1
        assert result.day == 1
        today = dt.now(timezone.utc).replace(tzinfo=None)
        assert result.year in (today.year, today.year - 1)

    def test_invalid_date_returns_none(self):
        assert _parse_date("bad-date") is None

    def test_relative_time(self):
        from datetime import datetime as dt, timezone, timedelta
        today = dt.now(timezone.utc).replace(tzinfo=None)
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)

        result = _parse_date("5小时前")
        assert result is not None
        assert result == today_start

        result = _parse_date("1天前")
        assert result is not None
        assert result == today_start - timedelta(days=1)

        result = _parse_date("30分钟前")
        assert result is not None
        assert result == today_start

        result = _parse_date("3个月前")
        assert result is not None
        assert result == today_start - timedelta(days=90)


class TestParseCard:
    @staticmethod
    def _make_card_mock(*, bvid="BV1xx411c7mD", title="测试视频",
                        date_str="2023-11-15", duration_str="10:30"):
        card = MagicMock()

        def locator_side_effect(selector):
            m = MagicMock()
            if selector == "a":
                mock_link = MagicMock()
                mock_link.get_attribute = AsyncMock(return_value=(
                    f"https://www.bilibili.com/video/{bvid}?spm_id_from=xxx"
                ))
                m.first = mock_link
            elif "bili-video-card__title" in selector:
                m.text_content = AsyncMock(return_value=title)
            elif "bili-video-card__subtitle" in selector:
                m.text_content = AsyncMock(return_value=date_str)
            elif "bili-cover-card__stat" in selector:
                m.count = AsyncMock(return_value=3)
                m_dur = MagicMock()
                m_dur.text_content = AsyncMock(return_value=duration_str)
                m.nth = MagicMock(return_value=m_dur)
            return m

        card.locator.side_effect = locator_side_effect

        return card

    async def test_basic_conversion(self):
        card = self._make_card_mock()
        video = await _parse_card(card)
        assert video is not None
        assert video.bvid == "BV1xx411c7mD"
        assert video.title == "测试视频"
        assert video.video_url == "https://www.bilibili.com/video/BV1xx411c7mD"
        assert video.duration_seconds == 630
        assert video.published_at == datetime(2023, 11, 15)
        assert video.published_at.tzinfo is None

    async def test_no_bvid_returns_none(self):
        card = MagicMock()

        def locator_side_effect(selector):
            m = MagicMock()
            if selector == "a":
                mock_link = MagicMock()
                mock_link.get_attribute = AsyncMock(return_value="https://space.bilibili.com/546195")
                m.first = mock_link
            return m

        card.locator.side_effect = locator_side_effect
        assert await _parse_card(card) is None


class TestFetchedVideo:
    def test_dataclass_fields(self):
        dt = datetime(2023, 11, 15, 0, 0, 0)
        video = FetchedVideo(
            bvid="BV1xx411c7mD",
            title="测试",
            video_url="https://www.bilibili.com/video/BV1xx411c7mD",
            published_at=dt,
            duration_seconds=630,
        )
        assert video.bvid == "BV1xx411c7mD"
        assert video.title == "测试"
        assert video.video_url == "https://www.bilibili.com/video/BV1xx411c7mD"
        assert video.published_at == dt
        assert video.duration_seconds == 630


class TestPlaywrightBilibiliFetcher:
    @staticmethod
    def _make_mock_context():
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        return mock_context, mock_page

    async def test_fetch_videos_success(self):
        mock_ctx, mock_page = self._make_mock_context()

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", new_callable=AsyncMock, return_value=mock_ctx), \
             patch.object(PlaywrightBilibiliFetcher, "_get_cached", return_value=None), \
             patch.object(PlaywrightBilibiliFetcher, "_set_cache"), \
             patch.object(PlaywrightBilibiliFetcher, "_wait_for_cards", new_callable=AsyncMock, return_value=True), \
             patch.object(PlaywrightBilibiliFetcher, "_extract_all_pages", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = [
                FetchedVideo(
                    bvid="BV1xx411c7mD",
                    title="测试视频",
                    video_url="https://www.bilibili.com/video/BV1xx411c7mD",
                    published_at=datetime(2023, 11, 15),
                    duration_seconds=630,
                )
            ]
            fetcher = PlaywrightBilibiliFetcher()
            videos = await fetcher.fetch_videos("12345", ttl_cache=False)

        assert len(videos) == 1
        assert all(isinstance(v, FetchedVideo) for v in videos)
        assert videos[0].bvid == "BV1xx411c7mD"

    async def test_fetch_videos_empty_page_raises(self):
        mock_ctx, mock_page = self._make_mock_context()

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", new_callable=AsyncMock, return_value=mock_ctx), \
             patch.object(PlaywrightBilibiliFetcher, "_get_cached", return_value=None), \
             patch.object(PlaywrightBilibiliFetcher, "_wait_for_cards", new_callable=AsyncMock, return_value=True), \
             patch.object(PlaywrightBilibiliFetcher, "_extract_all_pages", new_callable=AsyncMock, return_value=[]), \
             patch.object(PlaywrightBilibiliFetcher, "_set_cache"):
            fetcher = PlaywrightBilibiliFetcher()

            with pytest.raises(FetchError):
                await fetcher.fetch_videos("12345", ttl_cache=False)

    async def test_fetch_creator_name(self):
        mock_nickname_el = MagicMock()
        mock_nickname_el.text_content = AsyncMock(return_value="测试UP主")

        mock_page = MagicMock()
        mock_page.locator.return_value.first = mock_nickname_el

        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", new_callable=AsyncMock, return_value=mock_context), \
             patch.object(PlaywrightBilibiliFetcher, "_get_cached", return_value=None), \
             patch.object(PlaywrightBilibiliFetcher, "_set_cache"):
            fetcher = PlaywrightBilibiliFetcher()
            name = await fetcher.fetch_creator_name("12345")

        assert name == "测试UP主"

    async def test_fetch_creator_name_empty_text_raises(self):
        mock_nickname_el = MagicMock()
        mock_nickname_el.text_content = AsyncMock(return_value="   ")

        mock_page = MagicMock()
        mock_page.locator.return_value.first = mock_nickname_el

        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", new_callable=AsyncMock, return_value=mock_context), \
             patch.object(PlaywrightBilibiliFetcher, "_get_cached", return_value=None), \
             patch.object(PlaywrightBilibiliFetcher, "_set_cache"):
            fetcher = PlaywrightBilibiliFetcher()

            with pytest.raises(FetchError, match="未能提取到 UP 主昵称"):
                await fetcher.fetch_creator_name("12345")

    async def test_fetch_creator_name_page_failure_raises(self):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock(side_effect=Exception("连接超时"))

        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", new_callable=AsyncMock, return_value=mock_context), \
             patch.object(PlaywrightBilibiliFetcher, "_get_cached", return_value=None), \
             patch.object(PlaywrightBilibiliFetcher, "_set_cache"):
            fetcher = PlaywrightBilibiliFetcher()

            with pytest.raises(FetchError, match="获取 UP 主信息失败"):
                await fetcher.fetch_creator_name("12345")
```

- [ ] **Step 2: 运行测试**

```bash
.venv/bin/pytest tests/test_fetcher.py -v
```
Expected: 所有测试 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_fetcher.py
git commit -m "test: 将 fetcher 测试适配异步 API"
```

---

### Task 7: 最终验证

- [ ] **Step 1: 运行全部测试**

```bash
.venv/bin/pytest -v
```

- [ ] **Step 2: 检查导入链路完整性**

```bash
.venv/bin/python -c "from app.main import app; from app.routers.sync import router; from app.services.sync_service import SyncService; from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher; print('All imports OK')"
```

- [ ] **Step 3: 提交最终状态**

```bash
git status
git log --oneline -6
```
