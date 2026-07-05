"""使用 Playwright 无头浏览器抓取 B 站视频数据。

打开 UP 主投稿视频页面，通过 DOM 提取视频卡片数据并逐页翻页，
绕过 WBI API 签名风控。

浏览器实例使用线程本地存储，避免跨线程共享导致的 greenlet 切换错误。
"""
from __future__ import annotations

import json
import random as _random
import re
import threading as _threading
import time as _time
from datetime import datetime, timedelta, timezone

from playwright.sync_api import Browser, BrowserContext, sync_playwright

from app.fetcher.models import FetchedVideo


class FetchError(Exception):
    """抓取失败时抛出此异常。"""


# 视频卡片的 CSS class
_CARD_CLASS = ".bili-video-card"
_TITLE_CLASS = ".bili-video-card__title"
_SUBTITLE_CLASS = ".bili-video-card__subtitle"
_DURATION_CLASS = ".bili-cover-card__stat"
# 翻页按钮选择器
_NEXT_PAGE_SELECTOR = ".vui_pagenation--btn-side"
# 侧边栏视频总数
_VIDEO_COUNT_SELECTOR = ".side-nav__item.active .side-nav__item__sub-text"
# 操作间随机延迟范围（秒）
_DELAY_MIN = 1.0
_DELAY_MAX = 2.5
# 页面加载超时（毫秒）
_PAGE_TIMEOUT = 30000
# 等待视频卡片出现的超时（毫秒）
_CARD_WAIT_TIMEOUT = 10000
# 翻页安全上限
_MAX_PAGES = 50
# 重试次数
_RETRY_COUNT = 4
# 重试退避等待基数（秒）
_RETRY_BACKOFF = 2
# 缓存 TTL
_NAME_CACHE_TTL = timedelta(hours=24)
_VIDEOS_CACHE_TTL = timedelta(hours=1)


class PlaywrightBilibiliFetcher:
    """使用 Playwright 无头浏览器从 B 站空间页抓取视频列表和 UP 主信息。

    内部通过 SessionLocal 管理 SQLite 缓存，TTL 内命中缓存则跳过远程请求。
    浏览器实例使用线程本地存储，确保 Playwright 同步 API 的线程安全性。
    """

    _thread_local: _threading.local = _threading.local()

    def __init__(self, cookie: str | None = None, headless: bool = True) -> None:
        """初始化抓取器。

        参数：
            cookie: B 站登录 Cookie 字符串（可选）
            headless: 是否使用无头模式，默认 True
        """
        self._cookie = cookie
        self._headless = headless

    @classmethod
    def _get_browser(cls, headless: bool) -> Browser:
        """获取当前线程的浏览器实例（每个线程独立）。"""
        if not getattr(cls._thread_local, "browser", None):
            pw = sync_playwright().start()
            browser = pw.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
            cls._thread_local.playwright = pw
            cls._thread_local.browser = browser
        elif not cls._thread_local.browser.is_connected():
            cls._thread_local.browser = cls._thread_local.playwright.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
        return cls._thread_local.browser

    @classmethod
    def close_browser(cls) -> None:
        """关闭当前线程的浏览器实例，释放资源。"""
        browser = getattr(cls._thread_local, "browser", None)
        playwright = getattr(cls._thread_local, "playwright", None)
        if browser is not None:
            browser.close()
            cls._thread_local.browser = None
        if playwright is not None:
            playwright.stop()
            cls._thread_local.playwright = None

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

    # ── 缓存读写 ────────────────────────────────────────────────

    def _cache_key(self, uid: str, kind: str) -> str:
        return f"fetcher:{uid}:{kind}"

    def _get_cached(self, uid: str, kind: str) -> dict | None:
        """从 SQLite 读取缓存，过期返回 None。"""
        from sqlalchemy import text
        from app.database import SessionLocal

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
        """写入 SQLite 缓存。"""
        from sqlalchemy import text
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            data = json.dumps({
                "ts": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "payload": payload,
            }, ensure_ascii=False)
            db.execute(
                text("INSERT OR REPLACE INTO cache (key, value) VALUES (:key, :value)"),
                {"key": self._cache_key(uid, kind), "value": data},
            )
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    # ── 公开抓取方法 ──────────────────────────────────────────────

    def fetch_videos(self, uid: str, ttl_cache: bool = True) -> list[FetchedVideo]:
        """抓取指定 UP 主的视频列表。

        打开投稿视频页面，通过 DOM 提取视频卡片数据，
        逐页翻页，遇到本地已有的视频即停止（智能停止）。

        参数：
            uid: UP 主的数字 ID
            ttl_cache: True 时优先返回 TTL 缓存（1h），False 时每次翻页查 B 站但智能停止

        返回：
            FetchedVideo 列表（按 bvid 去重）

        异常：
            FetchError: 页面加载失败或数据提取失败时抛出
        """
        if ttl_cache:
            cached = self._get_cached(uid, "videos")
            if cached is not None:
                return [
                    FetchedVideo(
                        bvid=v["bvid"],
                        title=v["title"],
                        video_url=v["video_url"],
                        published_at=datetime.fromisoformat(v["published_at"])
                        if v.get("published_at") else None,
                        duration_seconds=v["duration_seconds"],
                    )
                    for v in cached
                ]

        last_error: Exception | None = None

        for attempt in range(_RETRY_COUNT + 1):
            if attempt > 0:
                _time.sleep(_RETRY_BACKOFF * attempt)

            context = self._create_context()
            page = context.new_page()
            try:
                page.goto(
                    f"https://space.bilibili.com/{uid}/upload/video",
                    wait_until="networkidle",
                    timeout=_PAGE_TIMEOUT,
                )

                # 等待卡片出现，若白屏或验证码则刷新重试
                if not self._wait_for_cards(page):
                    last_error = FetchError(f"未能从页面提取到视频数据，uid={uid}")
                    continue

                videos = self._extract_all_pages(page)
                if videos:
                    self._set_cache(uid, "videos", [
                        {
                            "bvid": v.bvid,
                            "title": v.title,
                            "video_url": v.video_url,
                            "published_at": v.published_at.isoformat()
                            if v.published_at else None,
                            "duration_seconds": v.duration_seconds,
                        }
                        for v in videos
                    ])
                    return videos

                last_error = FetchError(f"未能从页面提取到视频数据，uid={uid}")
            except Exception as exc:
                last_error = FetchError(f"页面加载失败，uid={uid}: {exc}")
            finally:
                page.close()
                context.close()

        raise last_error  # type: ignore[return-value]

    def _wait_for_cards(self, page, max_refresh: int = 4) -> bool:
        """等待视频卡片渲染，白屏或验证码时刷新页面重试。"""
        for refresh in range(max_refresh + 1):
            try:
                page.wait_for_selector(_TITLE_CLASS, timeout=_CARD_WAIT_TIMEOUT)
                return True
            except Exception:
                if refresh < max_refresh:
                    _time.sleep(_random.uniform(_DELAY_MIN, _DELAY_MAX))
                    page.reload(wait_until="networkidle",
                                timeout=_PAGE_TIMEOUT)
        return False

    def _extract_all_pages(self, page) -> list[FetchedVideo]:
        """逐页提取视频，直到某页全为已知视频或翻页按钮禁用。"""
        seen: set[str] = set()
        videos: list[FetchedVideo] = []

        # 读取侧边栏的视频总数
        total_count = 0
        try:
            count_text = page.locator(_VIDEO_COUNT_SELECTOR).first.text_content() or ""
            total_count = int(count_text.strip())
        except (ValueError, Exception):
            pass

        for _ in range(_MAX_PAGES):
            _time.sleep(_random.uniform(_DELAY_MIN, _DELAY_MAX))

            page_bvids: set[str] = set()
            for video in self._extract_videos_from_page(page):
                if video.bvid not in seen:
                    seen.add(video.bvid)
                    videos.append(video)
                page_bvids.add(video.bvid)

            # 已收集齐全部视频
            if total_count and len(videos) >= total_count:
                break

            # 当前页有任一视频已在本地数据库中 → 后面都是旧数据，停止翻页
            if page_bvids and self._any_known(page_bvids):
                break

            # 点击下一页
            next_btn = page.locator(_NEXT_PAGE_SELECTOR).last
            btn_class = next_btn.get_attribute("class") or ""
            if "disabled" in btn_class:
                break

            next_btn.click()
            if not self._wait_for_cards(page):
                break
            _time.sleep(_random.uniform(_DELAY_MIN + 1, _DELAY_MAX + 1))

        return videos

    @staticmethod
    def _any_known(bvids: set[str]) -> bool:
        """检查给定的 bvids 中是否有任一已存在于本地 videos 表。"""
        from sqlalchemy import text
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            placeholders = ",".join(f":b{i}" for i in range(len(bvids)))
            params = {f"b{i}": b for i, b in enumerate(bvids)}
            row = db.execute(
                text(
                    f"SELECT COUNT(*) FROM videos WHERE bvid IN ({placeholders})"
                ),
                params,
            ).fetchone()
            return row is not None and row[0] > 0
        except Exception:
            return False
        finally:
            db.close()

    def fetch_creator_name(self, uid: str, ttl_cache: bool = True) -> str:
        """获取指定 UP 主的昵称（兼容旧接口，内部调用 fetch_creator_info）。"""
        return self.fetch_creator_info(uid, ttl_cache)["name"]

    def fetch_creator_info(self, uid: str, ttl_cache: bool = True) -> dict:
        """获取指定 UP 主的昵称和头像 URL。

        从空间页面提取昵称和头像。

        参数：
            uid: UP 主的数字 ID
            ttl_cache: True 时优先返回 TTL 缓存（24h）

        返回：
            dict，包含 name 和 avatar_url 字段

        异常：
            FetchError: 获取失败时抛出
        """
        context = self._create_context()
        page = context.new_page()
        try:
            page.goto(
                f"https://space.bilibili.com/{uid}",
                wait_until="networkidle",
                timeout=_PAGE_TIMEOUT,
            )
            name = page.locator(".nickname").first.text_content()
            if not name or not name.strip():
                raise FetchError(f"未能提取到 UP 主昵称，uid={uid}")
            name = name.strip()

            avatar_url: str | None = None
            try:
                avatar_el = page.locator("#h-avatar").first
                avatar_url = avatar_el.get_attribute("src")
            except Exception:
                pass

            return {"name": name, "avatar_url": avatar_url}
        except FetchError:
            raise
        except Exception as exc:
            raise FetchError(f"获取 UP 主信息失败，uid={uid}: {exc}") from exc
        finally:
            page.close()
            context.close()

    # ── DOM 数据提取 ────────────────────────────────────────────

    @staticmethod
    def _extract_videos_from_page(page) -> list[FetchedVideo]:
        """从渲染后的页面 DOM 中提取视频卡片数据。"""
        videos: list[FetchedVideo] = []
        cards = page.locator(_CARD_CLASS)
        count = cards.count()

        for i in range(count):
            card = cards.nth(i)
            try:
                video = _parse_card(card)
                if video is not None:
                    videos.append(video)
            except Exception:
                continue

        return videos



_BVID_RE = re.compile(r"/video/(BV\w+)")


def _parse_card(card) -> FetchedVideo | None:
    """从单个 .bili-video-card 元素中提取视频数据。"""
    # 从封面链接中提取 bvid
    cover_link = card.locator("a").first
    href = cover_link.get_attribute("href") or ""
    m = _BVID_RE.search(href)
    if not m:
        return None
    bvid = m.group(1)

    # 标题
    title_el = card.locator(_TITLE_CLASS)
    title = (title_el.text_content() or "").strip()

    # 发布日期（subtitle span 可能为空）
    subtitle_el = card.locator(_SUBTITLE_CLASS + " span")
    date_str = (subtitle_el.text_content() or "").strip()

    # 时长（最后一个 stat span）
    stat_spans = card.locator(_DURATION_CLASS + " span")
    stat_count = stat_spans.count()
    duration_str = ""
    if stat_count > 0:
        duration_str = (stat_spans.nth(stat_count - 1).text_content() or "").strip()

    published_at = _parse_date(date_str) if date_str else None
    duration_seconds = _parse_duration(duration_str) if duration_str else 0

    return FetchedVideo(
        bvid=bvid,
        title=title,
        video_url=f"https://www.bilibili.com/video/{bvid}",
        published_at=published_at,
        duration_seconds=duration_seconds,
    )


_RELATIVE_RE = re.compile(r"(\d+)\s*(分钟|小时|天|个月)前")


def _parse_date(date_str: str) -> datetime | None:
    """将日期字符串转为 naive datetime。

    支持的格式：
    - "YYYY-MM-DD"（如 "2023-11-18"）
    - "MM-DD"（如 "06-27"，自动推断年份）
    - 相对时间（如 "5小时前"、"1天前"、"30分钟前"、"3个月前"）
    """
    date_str = date_str.strip()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # YYYY-MM-DD
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass

    # MM-DD：推断年份
    try:
        parsed = datetime.strptime(date_str, "%m-%d")
        result = parsed.replace(year=now.year)
        if result > now:
            result = result.replace(year=now.year - 1)
        return result
    except ValueError:
        pass

    # 相对时间：如 "5小时前"、"1天前"、"30分钟前"、"3个月前"
    m = _RELATIVE_RE.match(date_str)
    if m:
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "分钟":
            delta = num * 60
        elif unit == "小时":
            delta = num * 3600
        elif unit == "天":
            delta = num * 86400
        elif unit == "个月":
            delta = num * 30 * 86400
        else:
            return None
        from datetime import timedelta
        return (now - timedelta(seconds=delta)).replace(hour=0, minute=0, second=0, microsecond=0)

    return None


def _parse_duration(length: str) -> int:
    """将时长字符串解析为秒数（"SS" / "MM:SS" / "HH:MM:SS"）。"""
    parts = length.split(":")
    if len(parts) == 1:
        return int(parts[0])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    else:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
