"""同步相关的 Pydantic Schema。"""
from typing import Optional

from app.schemas._datetime import BeijingDateTime

from pydantic import BaseModel, ConfigDict


class SyncTaskVo(BaseModel):
    """同步日志读取响应体（对应 SyncLog ORM 字段）。"""

    # 主键
    id: int
    # 范围
    scope: str
    # 状态
    status: str
    # 开始时间
    started_at: BeijingDateTime
    # 结束时间
    finished_at: Optional[BeijingDateTime] = None
    # 最近心跳时间
    heartbeat_at: Optional[BeijingDateTime] = None
    # 新视频的数量
    new_videos_count: int
    # 总共更新up数
    total_creators: int
    # 更新成功up数
    completed_creators: int
    # 当前更新up
    current_creator_name: Optional[str] = None
    # 失败信息，json，up和对应失败原因
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
