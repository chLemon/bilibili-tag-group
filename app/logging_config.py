"""日志配置：统一输出到 stderr，由 manage.py 重定向落盘到 logs/backend.log。"""

import logging
import sys

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging() -> None:
    """配置全局日志（幂等，lifespan 中调用）。

    只挂 stderr handler：服务固定由 manage.py 启动，stderr 会被重定向到
    backend.log（含 uvicorn 自身输出，是排障的唯一日志文件）。
    """
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=logging.INFO,
        format=_FORMAT,
        datefmt=_DATEFMT,
        handlers=[logging.StreamHandler(sys.stderr)],
    )
    _configured = True
