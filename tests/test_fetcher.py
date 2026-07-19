"""测试抓取层：PlaywrightBilibiliFetcher 与 FetchedVideo 标准化逻辑。"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


from app.fetcher.models import FetchedVideo
from app.fetcher.playwright_fetcher import (
    PlaywrightBilibiliFetcher,
)

class TestPlaywrightBilibiliFetcher:
    """测试 PlaywrightBilibiliFetcher 方法（mock 浏览器部分）。"""

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
            videos = await fetcher.fetch_new_videos("12345", ttl_cache=False)

        assert len(videos) == 1
        assert all(isinstance(v, FetchedVideo) for v in videos)
        assert videos[0].bvid == "BV1xx411c7mD"

    async def test_fetch_creator_info(self):
        uid = "1024129080" # 东哥，视频多

        fetcher = PlaywrightBilibiliFetcher()
        creator_info : dict = await fetcher.fetch_creator_info(uid)
        assert creator_info["name"] == '烧毁一切就是美'
        assert len(creator_info["avatar_url"]) > 0
        assert creator_info['video_count'] > 999
        print(creator_info)
