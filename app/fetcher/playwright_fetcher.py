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
    浏览器实例存储在 fetcher 实例上，通过 close_browser() 释放资源。
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
