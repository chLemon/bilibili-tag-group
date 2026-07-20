"""测试抓取层：PlaywrightBilibiliFetcher 与 FetchedVideo 标准化逻辑。"""
from datetime import datetime, timezone
import logging
from unittest.mock import AsyncMock, MagicMock, patch


from app.fetcher.models import FetchedVideo
from app.fetcher.playwright_fetcher import (
    PlaywrightBilibiliFetcher,
)

class TestPlaywrightBilibiliFetcher:
    """测试 PlaywrightBilibiliFetcher 方法（mock 浏览器部分）。"""

    async def test_fetch_videos_success(self):
        uid = "1024129080"  # 东哥，视频多

        fetcher = PlaywrightBilibiliFetcher()
        videos: list[FetchedVideo] = await fetcher.fetch_new_videos(uid)
        assert len(videos) > 999
        logging.info(videos[0])
        logging.info(len(videos))

    async def test_fetch_creator_info(self):
        uid = "1024129080" # 东哥，视频多

        fetcher = PlaywrightBilibiliFetcher()
        creator_info : dict = await fetcher.fetch_creator_info(uid)
        assert creator_info["name"] == '烧毁一切就是美'
        assert len(creator_info["avatar_url"]) > 0
        assert creator_info['video_count'] > 999
        logging.info(creator_info)
