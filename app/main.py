"""FastAPI 应用入口：注册路由，通过 lifespan 管理定时同步调度器生命周期。"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import SessionLocal, run_migrations
from app.routers.creators import router as creators_router
from app.routers.sync import router as sync_router, set_sync_context
from app.routers.tags import router as tags_router
from app.routers.videos import router as videos_router
from app.scheduler import run_sync_loop
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.services.sync_service import SyncService

# ── 日志配置 ──────────────────────────────────────────────────────

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_file_handler = RotatingFileHandler(
    LOG_DIR / "app.log",
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stderr),
        _file_handler,
    ],
)

logger = logging.getLogger(__name__)

_fetcher = PlaywrightBilibiliFetcher(
    cookie=settings.bilibili_cookie if settings.bilibili_cookie else None
)
_sync_svc = SyncService(fetcher=_fetcher)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """管理调度器生命周期：启动时创建定时同步协程，关闭时清理。"""
    run_migrations()
    sync_loop_task = asyncio.create_task(
        run_sync_loop(_sync_svc, SessionLocal, settings.sync_interval_minutes)
    )
    set_sync_context(True, settings.sync_interval_minutes)
    try:
        yield
    finally:
        sync_loop_task.cancel()
        try:
            await sync_loop_task
        except asyncio.CancelledError:
            pass
        await _fetcher.close_browser()


app = FastAPI(title="my_bilibili", lifespan=lifespan)

app.include_router(creators_router)
app.include_router(tags_router)
app.include_router(videos_router)
app.include_router(sync_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器：记录完整堆栈到日志文件后返回 500。"""
    logger.exception(
        "未捕获的异常: %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请查看日志"},
    )


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}
