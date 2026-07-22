"""FastAPI 应用入口：注册路由，通过 lifespan 管理定时同步调度器生命周期。"""
import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.dependencies import init_app
from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.logging_config import setup_logging
from app.routers.creators import router as creators_router
from app.routers.sync import router as sync_router
from app.routers.sync import set_sync_context
from app.routers.tags import router as tags_router
from app.routers.videos import router as videos_router
from app.scheduler import run_sync_loop
from app.services.sync_service import SyncService
from app.store.store import DataStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """初始化日志与全局实例，管理调度器与浏览器生命周期。"""
    setup_logging()
    store = DataStore(settings.data_dir)
    fetcher = PlaywrightBilibiliFetcher(cookie=settings.bilibili_cookie or None)
    sync_service = SyncService(fetcher=fetcher)
    init_app(store, fetcher, sync_service)

    sync_loop_task = asyncio.create_task(
        run_sync_loop(sync_service, store, settings.sync_interval_minutes)
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
        await fetcher.close_browser()


app = FastAPI(title="my_bilibili", lifespan=lifespan)

app.include_router(creators_router)
app.include_router(tags_router)
app.include_router(videos_router)
app.include_router(sync_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器：记录完整堆栈到日志文件后返回 500。"""
    logger.exception("未捕获的异常: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请查看日志"})


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}
