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
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from playwright.async_api import Browser, BrowserContext, async_playwright

from app.fetcher.models import FetchedVideo

_logger = logging.getLogger(__name__)


class FetchError(Exception):
    """抓取失败时抛出此异常。"""


# ── CSS 选择器 ────────────────────────────────────────────────────

_CARD_CLASS = ".bili-video-card"
_TITLE_CLASS = ".bili-video-card__title"
_SUBTITLE_CLASS = ".bili-video-card__subtitle"
_DURATION_CLASS = ".bili-cover-card__stat"
_VIDEO_COUNT_SELECTOR = ".side-nav__item.active .side-nav__item__sub-text"
_CURRENT_PAGE_NUM_SELECTOR = ".vui_pagenation--btns .vui_button--active"
_PAGE_BUTTONS_SELECTOR = ".vui_pagenation--btns button"
_JUMP_INPUT_SELECTOR = ".vui_pagenation-go input"

# ── 时间与重试配置 ────────────────────────────────────────────────

_DELAY_MIN = 1.0
_DELAY_MAX = 2.5
_PAGE_TIMEOUT = 30_000
_CARD_WAIT_TIMEOUT = 10_000
_MAX_PAGES = 1000
_PAGINATION_RETRY_MAX = 3
_RETRY_DELAY_MIN = 20.0
_RETRY_DELAY_MAX = 40.0

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
    浏览器实例存储在 fetcher 实例上，通过 close() 释放资源。
    """

    def __init__(
        self, headless: bool = True, cookies: dict[str, str] | None = None
    ) -> None:
        self._headless = headless
        self._cookies = cookies or {}
        self._playwright = None
        self._browser = None

    async def close(self) -> None:
        """对外暴露的资源释放入口，应用关闭时调用。"""
        await self._close_browser()

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

    async def _close_browser(self) -> None:
        """关闭浏览器实例，释放资源。"""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def _create_context(self) -> BrowserContext:
        """创建带反检测配置的浏览器上下文。"""
        browser = await self._get_browser()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        if self._cookies:
            await context.add_cookies(
                [
                    {"name": k, "value": v, "domain": ".bilibili.com", "path": "/"}
                    for k, v in self._cookies.items()
                ]
            )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)
        return context

    # ── 公开抓取方法 ────────────────────────────────────────────

    async def fetch_new_videos(
        self,
        uid: str,
        known_videos: list[FetchedVideo] | None = None,
        on_page_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[FetchedVideo]:
        """抓取某个 up 主的视频列表

        1. 访问 /upload/video
        2. 提取总页数后按 1..N 顺序抓取，每页用"跳至 xx 页"输入框直跳

        某页跳页后等不到新 bvid（疑似 B 站风控）时，reload 当前页（回到
        第 1 页）后重新跳到目标页重试，最多 _PAGINATION_RETRY_MAX 次。

        如果某页抓取失败，则整个失败。

        known_videos 为调用方已持有的该 UP 主视频集合（来自本地存储）。
        翻页时若某页出现已知 bvid，提前停止翻页，并把 known_videos 中
        本次未抓到的视频补回返回值——返回的是"已知 ∪ 本次新抓"的并集，
        早停只省抓取量，不损失返回完整性。

        on_page_progress 为可选的页级进度回调：每完成一页抓取后以
        (当前页码, 总页数) 调用一次，供调用方及时透出进度。回调抛异常会
        中断抓取。
        """
        context = await self._create_context()
        page = await context.new_page()
        try:
            _logger.info(f"开始抓取 {uid} 的视频")
            await self._open_upload_page(page, uid)

            # 首页拿总页数；无分页按钮（仅 1 页）当作 1 页
            total_pages = await self._extract_total_pages(page) or 1

            videos: list[FetchedVideo] = []
            seen_bvids: set[str] = set()
            known_bvids = {v.bvid for v in known_videos} if known_videos else set()

            for target_page in range(1, total_pages + 1):
                # 第 1 页已在；后续页跳页 + 风控重试
                if target_page > 1:
                    await self._jump_to_target_page(page, target_page, seen_bvids, uid)

                current_page_num = await self._extract_current_page_num(page)
                _logger.info(f"抓取第 {current_page_num} 页的数据")

                page_bvids, new_videos = await self._collect_new_videos(page, seen_bvids)
                videos.extend(new_videos)
                _logger.info(f"{uid} 第 {current_page_num} 页抓到 {len(page_bvids)} 个视频")
                _logger.debug(
                    f"{uid} 第 {current_page_num} 页 bvid: {', '.join(sorted(page_bvids))}"
                )

                if on_page_progress is not None:
                    current_num = int(current_page_num) if current_page_num.isdigit() else 0
                    await on_page_progress(current_num, total_pages)

                # 翻到含已知视频的页，提前结束
                if page_bvids and page_bvids & known_bvids:
                    break

                # 翻页前随机延迟，降低风控触发概率
                if target_page < total_pages:
                    await asyncio.sleep(random.uniform(2.0, 4.0))

            fetched_count = len(videos)
            self._backfill_known(videos, known_videos)
            _logger.info(f"{uid} 抓取到 {fetched_count} 个视频，最终返回 {len(videos)} 个")
            return videos
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
                wait_until="domcontentloaded",
                timeout=_PAGE_TIMEOUT,
            )

            name = (await page.locator(".nickname").first.text_content() or "").strip()
            raw = await page.locator(
                "#h-avatar img, .avatar img, .b-avatar img"
            ).first.get_attribute("src") or ""
            avatar_url = f"https:{raw}" if raw.startswith("//") else raw

            # 从侧栏"视频"项的 sub-text 取视频数
            video_count: int | None = None
            nav_items = page.locator(".side-nav__item")
            for i in range(await nav_items.count()):
                item = nav_items.nth(i)
                text_el = item.locator(".side-nav__item__main-text")
                if await text_el.count() > 0 and "视频" in (
                    await text_el.text_content() or ""
                ):
                    count_el = item.locator(".side-nav__item__sub-text")
                    if await count_el.count() > 0:
                        count_text = (await count_el.text_content() or "").strip()
                        if count_text:
                            video_count = int(count_text)
                    break

            if not name or not avatar_url or video_count is None:
                raise FetchError(f"获取 UP 主信息失败，uid={uid}")

            return {
                "name": name,
                "avatar_url": avatar_url,
                "video_count": video_count,
            }
        except Exception as exc:
            raise FetchError(f"获取 UP 主信息失败，uid={uid}: {exc}") from exc
        finally:
            await page.close()
            await context.close()

    # ── 页面交互 ────────────────────────────────────────────────

    async def _wait_for_cards(self, page, max_refresh: int = 4) -> bool:
        for refresh in range(max_refresh + 1):
            try:
                await page.wait_for_selector(_TITLE_CLASS, timeout=_CARD_WAIT_TIMEOUT)
                return True
            except Exception:
                if refresh < max_refresh:
                    await asyncio.sleep(random.uniform(_DELAY_MIN, _DELAY_MAX))
                    await page.reload(wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT)
        return False

    async def _jump_to_page(
        self, page, target_page: int, timeout_ms: int = _PAGE_TIMEOUT
    ) -> bool:
        """跳转到指定页码：填跳页输入框 + Enter，等激活页码变 target_page 确认生效。"""
        go_input = page.locator(_JUMP_INPUT_SELECTOR)
        try:
            await go_input.fill(str(target_page))
            await go_input.press("Enter")
            await page.wait_for_function(
                f"""() => {{
                    const el = document.querySelector('{_CURRENT_PAGE_NUM_SELECTOR}');
                    return el && el.textContent.trim() === '{target_page}';
                }}""",
                timeout=timeout_ms,
            )
            return True
        except Exception:
            return False

    async def _wait_for_new_bvid(
        self, page, seen_bvids: set[str], timeout_ms: int = _PAGE_TIMEOUT
    ) -> bool:
        """等待 DOM 中最后一张卡片的 bvid 未抓过，确认翻页后 cards 真刷新而非上一页残留。"""
        seen_js = ",".join(f"'{b}'" for b in seen_bvids)
        try:
            await page.wait_for_function(
                f"""() => {{
                    const seen = new Set([{seen_js}]);
                    const links = document.querySelectorAll('{_CARD_CLASS} a[href*="/video/BV"]');
                    if (!links.length) return false;
                    const last = links[links.length - 1];
                    const m = (last.href || '').match(/\\/video\\/(BV\\w+)/);
                    return !!(m && !seen.has(m[1]));
                }}""",
                timeout=timeout_ms,
            )
            return True
        except Exception:
            try:
                diag = await page.evaluate(
                    f"""() => {{
                        const links = document.querySelectorAll('{_CARD_CLASS} a[href*="/video/BV"]');
                        const bvids = [];
                        for (const a of links) {{
                            const m = (a.href || '').match(/\\/video\\/(BV\\w+)/);
                            if (m) bvids.push(m[1]);
                        }}
                        return {{
                            total: bvids.length,
                            unique: new Set(bvids).size,
                            current_page: (document.querySelector('{_CURRENT_PAGE_NUM_SELECTOR}') || {{}}).textContent || '',
                        }};
                    }}"""
                )
                _logger.debug(
                    f"_wait_for_new_bvid 失败：cards={diag.get('total')}, "
                    f"unique_bvids={diag.get('unique')}, "
                    f"current_page={diag.get('current_page')!r}, "
                    f"seen={len(seen_bvids)}"
                )
            except Exception:
                pass
            return False

    async def _open_upload_page(self, page, uid: str) -> None:
        """打开投稿页并等卡片出现；等不到抛 FetchError。"""
        await page.goto(
            f"https://space.bilibili.com/{uid}/upload/video",
            wait_until="domcontentloaded",
            timeout=_PAGE_TIMEOUT,
        )
        if not await self._wait_for_cards(page):
            raise FetchError

    async def _jump_to_target_page(
        self, page, target_page: int, seen_bvids: set[str], uid: str
    ) -> None:
        """跳到目标页并等新 bvid 出现。

        失败多半是 B 站风控（412）：SPA 只更新页码 UI 不刷新 cards。
        reload 当前页（回到第 1 页）后下一轮 retry 重新跳页，最多
        _PAGINATION_RETRY_MAX 次；仍失败则抛 FetchError。
        """
        for retry in range(_PAGINATION_RETRY_MAX + 1):
            if await self._jump_to_page(page, target_page) and \
               await self._wait_for_new_bvid(page, seen_bvids):
                return
            if retry >= _PAGINATION_RETRY_MAX:
                break
            _logger.warning(
                f"{uid} 跳到第 {target_page} 页失败（retry {retry + 1}/"
                f"{_PAGINATION_RETRY_MAX}），疑似 B 站风控，reload 后重试"
            )
            await asyncio.sleep(random.uniform(_RETRY_DELAY_MIN, _RETRY_DELAY_MAX))
            await page.reload(wait_until="domcontentloaded", timeout=_PAGE_TIMEOUT)
            # reload 回到第 1 页；等不到 cards 直接下一轮 retry 再 reload
            await self._wait_for_cards(page)
        raise FetchError

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
    async def _extract_total_pages(page) -> int:
        """从分页按钮中取数字页码的最大值作为总页数；无分页按钮时返回 0。"""
        buttons = page.locator(_PAGE_BUTTONS_SELECTOR)
        count = await buttons.count()
        max_page = 0
        for i in range(count):
            text = (await buttons.nth(i).text_content() or "").strip()
            if text.isdigit():
                max_page = max(max_page, int(text))
        return max_page

    async def _collect_new_videos(
        self, page, seen_bvids: set[str]
    ) -> tuple[set[str], list[FetchedVideo]]:
        """提取当前页所有卡片，按 bvid 全局去重。

        返回 (本页新 bvid 集合, 本页新视频列表)。同一 bvid 即便多次出现
        也只入列一次——防御 SPA 跳页后 DOM 未刷新时把上一页卡片重复 append。
        """
        page_bvids: set[str] = set()
        new_videos: list[FetchedVideo] = []
        for video in await self._extract_videos_from_page(page):
            if video.bvid in seen_bvids:
                continue
            seen_bvids.add(video.bvid)
            page_bvids.add(video.bvid)
            new_videos.append(video)
        return page_bvids, new_videos

    @staticmethod
    def _backfill_known(
        videos: list[FetchedVideo], known_videos: list[FetchedVideo] | None
    ) -> None:
        """把 known_videos 里本次未抓到的视频补回 videos 列表（原地修改）。

        早停只省抓取量，返回值始终是"已知 ∪ 本次新抓"的并集。
        """
        fetched_bvids = {v.bvid for v in videos}
        for kv in known_videos or []:
            if kv.bvid not in fetched_bvids:
                videos.append(kv)


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
    if not date_str:
        raise FetchError(f"视频卡片未提取到发布时间，bvid={bvid}")
    published_at = _parse_date(date_str)

    stat_spans = card.locator(_DURATION_CLASS + " span")
    stat_count = await stat_spans.count()
    duration_str = ""
    if stat_count > 0:
        duration_str = (
            await stat_spans.nth(stat_count - 1).text_content() or ""
        ).strip()
    duration_seconds = _parse_duration(duration_str) if duration_str else 0

    cover_area = card.locator(".bili-video-card__cover")
    if await cover_area.count() == 0:
        raise FetchError(f"视频卡片未提取到封面，bvid={bvid}")
    cover_img = cover_area.locator("img").first
    if await cover_img.count() == 0:
        raise FetchError(f"视频卡片未提取到封面 img，bvid={bvid}")
    raw = await cover_img.get_attribute("src") or ""
    if not raw:
        raise FetchError(f"视频卡片封面 img src 为空，bvid={bvid}")
    cover_url = f"https:{raw}" if raw.startswith("//") else raw

    return FetchedVideo(
        bvid=bvid,
        title=title,
        video_url=f"https://www.bilibili.com/video/{bvid}",
        published_at=published_at,
        duration_seconds=duration_seconds,
        cover_url=cover_url,
    )


def _parse_date(date_str: str) -> datetime:
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
            raise FetchError(f"无法解析发布时间：{date_str}")
        return (now - timedelta(seconds=delta_seconds)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    raise FetchError(f"无法解析发布时间：{date_str}")


def _parse_duration(length: str) -> int:
    parts = length.split(":")
    if len(parts) == 1:
        return int(parts[0])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
