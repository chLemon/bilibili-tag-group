"""测试抓取层：PlaywrightBilibiliFetcher 真实接口抓取。"""

import logging
from collections.abc import AsyncIterator
from datetime import datetime

import pytest
import pytest_asyncio

from app.config import settings
from app.fetcher.models import FetchedVideo
from app.fetcher.playwright_fetcher import (
    PlaywrightBilibiliFetcher,
)

# MayzaRun
TEST_UID = "880104"
EXPECTED_NAME = "MayzaRun"

# 整个模块共享一个 module 级事件循环，让 module-scoped fixture 能跨测试复用 chromium
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def fetcher() -> AsyncIterator[PlaywrightBilibiliFetcher]:
    """模块级共享 fetcher：chromium 只启动一次，所有测试复用，模块结束统一关闭。"""
    f = PlaywrightBilibiliFetcher(cookies=settings.cookies)
    try:
        yield f
    finally:
        await f.close()


class TestPlaywrightBilibiliFetcher:
    """真实 B 站接口抓取，需网络与 chromium。"""

    async def test_fetch_videos_success(self, fetcher: PlaywrightBilibiliFetcher):
        videos: list[FetchedVideo] = await fetcher.fetch_new_videos(TEST_UID)
        assert videos, "应至少抓到一个视频"
        assert len(videos) == 48, f"应抓到 48 个视频，实际 {len(videos)}"

        bvids = [v.bvid for v in videos]
        assert len(bvids) == len(set(bvids)), "bvid 不应重复出现"

        for v in videos:
            assert v.bvid.startswith("BV"), f"bvid 应以 BV 开头: {v.bvid}"
            assert v.title.strip(), f"title 不应为空白: {v.bvid}"
            assert v.video_url == f"https://www.bilibili.com/video/{v.bvid}"
            assert v.cover_url.startswith("https://"), \
                f"cover_url 应是 https 开头: {v.cover_url}"
            assert isinstance(v.published_at, datetime)
            assert v.duration_seconds >= 0
            assert isinstance(v.mark, str), f"mark 应是 str: {v.bvid}"
            assert v.mark in ("", "充电视频"), \
                f"mark 值域异常: {v.bvid} mark={v.mark!r}"
        logging.info(videos[0])
        logging.info(len(videos))

    async def test_fetch_creator_info(self, fetcher: PlaywrightBilibiliFetcher):
        creator_info: dict = await fetcher.fetch_creator_info(TEST_UID)
        assert creator_info["name"] == EXPECTED_NAME
        assert creator_info["name"].strip() == creator_info["name"], "name 不应有前后空白"
        assert creator_info["avatar_url"].startswith("https://"), \
            f"avatar_url 应是 https 开头: {creator_info['avatar_url']}"
        assert isinstance(creator_info["video_count"], int)
        assert creator_info["video_count"] > 0
        logging.info(creator_info)

    async def test_fetch_new_videos_returns_union_with_known(
        self, fetcher: PlaywrightBilibiliFetcher
    ):
        """传 known_videos 时：翻到含已知 bvid 的页早停，并把未抓到的 known 补回返回值。"""
        full = await fetcher.fetch_new_videos(TEST_UID)
        assert len(full) > 2, "UP 主视频数不足以验证早停"

        # 取第 2 页会出现的 bvid 作为 known（第 1 页的会立即触发早停，覆盖不到翻页）
        # 构造 1 个已知视频：全集的最后一个（位于最末页）
        known = [full[-1]]
        partial = await fetcher.fetch_new_videos(TEST_UID, known_videos=known)

        # 返回的是并集：本次抓到的 + known 里未抓到的，bvid 集合应与全集一致
        assert {v.bvid for v in partial} == {v.bvid for v in full}

    async def test_fetch_creator_info_video_count_matches_videos(
        self, fetcher: PlaywrightBilibiliFetcher
    ):
        """侧栏 video_count 应与 fetch_new_videos 抓到的视频数一致。"""
        creator_info = await fetcher.fetch_creator_info(TEST_UID)
        videos = await fetcher.fetch_new_videos(TEST_UID)
        assert creator_info["video_count"] == len(videos), \
            f"video_count={creator_info['video_count']} 但 fetch_new_videos 返回 {len(videos)}"


