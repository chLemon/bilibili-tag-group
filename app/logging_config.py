"""日志配置：文件（logs/app.log，滚动）+ 控制台双输出。"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging() -> None:
    """配置全局日志（幂等，lifespan 中调用）。"""
    global _configured
    if _configured:
        return
    LOG_DIR.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))

    logging.basicConfig(
        level=logging.INFO,
        format=_FORMAT,
        datefmt=_DATEFMT,
        handlers=[logging.StreamHandler(sys.stderr), file_handler],
    )
    _configured = True
