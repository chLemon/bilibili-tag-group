"""使用 Playwright 无头浏览器抓取 B 站视频数据。

打开 UP 主空间页面，从 window.__INITIAL_STATE__ 中提取视频列表，
绕过 WBI API 签名风控。

浏览器实例作为类级别单例复用，避免反复启动开销。
"""
from __future__ import annotations

import json
import re
import time as _time
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Browser, BrowserContext, sync_playwright

from app.fetcher.models import FetchedVideo


class FetchError(Exception):
    """抓取失败时抛出此异常。"""


_INITIAL_STATE_RE = re.compile(
    r'<script>\s*window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>',
    re.DOTALL,
)


class PlaywrightBilibiliFetcher:
    """使用 Playwright 无头浏览器从 B 站空间页抓取视频列表和 UP 主信息。"""

    _PAGE_TIMEOUT = 30000  # 页面加载超时（毫秒）
    _RETRY_COUNT = 2

    _playwright = None
    _browser: Browser | None = None

    def __init__(self, cookie: str | None = None, headless: bool = True) -> None:
        """初始化抓取器。

        参数：
            cookie: B 站登录 Cookie 字符串（可选），会注入到浏览器上下文
            headless: 是否使用无头模式，默认 True
        """
        self._cookie = cookie
        self._headless = headless

    @classmethod
    def _get_browser(cls, headless: bool) -> Browser:
        """懒加载浏览器实例（类级别单例，跨请求复用）。"""
        if cls._browser is None or not cls._browser.is_connected():
            cls._playwright = sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
        return cls._browser

    @classmethod
    def close_browser(cls) -> None:
        """关闭浏览器实例，释放资源。"""
        if cls._browser is not None:
            cls._browser.close()
            cls._browser = None
        if cls._playwright is not None:
            cls._playwright.stop()
            cls._playwright = None

    def _create_context(self) -> BrowserContext:
        """创建带反检测配置的浏览器上下文。"""
        browser = self._get_browser(self._headless)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        # 注入 stealth 脚本，隐藏 webdriver 特征
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)
        if self._cookie:
            self._add_cookies_from_string(context, self._cookie)
        return context

    @staticmethod
    def _add_cookies_from_string(context: BrowserContext, cookie_str: str) -> None:
        """解析 Cookie 字符串并添加到浏览器上下文。"""
        cookies = []
        for part in cookie_str.split(";"):
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
            context.add_cookies(cookies)

    def fetch_videos(self, uid: str) -> list[FetchedVideo]:
        """抓取指定 UP 主的视频列表。

        打开空间页面，从 window.__INITIAL_STATE__ 中提取视频数据，
        无需经过 WBI 签名 API，因此不受风控影响。

        参数：
            uid: UP 主的数字 ID

        返回：
            FetchedVideo 列表

        异常：
            FetchError: 页面加载失败或数据提取失败时抛出
        """
        last_error: Exception | None = None

        for attempt in range(self._RETRY_COUNT + 1):
            if attempt > 0:
                _time.sleep(2 * attempt)

            context = self._create_context()
            page = context.new_page()
            try:
                page.goto(
                    f"https://space.bilibili.com/{uid}/video",
                    wait_until="networkidle",
                    timeout=self._PAGE_TIMEOUT,
                )
                html = page.content()
                videos = self._extract_videos_from_html(html, uid)
                if videos:
                    return videos

                last_error = FetchError(f"未能从页面提取到视频数据，uid={uid}")
            except Exception as exc:
                last_error = FetchError(f"页面加载失败，uid={uid}: {exc}")
            finally:
                page.close()
                context.close()

        raise last_error  # type: ignore[return-value]

    def fetch_creator_name(self, uid: str) -> str:
        """获取指定 UP 主的昵称。

        从空间页面定位 class='nickname' 元素获取。

        参数：
            uid: UP 主的数字 ID

        返回：
            UP 主昵称

        异常：
            FetchError: 获取失败时抛出
        """
        context = self._create_context()
        page = context.new_page()
        try:
            page.goto(
                f"https://space.bilibili.com/{uid}",
                wait_until="networkidle",
                timeout=self._PAGE_TIMEOUT,
            )
            nickname_el = page.locator(".nickname").first
            name = nickname_el.text_content()
            if name and name.strip():
                return name.strip()

            raise FetchError(f"未能提取到 UP 主昵称，uid={uid}")
        except FetchError:
            raise
        except Exception as exc:
            raise FetchError(f"获取昵称失败，uid={uid}: {exc}") from exc
        finally:
            page.close()
            context.close()

    # ── HTML 数据提取 ────────────────────────────────────────────

    @staticmethod
    def _extract_videos_from_html(html: str, uid: str) -> list[FetchedVideo] | None:
        """从页面 HTML 的 __INITIAL_STATE__ 中提取视频列表。"""
        match = _INITIAL_STATE_RE.search(html)
        if not match:
            return None

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

        vlist = (
            data.get("data", {})
            .get("list", {})
            .get("vlist", [])
        )
        if not vlist:
            return None

        return [_parse_video_item(item) for item in vlist]



def _parse_video_item(item: dict) -> FetchedVideo:
    """将 __INITIAL_STATE__ 中的单条视频数据转换为 FetchedVideo。"""
    bvid = item["bvid"]
    video_url = f"https://www.bilibili.com/video/{bvid}"
    published_at = datetime.fromtimestamp(
        item["created"], tz=timezone.utc
    ).replace(tzinfo=None)
    duration_seconds = _parse_duration(item["length"])
    return FetchedVideo(
        bvid=bvid,
        title=item["title"],
        video_url=video_url,
        published_at=published_at,
        duration_seconds=duration_seconds,
    )


def _parse_duration(length: str) -> int:
    """将时长字符串解析为秒数（"SS" / "MM:SS" / "HH:MM:SS"）。"""
    parts = length.split(":")
    if len(parts) == 1:
        return int(parts[0])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
