"""FastAPI 应用入口：注册路由，通过 lifespan 管理定时同步调度器生命周期。"""
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
from app.routers.sync import router as sync_router, set_scheduler_context
from app.routers.tags import router as tags_router
from app.routers.videos import router as videos_router
from app.scheduler import build_scheduler
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


def _make_sync_job() -> None:
    """定时 job 回调：使用独立 Session 执行全量同步。

    每次调用开启新 Session，同步完成后自动关闭，异常不向上传播以保证调度器稳定。
    """
    db = SessionLocal()
    try:
        _sync_svc.sync_all(db)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("定时全量同步失败")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """管理调度器生命周期：启动时注册并启动，关闭时停止。"""
    run_migrations()
    scheduler = build_scheduler(
        sync_interval_minutes=settings.sync_interval_minutes,
        sync_callable=_make_sync_job,
    )
    # 将调度器实例与间隔配置注入 sync 路由，供 /api/sync/settings 读取
    set_scheduler_context(scheduler, settings.sync_interval_minutes)
    scheduler.start()
    try:
        yield
    finally:
        # wait=False：应用关闭时不阻塞等待正在执行的 job 结束。
        # 权衡：同步 job 可能被中断，但避免了 uvicorn 因超时强杀进程时
        # 造成 Session 泄漏或数据库连接悬挂。单次同步耗时通常很短，
        # 可接受此取舍；如需保证 job 完整执行，改为 wait=True。
        scheduler.shutdown(wait=False)


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
