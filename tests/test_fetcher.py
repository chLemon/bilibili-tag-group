"""测试抓取层：PlaywrightBilibiliFetcher 与 FetchedVideo 标准化逻辑。"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.fetcher.models import FetchedVideo
from app.fetcher.playwright_fetcher import (
    PlaywrightBilibiliFetcher,
    FetchError,
    _parse_video_item,
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


class TestParseVideoItem:
    """测试 _parse_video_item 辅助函数。"""

    def test_basic_conversion(self):
        item = {
            "bvid": "BV1xx411c7mD",
            "title": "测试视频",
            "created": 1700000000,
            "length": "10:30",
        }
        video = _parse_video_item(item)
        assert video.bvid == "BV1xx411c7mD"
        assert video.title == "测试视频"
        assert video.video_url == "https://www.bilibili.com/video/BV1xx411c7mD"
        assert video.duration_seconds == 630
        expected_dt = datetime.fromtimestamp(1700000000, tz=timezone.utc).replace(tzinfo=None)
        assert video.published_at == expected_dt
        assert video.published_at.tzinfo is None


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


MOCK_HTML = """<html>
<script>window.__INITIAL_STATE__={"data":{"list":{"vlist":[
    {"bvid":"BV1xx411c7mD","title":"测试视频","created":1700000000,"length":"10:30"},
    {"bvid":"BV2yy522d8nE","title":"第二个视频","created":1700100000,"length":"01:05:20"}
]}}};</script>
</html>"""

MOCK_HTML_EMPTY = """<html><body>No data</body></html>"""

MOCK_HTML_CARD = """<html>
<script>window.__INITIAL_STATE__={"data":{"card":{"name":"测试UP主"},"list":{"vlist":[
    {"bvid":"BV1xx411c7mD","title":"测试视频","created":1700000000,"length":"10:30"}
]}}};</script>
</html>"""


class TestHtmlExtraction:
    """测试从 HTML 中提取数据。"""

    def test_extract_videos(self):
        videos = PlaywrightBilibiliFetcher._extract_videos_from_html(MOCK_HTML, "12345")
        assert videos is not None
        assert len(videos) == 2
        assert videos[0].bvid == "BV1xx411c7mD"
        assert videos[0].duration_seconds == 630
        assert videos[1].duration_seconds == 3920

    def test_extract_videos_no_data(self):
        videos = PlaywrightBilibiliFetcher._extract_videos_from_html(MOCK_HTML_EMPTY, "12345")
        assert videos is None

    def test_extract_name(self):
        name = PlaywrightBilibiliFetcher._extract_name_from_html(MOCK_HTML_CARD)
        assert name == "测试UP主"

    def test_extract_name_no_data(self):
        name = PlaywrightBilibiliFetcher._extract_name_from_html(MOCK_HTML_EMPTY)
        assert name is None


class TestPlaywrightBilibiliFetcher:
    """测试 PlaywrightBilibiliFetcher fetch_videos 方法（mock 浏览器部分）。"""

    @staticmethod
    def _make_mock_context(page_html: str):
        """构造 mock context/page，stub 掉 Playwright 调用链。"""
        from unittest.mock import MagicMock

        mock_page = MagicMock()
        mock_page.content.return_value = page_html

        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        return mock_context, mock_page

    def test_fetch_videos_success(self):
        mock_ctx, _ = self._make_mock_context(MOCK_HTML)

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", return_value=mock_ctx):
            fetcher = PlaywrightBilibiliFetcher()
            videos = fetcher.fetch_videos("12345")

        assert len(videos) == 2
        assert all(isinstance(v, FetchedVideo) for v in videos)
        assert videos[0].bvid == "BV1xx411c7mD"

    def test_fetch_videos_empty_page_raises(self):
        mock_ctx, _ = self._make_mock_context(MOCK_HTML_EMPTY)

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", return_value=mock_ctx):
            fetcher = PlaywrightBilibiliFetcher()

            with pytest.raises(FetchError):
                fetcher.fetch_videos("12345")

    def test_fetch_creator_name(self):
        mock_ctx, _ = self._make_mock_context(MOCK_HTML_CARD)

        with patch.object(PlaywrightBilibiliFetcher, "_create_context", return_value=mock_ctx):
            fetcher = PlaywrightBilibiliFetcher()
            name = fetcher.fetch_creator_name("12345")

        assert name == "测试UP主"
