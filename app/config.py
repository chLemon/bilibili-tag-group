"""全局配置：从项目根 config.json 读取，前端与 scripts/manage.py 共享同一份。"""

import json
from pathlib import Path

from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"

# 数据目录默认在仓库外的 ../private-data/bilibili-tag-group/，由用户自行用 git 管理
DEFAULT_DATA_DIR = PROJECT_ROOT.parent / "private-data" / "bilibili-tag-group"


class Settings(BaseModel):
    data_dir: Path = DEFAULT_DATA_DIR
    # 端口与同步间隔从 config.json 读，前端 vite.config.ts 也读同一份；
    # data_dir 是 Python 专属路径逻辑，不放 config.json
    backend_host: str = "127.0.0.1"
    backend_port: int = 3333
    frontend_port: int = 2222
    sync_interval_minutes: int = 60


def _load_settings() -> Settings:
    """读 config.json 覆盖默认值；文件缺失或字段非法用默认值兜底。"""
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    return Settings.model_validate(data)


settings = _load_settings()
