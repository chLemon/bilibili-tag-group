"""B 站视频抓取器：调用 B 站开放接口获取 UP 主的视频列表。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.fetcher.models import FetchedVideo
from app.fetcher.wbi import BASE_HEADERS, sign_params

# B 站登录 Cookie 环境变量名
_BILIBILI_COOKIE_ENV = "BILIBILI_COOKIE"


class FetchError(Exception):
    """抓取失败时抛出此异常（如非 200 状态码、网络错误等）。"""


class BilibiliFetcher:
    """B 站视频抓取器，封装对 space.wbi.arc.search 接口的调用与数据标准化。"""

    API_URL = "https://api.bilibili.com/x/space/wbi/arc/search"

    def __init__(self, cookie: str | None = None) -> None:
        """初始化抓取器。

        参数：
            cookie: B 站登录 Cookie 字符串（可选）。
                    如果不传，会尝试读取环境变量 BILIBILI_COOKIE。
                    提供有效的 Cookie 可以提高反爬成功率。
        """
        self._cookie = cookie

    @property
    def _headers(self) -> dict[str, str]:
        """构建请求头，包含浏览器 UA、Referer 和可选的 Cookie。"""
        headers = dict(BASE_HEADERS)
        cookie = self._cookie or self._read_cookie_from_env()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    @staticmethod
    def _read_cookie_from_env() -> str | None:
        """从环境变量 BILIBILI_COOKIE 读取 Cookie。"""
        import os
        return os.environ.get(_BILIBILI_COOKIE_ENV)

    def fetch_videos(self, uid: str) -> list[FetchedVideo]:
        """抓取指定 UP 主（uid）的最新视频列表。

        参数：
            uid: UP 主的数字 ID（字符串形式）

        返回：
            FetchedVideo 列表，字段已标准化

        异常：
            FetchError: 接口返回非 200 状态码或业务错误时抛出
        """
        # WBI 签名：对原始参数添加 w_rid 和 wts
        raw_params: dict[str, str | int] = {"mid": uid, "pn": 1, "ps": 30}
        signed_params: dict[str, str] = sign_params(raw_params)

        response = httpx.get(
            self.API_URL,
            params=signed_params,
            headers=self._headers,
            timeout=10,
        )
        if response.status_code != 200:
            raise FetchError(
                f"B 站接口返回异常状态码 {response.status_code}，uid={uid}"
            )

        data = response.json()
        if data.get("code") != 0:
            raise FetchError(
                f"B 站接口返回业务错误 code={data.get('code')}，"
                f"uid={uid}，message={data.get('message', '')}"
            )

        vlist: list[dict[str, Any]] = data["data"]["list"]["vlist"]
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
