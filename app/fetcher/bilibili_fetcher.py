"""B 站视频抓取器：调用 B 站开放接口获取 UP 主的视频列表。"""
from datetime import datetime, timezone

import httpx

from app.fetcher.models import FetchedVideo


class FetchError(Exception):
    """抓取失败时抛出此异常（如非 200 状态码、网络错误等）。"""


class BilibiliFetcher:
    """B 站视频抓取器，封装对 space.wbi.arc.search 接口的调用与数据标准化。"""

    API_URL = "https://api.bilibili.com/x/space/wbi/arc/search"

    def fetch_videos(self, uid: str) -> list[FetchedVideo]:
        """抓取指定 UP 主（uid）的最新视频列表。

        参数：
            uid: UP 主的数字 ID（字符串形式）

        返回：
            FetchedVideo 列表，字段已标准化

        异常：
            FetchError: 接口返回非 200 状态码时抛出
        """
        response = httpx.get(
            self.API_URL,
            params={"mid": uid, "pn": 1, "ps": 30},
            timeout=10,
        )
        if response.status_code != 200:
            raise FetchError(
                f"B 站接口返回异常状态码 {response.status_code}，uid={uid}"
            )

        data = response.json()
        if data.get("code") != 0:
            raise FetchError(
                f"B 站接口返回业务错误 code={data.get('code')}，uid={uid}，message={data.get('message', '')}"
            )

        vlist = data["data"]["list"]["vlist"]
        return [self._parse_video(item) for item in vlist]

    def _parse_video(self, item: dict) -> FetchedVideo:
        """将接口返回的单条视频 dict 转换为 FetchedVideo。"""
        bvid = item["bvid"]
        video_url = f"https://www.bilibili.com/video/{bvid}"

        # Unix 时间戳 -> UTC naive datetime
        published_at = datetime.fromtimestamp(
            item["created"], tz=timezone.utc
        ).replace(tzinfo=None)

        duration_seconds = self._parse_duration(item["length"])

        return FetchedVideo(
            bvid=bvid,
            title=item["title"],
            video_url=video_url,
            published_at=published_at,
            duration_seconds=duration_seconds,
        )

    @staticmethod
    def _parse_duration(length: str) -> int:
        """将时长字符串解析为秒数。

        支持格式：
        - "SS"（如 "45"）
        - "MM:SS"（如 "10:30"）
        - "HH:MM:SS"（如 "01:05:20"）
        """
        parts = length.split(":")
        if len(parts) == 1:
            # 仅秒数
            return int(parts[0])
        elif len(parts) == 2:
            # 分:秒
            return int(parts[0]) * 60 + int(parts[1])
        else:
            # 时:分:秒
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
