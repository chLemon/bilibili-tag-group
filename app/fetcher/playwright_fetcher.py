"""使用 Playwright 无头浏览器抓取 B 站视频数据。

打开 UP 主投稿视频页面，通过 DOM 提取视频卡片数据并逐页翻页，
绕过 WBI API 签名风控。

浏览器实例存储在 fetcher 实例上，在单个事件循环内复用。
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import UTC, datetime, timedelta

from playwright.async_api import Browser, BrowserContext, async_playwright

from app.fetcher.models import FetchedVideo

_logger = logging.getLogger(__name__)


class FetchError(Exception):
    """抓取失败时抛出此异常。"""


class CanRetryError(Exception):
    """可以重试的异常"""


# ── CSS 选择器 ────────────────────────────────────────────────────

_CARD_CLASS = ".bili-video-card"
_TITLE_CLASS = ".bili-video-card__title"
_SUBTITLE_CLASS = ".bili-video-card__subtitle"
_DURATION_CLASS = ".bili-cover-card__stat"
_NEXT_PAGE_SELECTOR = ".vui_pagenation--btn-side"
_VIDEO_COUNT_SELECTOR = ".side-nav__item.active .side-nav__item__sub-text"
_PAGE_COUNT_CSS_SELECTOR = ".vui_pagenation-go__count"
_CURRENT_PAGE_NUM_SELECTOR = ".vui_pagenation--btns .vui_button--active"
_NEXT_BUTTON_SELECTOR = ".vui_pagenation--btns button:has-text('下一页')"

# ── 时间与重试配置 ────────────────────────────────────────────────

_DELAY_MIN = 1.0
_DELAY_MAX = 2.5
_PAGE_TIMEOUT = 30_000
_CARD_WAIT_TIMEOUT = 10_000
_MAX_PAGES = 1000
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

    内部通过内存 dict 管理缓存，TTL 内命中缓存则跳过远程请求。
    浏览器实例存储在 fetcher 实例上，通过 close_browser() 释放资源。
    """

    def __init__(self, cookie: str | None = None, headless: bool = True) -> None:
        self._cookie = cookie
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._cache: dict[str, dict] = {}

    # ── 浏览器生命周期 ──────────────────────────────────────────

    async def _get_browser(self) -> Browser:
        """获取浏览器实例，断开时自动重连。"""
        # 合并条件：如果浏览器不存在，或者已经断开连接，都需要彻底重建
        if self._browser is None or not self._browser.is_connected():
            # 防御性清理：如果旧的 playwright 还在运行，先把它安全关闭
            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass  # 忽略关闭旧实例时的异常

            self._playwright = await async_playwright().start()
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
                    cookies.append(
                        {
                            "name": name.strip(),
                            "value": value.strip(),
                            "domain": ".bilibili.com",
                            "path": "/",
                        }
                    )
            if cookies:
                await context.add_cookies(cookies)
        return context

    # ── 缓存读写 ────────────────────────────────────────────────

    @staticmethod
    def _cache_key(uid: str, kind: str) -> str:
        return f"fetcher:{uid}:{kind}"

    def _get_cached(self, uid: str, kind: str) -> dict | None:
        key = self._cache_key(uid, kind)
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts = datetime.fromisoformat(entry["ts"])
        ttl = _NAME_CACHE_TTL if kind == "name" else _VIDEOS_CACHE_TTL
        if datetime.now(UTC).replace(tzinfo=None) - ts > ttl:
            return None
        return entry["payload"]

    def _set_cache(self, uid: str, kind: str, payload) -> None:
        key = self._cache_key(uid, kind)
        self._cache[key] = {
            "ts": datetime.now(UTC).replace(tzinfo=None).isoformat(),
            "payload": payload,
        }

    # ── 公开抓取方法 ────────────────────────────────────────────

    async def fetch_new_videos(self, uid: str) -> list[FetchedVideo]:
        """抓取某个 up 主的视频列表


        1. 访问 /upload/video
        2. 抓取视频
        3. 从前往后翻页继续抓取，直到完成

        如果某页抓取失败，则整个失败。
        """

        context = await self._create_context()
        page = await context.new_page()
        try:
            _logger.info(f"开始抓取 {uid} 的视频")
            # 前往页面
            await page.goto(
                f"https://space.bilibili.com/{uid}/upload/video",
                wait_until="networkidle",
                timeout=_PAGE_TIMEOUT,
            )

            videos: list[FetchedVideo] = []

            # 翻页抓取
            while True:
                # 刷新直到有视频卡片
                if not await self._wait_for_cards(page):
                    raise FetchError

                # 当前激活页码
                current_page_num = await self._extract_current_page_num(page)
                _logger.info(f"抓取第 {current_page_num} 页的数据")

                page_bvids: set[str] = set()
                for video in await self._extract_videos_from_page(page):
                    videos.append(video)
                    page_bvids.add(video.bvid)

                if page_bvids and self._any_known(page_bvids):
                    # 已经获取到了db里有的视频，那么提前返回即可
                    break

                next_button = page.locator(_NEXT_BUTTON_SELECTOR)
                if await next_button.is_disabled():
                    # 已到了最后一页
                    break

                # 翻页
                await next_button.click()
                # 模拟延迟
                delay = random.uniform(2.0, 4.0)
                await asyncio.sleep(delay)

            return videos
        except Exception as exc:
            raise exc
        finally:
            await page.close()
            await context.close()

    async def fetch_creator_info(self, uid: str) -> dict:
        """获取up主信息"""
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
                avatar_img = page.locator(
                    "#h-avatar img, .avatar img, .b-avatar img"
                ).first
                if await avatar_img.count() > 0:
                    raw = await avatar_img.get_attribute("src") or ""
                    if raw:
                        avatar_url = f"https:{raw}" if raw.startswith("//") else raw
            except Exception:
                raise FetchError(f"未能提取到 UP 主头像，uid={uid}")

            video_count: int | None = None
            try:
                nav_items = page.locator(".side-nav__item")
                count = await nav_items.count()
                for i in range(count):
                    item = nav_items.nth(i)
                    text_el = item.locator(".side-nav__item__main-text")
                    if await text_el.count() > 0 and "视频" in (
                        await text_el.text_content() or ""
                    ):
                        count_el = item.locator(".side-nav__item__sub-text")
                        if await count_el.count() > 0:
                            count_text = (await count_el.text_content() or "").strip()
                            video_count = int(count_text)
                        break
            except Exception:
                raise FetchError(f"未能提取到 UP 主视频数量，uid={uid}")

            result = {
                "name": name,
                "avatar_url": avatar_url,
                "video_count": video_count,
            }
            return result
        except FetchError:
            raise
        except Exception as exc:
            raise FetchError(f"获取 UP 主信息失败，uid={uid}: {exc}") from exc
        finally:
            await page.close()
            await context.close()

    async def fetch_creator_name(self, uid: str) -> str:
        info = await self.fetch_creator_info(uid)
        return info["name"]

    # ── 页面交互 ────────────────────────────────────────────────

    async def _wait_for_cards(self, page, max_refresh: int = 4) -> bool:
        for refresh in range(max_refresh + 1):
            try:
                await page.wait_for_selector(_TITLE_CLASS, timeout=_CARD_WAIT_TIMEOUT)
                return True
            except Exception:
                if refresh < max_refresh:
                    await asyncio.sleep(random.uniform(_DELAY_MIN, _DELAY_MAX))
                    await page.reload(wait_until="networkidle", timeout=_PAGE_TIMEOUT)
        return False

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
    async def _extract_current_page_num(page) -> str:
        """获取当前页数"""
        active_page_locator = page.locator(_CURRENT_PAGE_NUM_SELECTOR)
        return (await active_page_locator.text_content() or "").strip()

    @staticmethod
    def _any_known(bvids: set[str]) -> bool:
        """判断是否有已知视频（内存缓存命中则提前终止翻页）。"""
        return False


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
    now = datetime.now(UTC).replace(tzinfo=None)

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
        return (now - timedelta(seconds=delta_seconds)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    return None


def _parse_duration(length: str) -> int:
    parts = length.split(":")
    if len(parts) == 1:
        return int(parts[0])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
