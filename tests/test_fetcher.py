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
    """测试 _parse_duration 辅助函数。"""

    def test_seconds_only(self):
        assert _parse_duration("45") == 45

    def test_mm_ss(self):
        assert _parse_duration("10:30") == 630

    def test_hh_mm_ss(self):
        assert _parse_duration("01:05:20") == 3920


class TestParseDate:
    """测试 _parse_date 辅助函数。"""

    def test_valid_full_date(self):
        result = _parse_date("2023-11-15")
        assert result == datetime(2023, 11, 15)

    def test_mm_dd_format(self):
        """MM-DD 格式推断年份（当前或上一年）。"""
        from datetime import datetime as dt, timezone
        result = _parse_date("01-01")
        # 应该是今年或去年的 1月1日
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
        # 5 小时前应该是今天
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
    """测试 _parse_card 辅助函数。"""

    @staticmethod
    def _make_card_mock(*, bvid="BV1xx411c7mD", title="测试视频",
                        date_str="2023-11-15", duration_str="10:30"):
        """构造一个 mock 视频卡片 locator。"""
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
            elif "bili-video-card__cover" in selector:
                m.count = AsyncMock(return_value=0)
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
    """测试 FetchedVideo dataclass 基本属性。"""

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
    """测试 PlaywrightBilibiliFetcher 方法（mock 浏览器部分）。"""

    @staticmethod
    def _make_mock_locator(text="", count_val=0):
        """构造一个支持异步 locator 方法的 mock。"""
        m = MagicMock()
        m.text_content = AsyncMock(return_value=text)
        m.get_attribute = AsyncMock(return_value="")
        m.count = AsyncMock(return_value=count_val)
        m.first = m
        m.nth = MagicMock(return_value=m)
        return m

    @staticmethod
    def _make_mock_context():
        """构造 mock context/page，所有 Playwright 方法均为 AsyncMock。"""
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.close = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.locator = MagicMock(return_value=TestPlaywrightBilibiliFetcher._make_mock_locator())
        mock_page.reload = AsyncMock()
        mock_context = MagicMock()
        mock_context.close = AsyncMock()
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
        mock_page.goto = AsyncMock()
        mock_page.close = AsyncMock()
        mock_page.locator.return_value.first = mock_nickname_el

        mock_context = MagicMock()
        mock_context.close = AsyncMock()
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
        mock_page.goto = AsyncMock()
        mock_page.close = AsyncMock()
        mock_page.locator.return_value.first = mock_nickname_el

        mock_context = MagicMock()
        mock_context.close = AsyncMock()
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
        mock_page.close = AsyncMock()

        mock_context = MagicMock()
        mock_context.close = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", new_callable=AsyncMock, return_value=mock_context), \
             patch.object(PlaywrightBilibiliFetcher, "_get_cached", return_value=None), \
             patch.object(PlaywrightBilibiliFetcher, "_set_cache"):
            fetcher = PlaywrightBilibiliFetcher()

            with pytest.raises(FetchError, match="获取 UP 主信息失败"):
                await fetcher.fetch_creator_name("12345")
