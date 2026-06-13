"""测试抓取层：BilibiliFetcher 与 FetchedVideo 标准化逻辑。"""
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
import respx
import httpx

from app.fetcher.models import FetchedVideo
from app.fetcher.bilibili_fetcher import BilibiliFetcher, FetchError

# 固定 WBI 签名返回值，避免测试中调用真实的 nav 接口
_FIXED_WTS = "1700000000"
_FIXED_WRID = "0123456789abcdef0123456789abcdef"


def _stub_sign_params(params: dict) -> dict[str, str]:
    """stub 版 sign_params：将原参数全转字符串并追加固定 wts/w_rid。"""
    result = {k: str(v) for k, v in params.items()}
    result["wts"] = _FIXED_WTS
    result["w_rid"] = _FIXED_WRID
    return result


@pytest.fixture(autouse=True)
def mock_sign_params():
    """全局 mock sign_params，避免测试中访问真实 B 站 nav 接口。"""
    with patch(
        "app.fetcher.bilibili_fetcher.sign_params",
        side_effect=_stub_sign_params,
    ) as mock:
        yield mock


# 模拟 B 站接口返回的典型 payload
MOCK_RESPONSE = {
    "code": 0,
    "data": {
        "list": {
            "vlist": [
                {
                    "bvid": "BV1xx411c7mD",
                    "title": "测试视频标题",
                    "created": 1700000000,  # Unix 时间戳
                    "length": "10:30",      # 分:秒 格式
                },
                {
                    "bvid": "BV2yy522d8nE",
                    "title": "第二个视频",
                    "created": 1700100000,
                    "length": "01:05:20",   # 时:分:秒 格式
                },
            ]
        }
    },
}

# 只有秒数的格式
MOCK_RESPONSE_SHORT = {
    "code": 0,
    "data": {
        "list": {
            "vlist": [
                {
                    "bvid": "BV3zz633e9oF",
                    "title": "短视频",
                    "created": 1700200000,
                    "length": "45",  # 仅秒数
                },
            ]
        }
    },
}


class TestFetchedVideo:
    """测试 FetchedVideo dataclass 基本属性。"""

    def test_dataclass_fields(self):
        """FetchedVideo 包含所有必需字段。"""
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


class TestBilibiliFetcher:
    """测试 BilibiliFetcher.fetch_videos 方法。"""

    @respx.mock
    def test_fetch_videos_returns_list_of_fetched_video(self):
        """fetch_videos 能把公开接口结果标准化为 FetchedVideo 列表。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(200, json=MOCK_RESPONSE)
        )
        fetcher = BilibiliFetcher()
        videos = fetcher.fetch_videos("12345")

        assert len(videos) == 2
        assert all(isinstance(v, FetchedVideo) for v in videos)

    @respx.mock
    def test_fetch_videos_bvid_and_url(self):
        """fetch_videos 正确设置 bvid 和视频页面 URL。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(200, json=MOCK_RESPONSE)
        )
        fetcher = BilibiliFetcher()
        videos = fetcher.fetch_videos("12345")

        assert videos[0].bvid == "BV1xx411c7mD"
        assert videos[0].video_url == "https://www.bilibili.com/video/BV1xx411c7mD"
        assert videos[1].bvid == "BV2yy522d8nE"
        assert videos[1].video_url == "https://www.bilibili.com/video/BV2yy522d8nE"

    @respx.mock
    def test_fetch_videos_duration_parsing_mm_ss(self):
        """fetch_videos 正确解析 MM:SS 格式的时长。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(200, json=MOCK_RESPONSE)
        )
        fetcher = BilibiliFetcher()
        videos = fetcher.fetch_videos("12345")

        # "10:30" -> 10*60 + 30 = 630 秒
        assert videos[0].duration_seconds == 630

    @respx.mock
    def test_fetch_videos_duration_parsing_hh_mm_ss(self):
        """fetch_videos 正确解析 HH:MM:SS 格式的时长。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(200, json=MOCK_RESPONSE)
        )
        fetcher = BilibiliFetcher()
        videos = fetcher.fetch_videos("12345")

        # "01:05:20" -> 1*3600 + 5*60 + 20 = 3920 秒
        assert videos[1].duration_seconds == 3920

    @respx.mock
    def test_fetch_videos_duration_parsing_seconds_only(self):
        """fetch_videos 正确解析纯秒数格式的时长。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(200, json=MOCK_RESPONSE_SHORT)
        )
        fetcher = BilibiliFetcher()
        videos = fetcher.fetch_videos("12345")

        # "45" -> 45 秒
        assert videos[0].duration_seconds == 45

    @respx.mock
    def test_fetch_videos_published_at_from_unix_timestamp(self):
        """fetch_videos 将 Unix 时间戳转换为 naive datetime（UTC）。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(200, json=MOCK_RESPONSE)
        )
        fetcher = BilibiliFetcher()
        videos = fetcher.fetch_videos("12345")

        expected = datetime.fromtimestamp(1700000000, tz=timezone.utc).replace(tzinfo=None)
        assert videos[0].published_at == expected
        assert videos[0].published_at.tzinfo is None

    @respx.mock
    def test_fetch_videos_raises_fetch_error_on_non_200(self):
        """非 200 状态码时抛出 FetchError。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(403, json={"code": -403})
        )
        fetcher = BilibiliFetcher()

        with pytest.raises(FetchError):
            fetcher.fetch_videos("12345")

    @respx.mock
    def test_fetch_videos_raises_fetch_error_on_500(self):
        """服务器错误时抛出 FetchError。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(500)
        )
        fetcher = BilibiliFetcher()

        with pytest.raises(FetchError):
            fetcher.fetch_videos("12345")

    @respx.mock
    def test_fetch_videos_raises_fetch_error_on_bilibili_error_code(self):
        """HTTP 200 但业务 code 非 0 时也应抛出 FetchError。"""
        respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(200, json={"code": -352, "message": "请求被拦截"})
        )
        fetcher = BilibiliFetcher()

        with pytest.raises(FetchError) as exc_info:
            fetcher.fetch_videos("12345")

        assert "code=-352" in str(exc_info.value)
        assert "12345" in str(exc_info.value)

    @respx.mock
    def test_fetch_videos_sends_correct_params(self):
        """fetch_videos 发送正确的请求参数（mid、pn、ps）。"""
        route = respx.get(BilibiliFetcher.API_URL).mock(
            return_value=httpx.Response(200, json=MOCK_RESPONSE)
        )
        fetcher = BilibiliFetcher()
        fetcher.fetch_videos("99999")

        assert route.called
        request = route.calls.last.request
        # 验证 URL 参数包含 mid=99999
        from httpx import URL
        url = URL(str(request.url))
        assert url.params["mid"] == "99999"
        assert url.params["pn"] == "1"
        assert url.params["ps"] == "30"

    def test_fetch_videos_passes_timeout_10_to_httpx_get(self):
        """fetch_videos 调用 httpx.get 时必须传入 timeout=10。"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_RESPONSE

        with patch("app.fetcher.bilibili_fetcher.httpx.get", return_value=mock_response) as mock_get:
            fetcher = BilibiliFetcher()
            fetcher.fetch_videos("12345")

            mock_get.assert_called_once()
            _, kwargs = mock_get.call_args
            assert kwargs.get("timeout") == 10
