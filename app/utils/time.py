"""时间工具：统一 naive UTC 约定。"""
from datetime import UTC, datetime


def now_utc() -> datetime:
    """返回当前 UTC 时间（naive datetime，不含 tzinfo）。"""
    return datetime.now(UTC).replace(tzinfo=None)
