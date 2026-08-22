"""全局配置：数据目录、同步间隔、B 站 Cookie。可用 .env 覆盖（见 model_config）。"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据目录默认在仓库外的 ../private-data/bilibili-tag-group/，由用户自行用 git 管理
    data_dir: Path = (
        Path(__file__).resolve().parent.parent.parent / "private-data" / "bilibili-tag-group"
    )
    sync_interval_minutes: int = 60
    bilibili_cookie: str = ""
    """B 站登录 Cookie（可选）。设置有效的 Cookie 可以提高反爬成功率。
    在项目根目录的 .env 文件中配置：BILIBILI_COOKIE=SESSDATA=xxxx; bili_jct=xxxx"""
    # 启动器与前端开发服务器共用的端口配置，scripts/manage.py 启动 uvicorn、
    # frontend/vite.config.ts 读 proxy target 与 server.port 都从这里来；
    # 无 .env 时走默认值，改端口只动 .env 一处
    backend_host: str = "127.0.0.1"
    backend_port: int = 3333
    frontend_port: int = 2222

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
