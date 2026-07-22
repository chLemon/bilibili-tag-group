"""now_utc 工具函数测试。"""
from datetime import UTC, datetime, timedelta

from app.utils.time import now_utc


def test_now_utc_returns_naive_datetime():
    assert now_utc().tzinfo is None


def test_now_utc_is_close_to_real_utc():
    t = now_utc()
    expected = datetime.now(UTC).replace(tzinfo=None)
    assert abs(expected - t) < timedelta(seconds=5)
