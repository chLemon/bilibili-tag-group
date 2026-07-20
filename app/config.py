from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path(__file__).resolve().parent.parent / ".." / "private-data" / "bilibili-tag-group"
    sync_interval_minutes: int = 60
    bilibili_cookie: str = ""
    """B 站登录 Cookie（可选）。设置有效的 Cookie 可以提高反爬成功率。
    在项目根目录的 .env 文件中配置：BILIBILI_COOKIE=SESSDATA=xxxx; bili_jct=xxxx"""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
