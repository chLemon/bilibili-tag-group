"""抓取层数据模型：用 dataclass 表示从 B 站接口获取的视频信息。"""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FetchedVideo:
    """从 B 站接口抓取到的单条视频信息，字段经过标准化处理。"""

    bvid: str
    """视频唯一 ID，如 BV1xx411c7mD"""

    title: str
    """视频标题"""

    video_url: str
    """视频页面 URL，格式：https://www.bilibili.com/video/{bvid}"""

    published_at: datetime
    """发布时间：UTC 时刻对应的 naive datetime（已去掉 tzinfo，但表示的是 UTC 时间）"""

    duration_seconds: int
    """视频时长（秒）"""
