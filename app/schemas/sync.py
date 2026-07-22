"""同步相关的 Pydantic Schema。"""

from pydantic import BaseModel

from app.schemas._datetime import BeijingDateTime


class SyncTaskRead(BaseModel):
    """同步任务响应体，时间字段序列化为北京时间。"""

    id: int
    scope: str
    status: str
    total_creators: int
    completed_creators: int
    current_creator_name: str | None = None
    new_videos: int
    error_message: str | None = None
    started_at: BeijingDateTime
    finished_at: BeijingDateTime | None = None
    heartbeat_at: BeijingDateTime | None = None

    model_config = {"from_attributes": True}
