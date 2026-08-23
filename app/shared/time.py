"""时间工具：统一 naive UTC 约定，并提供北京时间序列化类型。

- `now_utc()`：产生当前 naive UTC datetime，给 model/service 运行时用
- `BeijingDateTime`：Pydantic 类型，给 schema 序列化用——API 响应时把 naive UTC 转为北京时间 ISO8601 字符串
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

from pydantic import PlainSerializer

_BEIJING_TZ = timezone(timedelta(hours=8))


def now_utc() -> datetime:
    """返回当前 UTC 时间（naive datetime，不含 tzinfo）。"""
    return datetime.now(UTC).replace(tzinfo=None)


def _serialize_datetime(dt: datetime) -> str:
    """将 naive UTC datetime 转为北京时间 ISO8601 字符串（不带时区后缀）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    beijing = dt.astimezone(_BEIJING_TZ)
    return beijing.replace(tzinfo=None).isoformat()


BeijingDateTime = Annotated[
    datetime,
    PlainSerializer(_serialize_datetime, return_type=str, when_used="json"),
]
