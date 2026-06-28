"""自定义 datetime 序列化类型。

后端存储 naive UTC 时间，序列化为 JSON 时转换为北京时间（UTC+8）的 ISO8601 字符串。
"""
from datetime import datetime, timedelta, timezone

from pydantic import PlainSerializer
from typing import Annotated

_BEIJING_TZ = timezone(timedelta(hours=8))


def _serialize_datetime(dt: datetime) -> str:
    """将 naive UTC datetime 转为北京时间 ISO8601 字符串（不带时区后缀）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    beijing = dt.astimezone(_BEIJING_TZ)
    return beijing.replace(tzinfo=None).isoformat()


BeijingDateTime = Annotated[
    datetime,
    PlainSerializer(_serialize_datetime, return_type=str, when_used="json"),
]
