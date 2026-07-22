# 工程化重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 bilibili-tag-group 全部已知 bug、收敛重复逻辑、达标仓库卫生与工具链、重写全部文档。

**Architecture:** 保持 FastAPI + Pydantic + JSON 文件存储架构不变。全应用共享单个 fetcher/SyncService 实例（lifespan 创建、依赖注入分发）；全量同步收敛为 `start_sync` + `run_sync_task` 一套实现；业务逻辑从路由收回 service 层。

**Tech Stack:** Python 3.12+ / uv / FastAPI / Pydantic v2 / Playwright / pytest / Vite + React + TypeScript / vitest

## Global Constraints

- 设计文档：`docs/superpowers/specs/2026-07-22-refactor-design.md`（D1-D4 决策以此为准）
- **D4 抓取层冻结**：不改动 `app/fetcher/` 的抓取、缓存 TTL（1h/24h）、重试、翻页、`_any_known` 行为；不改动 `sync_creator` 中 5min/50min 的 TTL 判断逻辑。唯一允许：`FetchedVideo.published_at` 类型标注修正、全应用共享 fetcher 实例
- **D3 数据兼容**：不改 `private-data/` 下 JSON 文件结构与字段含义
- **D1 logs 约定**：`logs/*.log` 保留在 git 中（跨机器排查用），`.gitignore` 只排除 `*.pid`
- **D2 脚本保留**：`start.ps1/stop.ps1/start.bat/stop.bat` 保留
- 时间字段统一 naive UTC；API 响应序列化北京时间用 `app/schemas/_datetime.py` 的 `BeijingDateTime`
- 使用 uv 管理依赖与执行命令（`uv run ...`），Python >= 3.12
- ruff 行宽 100，规则集 E/F/I/UP
- **不执行 git commit**（用户全局规则：仅用户明确要求时才提交）。每个任务完成后停下，由用户统一提交
- 测试基线命令：`uv run pytest`（默认跳过 integration marker）；前端：`cd frontend && npm test`

---

### Task 1: 修复依赖与测试基线

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_fetcher.py`

**Interfaces:**
- Produces: `httpx` 依赖可用（`fastapi.testclient` 需要）；marker `integration`（后续任务默认不跑真实网络测试）

- [ ] **Step 1: 修改 pyproject.toml**

`[project.optional-dependencies]` 整段替换为（删除 `test` extra，修正 `httpx2`）：

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.0,<9.0",
  "pytest-asyncio>=0.24,<1.0",
  "ruff>=0.4,<1.0",
  "httpx>=0.27,<1.0",
]
```

文件末尾追加：

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

`[tool.pytest.ini_options]` 中追加两行（与现有键并列）：

```toml
addopts = "-m 'not integration'"
markers = [
    "integration: 需要真实网络与浏览器的集成测试（默认跳过）",
]
```

- [ ] **Step 2: 标记集成测试**

`tests/test_fetcher.py` 中给两个测试方法加 marker（文件顶部 `import pytest` 已存在则复用）：

```python
@pytest.mark.integration
async def test_fetch_videos_success(self): ...

@pytest.mark.integration
async def test_fetch_creator_info(self): ...
```

- [ ] **Step 3: 验证基线**

Run: `uv sync --extra dev && uv run pytest --tb=short -q`
Expected: `69 passed, 2 deselected`（无 httpx 报错）

- [ ] **Step 4: 验证 ruff 可用**

Run: `uv run ruff check app tests`
Expected: 列出存量问题或通过（本任务不要求清零，只确认 ruff 可运行；存量问题在后续任务顺手修）

---

### Task 2: 统一 naive UTC 时间工具

**Files:**
- Create: `app/utils/__init__.py`
- Create: `app/utils/time.py`
- Modify: `app/models/sync_task.py:17`（`started_at` 默认值）
- Modify: `app/services/sync_service.py:16-17`（删除本地 `_now_utc`）
- Modify: `app/services/video_service.py:10-12`（删除本地 `_now_utc`）
- Test: `tests/test_utils_time.py`（新建）

**Interfaces:**
- Produces: `app.utils.time.now_utc() -> datetime`（naive UTC）。后续所有任务统一使用

- [ ] **Step 1: 写失败测试**

新建 `tests/test_utils_time.py`：

```python
"""now_utc 工具函数测试。"""
from datetime import datetime, timedelta, timezone

from app.utils.time import now_utc


def test_now_utc_returns_naive_datetime():
    assert now_utc().tzinfo is None


def test_now_utc_is_close_to_real_utc():
    t = now_utc()
    expected = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(expected - t) < timedelta(seconds=5)
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_utils_time.py -v`
Expected: FAIL（`ModuleNotFoundError: app.utils`）

- [ ] **Step 3: 实现**

`app/utils/__init__.py`（空文件，仅一行 docstring）：

```python
"""通用工具包。"""
```

`app/utils/time.py`：

```python
"""时间工具：统一 naive UTC 约定。"""
from datetime import datetime, timezone


def now_utc() -> datetime:
    """返回当前 UTC 时间（naive datetime，不含 tzinfo）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)
```

- [ ] **Step 4: 替换三处本地实现**

`app/services/sync_service.py`：删除 `_now_utc` 定义，改为 `from app.utils.time import now_utc as _now_utc`（保留 `_now_utc` 别名，函数体内调用点不动——这些调用点属于 D4 冻结逻辑周边，最小改动）。

`app/services/video_service.py`：同样删除本地 `_now_utc`，改为 `from app.utils.time import now_utc as _now_utc`。

`app/models/sync_task.py`：

```python
"""同步任务模型：追踪异步全量同步的进度。"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.utils.time import now_utc


class SyncTask(BaseModel):
    id: int = Field(default=0)
    scope: str = "all"
    status: str = "running"
    """running / completed / failed"""
    total_creators: int = 0
    completed_creators: int = 0
    current_creator_name: str | None = None
    new_videos: int = 0
    error_message: str | None = None
    started_at: datetime = Field(default_factory=now_utc)
    finished_at: datetime | None = None
    heartbeat_at: datetime | None = None
    """每次同步完一个 UP 主时更新，用于前端探活"""
```

- [ ] **Step 5: 运行测试**

Run: `uv run pytest --tb=short -q`
Expected: 全部通过（69 passed, 2 deselected）

---

### Task 3: 修复 VideoService.set_status 的 id 语义

**Files:**
- Modify: `app/services/video_service.py:18-30`
- Modify: `tests/test_services.py:388-419`（TestVideoService 传参语义）
- Test: `tests/test_services.py`（新增错位回归测试）

**Interfaces:**
- Consumes: `JsonRepo.filter(**kwargs)`（`app/store/repo.py:38`）
- Produces: `VideoService.set_status(store, video_id: int, status_value: int) -> VideoStatus | None`——参数语义为 **Video.id**（与路由 `/api/videos/{video_id}/status` 一致）

- [ ] **Step 1: 写失败回归测试**

`tests/test_services.py` 的 `TestVideoService` 类中新增：

```python
    async def test_set_status_uses_video_id_not_status_id(self, store):
        """Video.id 与 VideoStatus.id 错位时，仍按 video_id 正确定位。"""
        video1 = Video(
            bvid="BV_misalign_1", creator_id=1, title="v1",
            video_url="https://example.com/1",
            published_at=datetime(2024, 1, 1), duration_seconds=100,
        )
        video2 = Video(
            bvid="BV_misalign_2", creator_id=1, title="v2",
            video_url="https://example.com/2",
            published_at=datetime(2024, 1, 2), duration_seconds=100,
        )
        await store.videos.add(video1)
        await store.videos.add(video2)
        # 先给 video2 建状态（status id=1），再给 video1 建状态（status id=2），制造错位
        await store.video_statuses.add(VideoStatus(video_id=video2.id))
        await store.video_statuses.add(VideoStatus(video_id=video1.id))

        svc = VideoService()
        result = await svc.set_status(store, video1.id, 1)

        assert result is not None
        assert result.video_id == video1.id
        assert result.status == 1
        assert store.video_statuses.filter(video_id=video2.id)[0].status == 0
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_services.py::TestVideoService::test_set_status_uses_video_id_not_status_id -v`
Expected: FAIL（错位下改错了 video2 的状态或断言不成立）

- [ ] **Step 3: 修复实现**

`app/services/video_service.py` 的 `set_status` 替换为：

```python
    async def set_status(self, store: DataStore, video_id: int, status_value: int) -> VideoStatus | None:
        """更新视频状态（0=未看, 1=已看, 2=不看）。video_id 为 Video.id。"""
        matches = store.video_statuses.filter(video_id=video_id)
        if not matches:
            return None
        vs = matches[0]

        updates: dict[str, object] = {"status": status_value}
        if status_value == 1:
            updates["watched_at"] = _now_utc()
        else:
            updates["watched_at"] = None
        await store.video_statuses.update(vs.id, **updates)
        return store.video_statuses.get(vs.id)
```

- [ ] **Step 4: 修正既有测试传参语义**

`tests/test_services.py` 的 `TestVideoService` 中，把 `svc.set_status(store, vs_list[0].id, ...)` 全部改为 `svc.set_status(store, seeded_data.video_id, ...)`（共 4 处：`test_set_status_watched`、`test_set_status_unwatched_clears_watched_at` 内 2 处、`test_set_status_ignored`）；删掉不再需要的 `vs_list` 局部变量与断言，保留行为断言。

- [ ] **Step 5: 运行测试**

Run: `uv run pytest --tb=short -q`
Expected: 全部通过

---

### Task 4: 依赖注入改造（日志配置抽离 + fetcher/SyncService 单例）

**Files:**
- Create: `app/logging_config.py`
- Modify: `app/dependencies.py`（扩展 init/get）
- Modify: `app/main.py`（移除模块级副作用，lifespan 统一创建实例）
- Modify: `app/routers/creators.py`（删除模块级 fetcher，改 Depends）
- Modify: `app/routers/sync.py`（删除模块级 _sync_svc，改 Depends）
- Modify: `tests/conftest.py`（override get_fetcher / get_sync_service）
- Modify: `tests/test_routers.py:258-303`（TestSyncRun 改为 override 方式）

**Interfaces:**
- Produces:
  - `app.logging_config.setup_logging() -> None`（幂等）
  - `app.dependencies.init_app(store, fetcher, sync_service) -> None`
  - `app.dependencies.get_fetcher() -> PlaywrightBilibiliFetcher`
  - `app.dependencies.get_sync_service() -> SyncService`
  - conftest `mock_fetcher` fixture（`fetch_creator_info`/`fetch_new_videos` 为 AsyncMock）
- 后续任务的路由签名约定：`fetcher: Annotated[PlaywrightBilibiliFetcher, Depends(get_fetcher)]`、`sync_svc: Annotated[SyncService, Depends(get_sync_service)]`

注意：`init_store` 删除，由 `init_app` 替代（仅 lifespan 调用，无其他调用方）。

- [ ] **Step 1: 新建 app/logging_config.py**

```python
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
```

- [ ] **Step 2: 改写 app/dependencies.py**

```python
"""FastAPI 依赖注入函数。"""
from __future__ import annotations

from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher
from app.services.sync_service import SyncService
from app.store.store import DataStore

_store: DataStore | None = None
_fetcher: PlaywrightBilibiliFetcher | None = None
_sync_service: SyncService | None = None


def init_app(
    store: DataStore,
    fetcher: PlaywrightBilibiliFetcher,
    sync_service: SyncService,
) -> None:
    """初始化全局应用实例（由 lifespan 调用）。"""
    global _store, _fetcher, _sync_service
    _store = store
    _fetcher = fetcher
    _sync_service = sync_service


def get_store() -> DataStore:
    """提供全局 DataStore 实例。"""
    if _store is None:
        raise RuntimeError("应用尚未初始化，请先调用 init_app()")
    return _store


def get_fetcher() -> PlaywrightBilibiliFetcher:
    """提供全局 B 站抓取器实例。"""
    if _fetcher is None:
        raise RuntimeError("应用尚未初始化，请先调用 init_app()")
    return _fetcher


def get_sync_service() -> SyncService:
    """提供全局 SyncService 实例。"""
    if _sync_service is None:
        raise RuntimeError("应用尚未初始化，请先调用 init_app()")
    return _sync_service
```

- [ ] **Step 3: 改写 app/main.py**

```python
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
from app.routers.sync import router as sync_router, set_sync_context
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
```

- [ ] **Step 4: 路由改 Depends（编译通过即可，逻辑瘦身在 Task 5/6）**

`app/routers/creators.py`：删除 `from app.config import settings` 与模块级 `_fetcher = ...`；`batch_create_creators` 与 `resolve_creator_name` 增加参数：

```python
fetcher: Annotated[PlaywrightBilibiliFetcher, Depends(get_fetcher)],
```

函数体内 `_fetcher` 引用改为 `fetcher`（`resolve_creator_name` 同步 `def` 改为 `async def`，内部调用改为 `await fetcher.fetch_creator_info(uid)`——await 修复在此顺带完成；batch 内的 `_fetcher.fetch_creator_info(item.uid)` 改为 `await fetcher.fetch_creator_info(item.uid)`）。

`app/routers/sync.py`：删除 `from app.config import settings`、`from app.fetcher.playwright_fetcher import PlaywrightBilibiliFetcher`、模块级 `_sync_svc`；`run_sync` 增加参数 `sync_svc: Annotated[SyncService, Depends(get_sync_service)]`，函数体内 `_sync_svc` 改为 `sync_svc`。

- [ ] **Step 5: 更新 conftest**

`tests/conftest.py` 的 import 区追加：

```python
from unittest.mock import AsyncMock, MagicMock

from app.dependencies import get_fetcher, get_store, get_sync_service
from app.services.sync_service import SyncService
```

（删除原有的 `from app.dependencies import get_store`。）追加 fixture 并改写 `client`：

```python
@pytest.fixture
def mock_fetcher():
    """默认 mock 抓取器：昵称/头像固定返回，视频列表为空。"""
    m = MagicMock()
    m.fetch_creator_info = AsyncMock(
        return_value={"name": "测试UP主", "avatar_url": None, "video_count": 0}
    )
    m.fetch_new_videos = AsyncMock(return_value=[])
    return m


@pytest.fixture
def client(store, mock_fetcher):
    """提供绑定到临时 DataStore 与 mock 抓取器的 FastAPI TestClient。"""
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_fetcher] = lambda: mock_fetcher
    app.dependency_overrides[get_sync_service] = lambda: SyncService(fetcher=mock_fetcher)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 6: 改写 TestSyncRun**

`tests/test_routers.py` 的 `TestSyncRun` 两个测试不再 patch 模块变量，改为直接调用（conftest 已 override 为 mock fetcher，无 creator 时任务立即完成）：

```python
class TestSyncRun:
    """POST /api/sync/run 测试。"""

    def test_run_sync_returns_task(self, client):
        """手动触发全量同步，返回 SyncTask。"""
        response = client.post("/api/sync/run")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("running", "completed")

    def test_run_sync_with_real_db_no_creators(self, client):
        """无 creator 时全量同步立即完成。"""
        response = client.post("/api/sync/run")
        assert response.status_code == 200
        body = response.json()
        assert body["total_creators"] == 0
```

（顶部 `patch`、`AsyncMock` import 若无其他使用则删除。）

- [ ] **Step 7: 运行测试**

Run: `uv run pytest --tb=short -q`
Expected: 全部通过

---

### Task 5: creators 路由瘦身（to_read / batch / resolve 移入 CreatorService）

**Files:**
- Modify: `app/services/creator_service.py`（新增 `to_read`、`resolve_creator_info`、`batch_create`、`uid_from_profile_url`）
- Modify: `app/routers/creators.py`（删除 `_UID_RE`、`_uid_from_profile_url`、`_to_creator_read` 与 batch 编排）
- Test: `tests/test_routers.py`（新增 resolve-name 与 batch 的回归测试）

**Interfaces:**
- Consumes: Task 4 的 `get_fetcher`、conftest `mock_fetcher`
- Produces:
  - `CreatorService.uid_from_profile_url(profile_url: str) -> str`（静态方法，无法解析时 `raise ValueError`）
  - `CreatorService.to_read(store, creator) -> CreatorRead`
  - `CreatorService.resolve_creator_info(fetcher, profile_url) -> dict`（fetcher 抛 `FetchError` 原样上抛）
  - `CreatorService.batch_create(store, fetcher, items: list[BatchCreatorItem]) -> BatchCreatorResponse`

- [ ] **Step 1: 写失败回归测试**

`tests/test_routers.py` 新增（文件顶部确保 `from app.dependencies import get_fetcher` 及 `AsyncMock, MagicMock` 可用）：

```python
class TestResolveName:
    """GET /api/creators/resolve-name 测试。"""

    def test_resolve_name_returns_info(self, client, mock_fetcher):
        mock_fetcher.fetch_creator_info = AsyncMock(
            return_value={"name": "某UP", "avatar_url": "https://x/a.jpg", "video_count": 10}
        )
        response = client.get(
            "/api/creators/resolve-name",
            params={"profile_url": "https://space.bilibili.com/12345"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "某UP"
        assert response.json()["avatar_url"] == "https://x/a.jpg"

    def test_resolve_name_invalid_url_returns_400(self, client):
        response = client.get(
            "/api/creators/resolve-name", params={"profile_url": "not-a-url"}
        )
        assert response.status_code == 400


class TestBatchCreateCreators:
    """POST /api/creators/batch 测试。"""

    def test_batch_create_success(self, client, mock_fetcher):
        mock_fetcher.fetch_creator_info = AsyncMock(
            return_value={"name": "UP1", "avatar_url": None, "video_count": 3}
        )
        response = client.post(
            "/api/creators/batch",
            json={"items": [{"uid": "123", "tag_names": ["游戏"]}]},
        )
        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["success"] is True
        assert result["creator"]["name"] == "UP1"
        assert result["creator"]["tag_ids"] != []

    def test_batch_create_fetch_failure(self, client, mock_fetcher):
        from app.fetcher.playwright_fetcher import FetchError
        mock_fetcher.fetch_creator_info = AsyncMock(side_effect=FetchError("被风控"))
        response = client.post(
            "/api/creators/batch", json={"items": [{"uid": "123"}]}
        )
        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["success"] is False
        assert "被风控" in result["error"]
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_routers.py -k "ResolveName or BatchCreate" -v`
Expected: FAIL（当前 resolve-name 未 await → 500；batch 同理）

- [ ] **Step 3: CreatorService 新增方法**

`app/services/creator_service.py` 顶部 import 追加：

```python
import logging
import re

from app.fetcher.playwright_fetcher import FetchError, PlaywrightBilibiliFetcher
from app.schemas.creator import (
    BatchCreatorItem,
    BatchCreatorResponse,
    BatchCreatorResult,
    CreatorRead,
)

logger = logging.getLogger(__name__)

_UID_RE = re.compile(r"space\.bilibili\.com/(\d+)")
```

类中新增：

```python
    @staticmethod
    def uid_from_profile_url(profile_url: str) -> str:
        """从 B 站主页 URL 中提取 uid；若已是纯数字 uid 则直接返回。"""
        trimmed = profile_url.strip()
        if trimmed.isdigit():
            return trimmed
        m = _UID_RE.search(trimmed)
        if m:
            return m.group(1)
        raise ValueError(f"无法从 URL 中提取 UID：{profile_url}")

    def to_read(self, store: DataStore, creator: Creator) -> CreatorRead:
        """将 Creator 模型转换为 CreatorRead schema，附带视频统计数据。"""
        videos_list = store.videos.filter(creator_id=creator.id)
        status_map = {s.video_id: s for s in store.video_statuses.all()}
        unwatched = sum(
            1 for v in videos_list
            if v.id not in status_map or status_map[v.id].status == 0
        )
        tag_ids = [link.tag_id for link in store.creator_tags.filter(creator_id=creator.id)]
        return CreatorRead(
            id=creator.id,
            name=creator.name,
            alias=creator.alias,
            profile_url=creator.profile_url,
            avatar_url=creator.avatar_url,
            tag_ids=tag_ids,
            enabled=creator.enabled,
            video_count=creator.video_count or 0,
            synced_video_count=len(videos_list),
            unwatched_count=unwatched,
            last_synced_at=creator.last_synced_at,
        )

    async def resolve_creator_info(
        self, fetcher: PlaywrightBilibiliFetcher, profile_url: str
    ) -> dict:
        """根据主页 URL 从 B 站获取 UP 主昵称和头像。"""
        uid = self.uid_from_profile_url(profile_url)
        return await fetcher.fetch_creator_info(uid)

    async def batch_create(
        self,
        store: DataStore,
        fetcher: PlaywrightBilibiliFetcher,
        items: list[BatchCreatorItem],
    ) -> BatchCreatorResponse:
        """批量添加 UP 主：逐条抓取昵称、关联标签、创建记录，单条失败不影响整体。"""
        results: list[BatchCreatorResult] = []
        for item in items:
            try:
                profile_url = f"https://space.bilibili.com/{item.uid}"
                if item.name:
                    creator_name = item.name
                    avatar_url = None
                else:
                    try:
                        info = await fetcher.fetch_creator_info(item.uid)
                        creator_name = info["name"]
                        avatar_url = info.get("avatar_url")
                    except FetchError as exc:
                        logger.exception("批量添加-获取 UP 主信息失败 uid=%s", item.uid)
                        results.append(BatchCreatorResult(
                            uid=item.uid, success=False, error=f"获取 UP 主信息失败：{exc}"
                        ))
                        continue

                tags = await self.find_or_create_tags(store, item.tag_names)
                creator = await self.create_creator(
                    store=store,
                    name=creator_name,
                    profile_url=profile_url,
                    tag_ids=[t.id for t in tags],
                    avatar_url=avatar_url,
                )
                results.append(BatchCreatorResult(
                    uid=item.uid, success=True, creator=self.to_read(store, creator)
                ))
            except Exception as exc:
                logger.exception("批量添加 UP 主失败 uid=%s", item.uid)
                results.append(BatchCreatorResult(uid=item.uid, success=False, error=str(exc)))
        return BatchCreatorResponse(results=results)
```

- [ ] **Step 4: 瘦身 routers/creators.py**

删除：`_UID_RE`、`_uid_from_profile_url`、`_to_creator_read`、`re` import、`settings` 相关残留、`FetchError` 中不再用的引用（保留路由需要的）。

路由要点（完整替换对应函数）：

```python
@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreatorRead)
async def create_creator(
    payload: CreatorCreate,
    store: Annotated[DataStore, Depends(get_store)],
) -> CreatorRead:
    """添加新 UP 主（可同时关联标签）。"""
    creator = await _creator_svc.create_creator(
        store=store,
        name=payload.name,
        profile_url=payload.profile_url,
        tag_ids=payload.tag_ids,
        avatar_url=payload.avatar_url,
        alias=payload.alias,
    )
    return _creator_svc.to_read(store, creator)


@router.post("/batch", status_code=status.HTTP_200_OK, response_model=BatchCreatorResponse)
async def batch_create_creators(
    payload: BatchCreatorRequest,
    store: Annotated[DataStore, Depends(get_store)],
    fetcher: Annotated[PlaywrightBilibiliFetcher, Depends(get_fetcher)],
) -> BatchCreatorResponse:
    """批量添加 UP 主。"""
    return await _creator_svc.batch_create(store, fetcher, payload.items)


@router.get("/resolve-name", response_model=dict)
async def resolve_creator_name(
    profile_url: str,
    fetcher: Annotated[PlaywrightBilibiliFetcher, Depends(get_fetcher)],
) -> dict:
    """根据主页 URL 从 B 站获取 UP 主昵称和头像。"""
    try:
        info = await _creator_svc.resolve_creator_info(fetcher, profile_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FetchError as exc:
        logger.exception("解析 UP 主名称失败 url=%s", profile_url)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"name": info["name"], "avatar_url": info.get("avatar_url")}
```

其余路由（list/get/videos/patch/batch_status）中 `_to_creator_read(x, store)` 调用全部改为 `_creator_svc.to_read(store, x)`。

- [ ] **Step 5: 运行测试**

Run: `uv run pytest --tb=short -q`
Expected: 全部通过（含新增 4 个回归测试）

---

### Task 6: 同步入口收敛（start_sync / run_sync_task，删除 sync_all）

**Files:**
- Modify: `app/services/sync_service.py`（`start_async_sync`→`start_sync` 返回 `(SyncTask, bool)`；`_run_async_sync`→`run_sync_task` 公开；删除 `sync_all`；新增 immediate-tags 三个方法）
- Modify: `app/routers/sync.py`（response_model 暂留 Task 8；immediate-tags 改调 service）
- Modify: `app/scheduler.py`
- Modify: `tests/test_services.py:146-218`（TestSyncAll 迁移）
- Test: `tests/test_services.py`（新增幂等测试）

**Interfaces:**
- Consumes: Task 2 的 `now_utc`、Task 4 的 `get_sync_service`
- Produces:
  - `SyncService.start_sync(store) -> tuple[SyncTask, bool]`（bool=是否新建；已有 running 任务返回 `(existing, False)`）
  - `SyncService.run_sync_task(task_id: int, store) -> None`（原 `_run_async_sync` 逻辑原样改名）
  - `SyncService.list_immediate_tags(store) -> list[TagSyncConfig]`
  - `SyncService.add_immediate_tag(store, tag_id: int) -> TagSyncConfig`（tag 不存在 `raise ValueError`）
  - `SyncService.remove_immediate_tag(store, tag_id: int) -> bool`

注意：`sync_creator` 及其 TTL 判断逻辑（D4）**一行不动**。

- [ ] **Step 1: 迁移 TestSyncAll 并新增幂等测试（先失败）**

`tests/test_services.py` 中 `TestSyncAll` 全部改为通过 `start_sync` + `run_sync_task` 驱动。文件顶部 import 区下方加辅助函数：

```python
async def _run_full_sync(service: SyncService, store) -> SyncTask:
    """创建并执行一次全量同步，返回最终 SyncTask。"""
    task, created = await service.start_sync(store)
    assert created
    await service.run_sync_task(task.id, store)
    final = store.sync_tasks.get(task.id)
    assert final is not None
    return final
```

`TestSyncAll` 各测试中原 `task = await service.sync_all(store)` 替换为 `task = await _run_full_sync(service, store)`，断言不变。新增：

```python
class TestStartSyncIdempotent:
    async def test_second_start_returns_existing_task(self, store):
        service = SyncService(fetcher=_make_mock_fetcher())
        task1, created1 = await service.start_sync(store)
        task2, created2 = await service.start_sync(store)
        assert created1 is True
        assert created2 is False
        assert task1.id == task2.id
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_services.py -v`
Expected: FAIL（`SyncService` 无 `start_sync`/`run_sync_task` 属性）

- [ ] **Step 3: 改写 SyncService**

`start_async_sync` 改名为 `start_sync`，签名与返回调整（心跳判死逻辑原样保留）：

```python
    async def start_sync(self, store: DataStore) -> tuple[SyncTask, bool]:
        """创建全量同步任务并返回 (task, created)。

        已有 running 任务时：心跳超时则标记失败并新建；否则返回 (existing, False)，
        调用方不得再启动执行协程。
        """
        running = store.sync_tasks.filter(status="running")
        if running:
            existing = max(running, key=lambda t: t.started_at)
            if existing.heartbeat_at is not None:
                age_sec = (_now_utc() - existing.heartbeat_at).total_seconds()
                if age_sec >= self._HEARTBEAT_DEAD_SEC:
                    await store.sync_tasks.update(
                        existing.id,
                        status="failed",
                        error_message="任务进程崩溃，心跳超时未更新",
                        finished_at=_now_utc(),
                    )
                else:
                    return existing, False
            else:
                return existing, False

        total = len(store.creators.all())
        task = SyncTask(
            status="running",
            total_creators=total,
            completed_creators=0,
            new_videos=0,
            started_at=_now_utc(),
            heartbeat_at=_now_utc(),
        )
        await store.sync_tasks.add(task)
        return task, True
```

`_run_async_sync` 改名为 `run_sync_task`（body 不变，仅去掉名字前的下划线）。

删除整个 `sync_all` 方法及 `# ── 调度器用同步方法 ──` 注释块。

类中新增 immediate-tags 方法：

```python
    # ── 立即同步标签管理 ──────────────────────────────────────────

    def list_immediate_tags(self, store: DataStore) -> list[TagSyncConfig]:
        """返回所有立即同步标签配置。"""
        return store.tag_sync_configs.all()

    async def add_immediate_tag(self, store: DataStore, tag_id: int) -> TagSyncConfig:
        """将指定标签设为立即同步模式；已配置时直接返回现有配置。"""
        if store.tags.get(tag_id) is None:
            raise ValueError(f"标签 id={tag_id} 不存在")
        existing = store.tag_sync_configs.filter(tag_id=tag_id)
        if existing:
            return existing[0]
        config = TagSyncConfig(tag_id=tag_id, sync_mode="immediate")
        await store.tag_sync_configs.add(config)
        return config

    async def remove_immediate_tag(self, store: DataStore, tag_id: int) -> bool:
        """移除标签的立即同步配置；未配置时返回 False。"""
        configs = store.tag_sync_configs.filter(tag_id=tag_id)
        if not configs:
            return False
        await store.tag_sync_configs.delete(configs[0].id)
        return True
```

import 区确认有 `from app.models.tag_sync_config import TagSyncConfig`（原文件没有则新增），删除不再使用的 import（如 `Video`/`VideoStatus` 仍被 `sync_creator` 使用则保留）。

- [ ] **Step 4: 改写 app/scheduler.py**

```python
"""定时同步调度：使用 asyncio 循环替代 APScheduler。"""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def run_sync_loop(sync_service, store, interval_minutes: int) -> None:
    """每隔 interval_minutes 分钟执行一次全量同步。

    通过 asyncio.sleep 实现周期调度，与 FastAPI 共用同一事件循环。
    异常不向上传播，保证循环持续运行。
    """
    while True:
        await asyncio.sleep(interval_minutes * 60)
        try:
            task, created = await sync_service.start_sync(store)
            if created:
                await sync_service.run_sync_task(task.id, store)
        except Exception:
            logger.exception("定时全量同步失败")
```

- [ ] **Step 5: 改写 routers/sync.py 的 run 与 immediate-tags**

`run_sync`：

```python
@router.post("/run", response_model=SyncTask)
async def run_sync(
    store: Annotated[DataStore, Depends(get_store)],
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> SyncTask:
    """手动触发全量同步：幂等创建任务，后台协程执行，立即返回任务进度。"""
    task, created = await sync_svc.start_sync(store)
    if created:
        asyncio.create_task(sync_svc.run_sync_task(task.id, store))
    return task
```

immediate-tags 三个端点：

```python
@router.get("/immediate-tags", response_model=list[dict])
def list_immediate_tags(
    store: Annotated[DataStore, Depends(get_store)],
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> list[dict]:
    """查询所有配置了"立即同步"的标签列表。"""
    return [
        {"id": c.id, "tag_id": c.tag_id, "sync_mode": c.sync_mode}
        for c in sync_svc.list_immediate_tags(store)
    ]


@router.post("/immediate-tags", status_code=status.HTTP_201_CREATED, response_model=dict)
async def add_immediate_tag(
    tag_id: int,
    store: Annotated[DataStore, Depends(get_store)],
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> dict:
    """将指定标签设为"立即同步"模式。"""
    try:
        config = await sync_svc.add_immediate_tag(store, tag_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"id": config.id, "tag_id": config.tag_id, "sync_mode": config.sync_mode}


@router.delete("/immediate-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_immediate_tag(
    tag_id: int,
    store: Annotated[DataStore, Depends(get_store)],
    sync_svc: Annotated[SyncService, Depends(get_sync_service)],
) -> None:
    """将指定标签从"立即同步"中移除（恢复为默认 TTL 模式）。"""
    if not await sync_svc.remove_immediate_tag(store, tag_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"标签 id={tag_id} 未配置为立即同步",
        )
```

删除 routers/sync.py 顶部不再使用的 import（`settings`、`PlaywrightBilibiliFetcher`、`Tag`、`TagSyncConfig` 若不再直接引用）。

- [ ] **Step 6: 运行测试**

Run: `uv run pytest --tb=short -q`
Expected: 全部通过

---

### Task 7: sync_creator 健壮性（disabled 跳过 + None 日期跳过）

**Files:**
- Modify: `app/services/sync_service.py`（`sync_creator` 顶部加 enabled 检查；视频循环加 None 跳过）
- Modify: `app/fetcher/models.py:19`（仅类型标注）
- Test: `tests/test_services.py`（新增 2 个回归测试）

**Interfaces:**
- Consumes: 无新依赖
- Produces: `FetchedVideo.published_at: datetime | None`（标注修正，行为不变）

注意：只新增"跳过"分支，TTL 判断与抓取流程（D4）不动。

- [ ] **Step 1: 写失败测试**

`tests/test_services.py` 的 `TestSyncCreatorNewVideos` 类后新增：

```python
class TestSyncCreatorGuards:
    async def test_disabled_creator_is_skipped(self, store):
        creator = await _make_creator_async(store, enabled=False)
        mock_fetcher = _make_mock_fetcher()
        service = SyncService(fetcher=mock_fetcher)
        count = await service.sync_creator(store, creator)
        assert count == 0
        mock_fetcher.fetch_new_videos.assert_not_called()
        mock_fetcher.fetch_creator_info.assert_not_called()

    async def test_video_without_published_at_is_skipped(self, store):
        creator = await _make_creator_async(store)
        bad = FetchedVideo(
            bvid="BV_bad_date", title="无日期", video_url="https://example.com",
            published_at=None, duration_seconds=60,
        )
        good = _make_fetched_video("BV_good_date")
        mock_fetcher = _make_mock_fetcher(fetch_new_videos=[bad, good])
        service = SyncService(fetcher=mock_fetcher)
        count = await service.sync_creator(store, creator)
        assert count == 1
        bvids = [v.bvid for v in store.videos.filter(creator_id=creator.id)]
        assert bvids == ["BV_good_date"]
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_services.py::TestSyncCreatorGuards -v`
Expected: 2 个 FAIL（disabled 仍被抓取；published_at=None 构造即报错或写入失败）

- [ ] **Step 3: 修改标注与防护**

`app/fetcher/models.py`：

```python
    published_at: datetime | None
    """发布时间：UTC 时刻对应的 naive datetime；无法解析时为 None"""
```

`app/services/sync_service.py` 的 `sync_creator`：方法体最顶部（TTL 判断之前）加：

```python
        if not creator.enabled:
            return 0
```

视频循环内（`for fv in fetched_list:` 之后第一行）加：

```python
            if fv.published_at is None:
                logger.warning("跳过无发布时间的视频 bvid=%s", fv.bvid)
                continue
```

文件顶部加 `logger = logging.getLogger(__name__)` 与 `import logging`（若无）。

- [ ] **Step 4: 运行测试**

Run: `uv run pytest --tb=short -q`
Expected: 全部通过

---

### Task 8: SyncTask 响应时区序列化（SyncTaskRead）

**Files:**
- Create: `app/schemas/sync.py`
- Modify: `app/routers/sync.py`（`/latest`、`/run`、`/task/current` 的 response_model）
- Test: `tests/test_routers.py`（TestSyncLatest 新增时间断言）

**Interfaces:**
- Consumes: `app/schemas/_datetime.py` 的 `BeijingDateTime`
- Produces: `SyncTaskRead` schema（sync 路由所有 SyncTask 响应统一使用；前端收到的 `started_at` 等变为北京时间字符串）

- [ ] **Step 1: 写失败测试**

`tests/test_routers.py` 的 `test_returns_latest_sync_log` 末尾追加断言（该测试已构造 `started_at=datetime(2026, 1, 1, 10, 0, 0)` 的 UTC 时间）：

```python
        assert body["started_at"] == "2026-01-01T18:00:00"
        assert body["finished_at"] == "2026-01-01T18:01:00"
        assert body["heartbeat_at"] == "2026-01-01T18:01:00"
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run pytest tests/test_routers.py::TestSyncLatest -v`
Expected: FAIL（当前原样输出 `"2026-01-01T10:00:00"`）

- [ ] **Step 3: 新建 app/schemas/sync.py**

```python
"""同步相关的 Pydantic Schema。"""
from typing import Optional

from pydantic import BaseModel

from app.schemas._datetime import BeijingDateTime


class SyncTaskRead(BaseModel):
    """同步任务响应体，时间字段序列化为北京时间。"""

    id: int
    scope: str
    status: str
    total_creators: int
    completed_creators: int
    current_creator_name: Optional[str] = None
    new_videos: int
    error_message: Optional[str] = None
    started_at: BeijingDateTime
    finished_at: Optional[BeijingDateTime] = None
    heartbeat_at: Optional[BeijingDateTime] = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: 切换 response_model**

`app/routers/sync.py`：`/latest`、`/run`、`/task/current` 三个端点的 `response_model=SyncTask | None` / `response_model=SyncTask` 改为 `SyncTaskRead | None` / `SyncTaskRead`，import 相应调整（`from app.schemas.sync import SyncTaskRead`，`SyncTask` import 若不再用则删除）。返回类型标注同步更新。

- [ ] **Step 5: 运行测试**

Run: `uv run pytest --tb=short -q`
Expected: 全部通过

---

### Task 9: 前端修复（TagsPage render 期 setState）

**Files:**
- Modify: `frontend/src/pages/TagsPage.tsx:11-21`

**Interfaces:**
- Consumes: 无
- Produces: 选中标签初始化逻辑移至 `useEffect`，行为不变

- [ ] **Step 1: 修改 TagsPage.tsx**

删除 render 期的 if 块（原 16-21 行），替换为（`useEffect` 从 react import）：

```tsx
export default function TagsPage() {
  const { tags, loading: loadingTags, error: tagsError } = useTags();
  const [selectedTagId, setSelectedTagId] = useState<number | null>(null);

  // 标签加载完成后自动选中第一个；无标签时选中"无标签"
  useEffect(() => {
    if (selectedTagId === null && !loadingTags) {
      setSelectedTagId(tags.length > 0 ? tags[0].id : UNTAGGED_ID);
    }
  }, [tags, loadingTags, selectedTagId]);
```

import 行改为 `import { useEffect, useState } from "react";`

- [ ] **Step 2: 运行前端测试**

Run: `cd frontend && npm test`
Expected: 全部通过（重点关注 `TagsPage.test.tsx` 的"默认选中第一个标签并加载视频"）

---

### Task 10: 仓库卫生（移除误提交文件）

**Files:**
- Delete: `alembic.ini`、`chrome-win64.zip`
- Modify: `.gitignore`

- [ ] **Step 1: 从 git 移除文件**

Run: `git rm alembic.ini chrome-win64.zip`
Expected: 两文件被删除并加入暂存（不 commit，由用户统一提交）

- [ ] **Step 2: 更新 .gitignore**

`.gitignore` 的"运行日志"段下方追加：

```gitignore
# 二进制压缩包
*.zip
```

- [ ] **Step 3: 确认 logs 仍在 git 中（D1 不动作）**

Run: `git ls-files logs/`
Expected: 仍列出 `logs/*.log`（确认未被误删）

---

### Task 11: JsonRepo 并发写测试

**Files:**
- Test: `tests/test_repo.py`（新建）

**Interfaces:**
- Consumes: `JsonRepo[T]`（`app/store/repo.py`）
- Produces: 无（纯测试补强）

- [ ] **Step 1: 新建 tests/test_repo.py**

```python
"""JsonRepo 存储层测试。"""
import asyncio

from app.models.tag import Tag
from app.store.repo import JsonRepo


async def test_concurrent_adds_have_unique_ids(tmp_path):
    """并发 add 不产生重复 id、不丢数据（写路径有 asyncio.Lock 保护）。"""
    repo = JsonRepo[Tag](Tag, tmp_path / "tags.json")
    await asyncio.gather(*(repo.add(Tag(name=f"tag{i}")) for i in range(50)))
    tags = repo.all()
    assert len(tags) == 50
    assert len({t.id for t in tags}) == 50


async def test_get_and_filter(tmp_path):
    repo = JsonRepo[Tag](Tag, tmp_path / "tags.json")
    await repo.add(Tag(name="a"))
    await repo.add(Tag(name="b"))
    assert repo.get(1).name == "a"
    assert repo.get(999) is None
    assert [t.name for t in repo.filter(name="b")] == ["b"]


async def test_update_and_delete(tmp_path):
    repo = JsonRepo[Tag](Tag, tmp_path / "tags.json")
    await repo.add(Tag(name="a"))
    updated = await repo.update(1, name="a2")
    assert updated is not None and updated.name == "a2"
    assert await repo.update(999, name="x") is None
    assert await repo.delete(1) is True
    assert await repo.delete(1) is False
    assert repo.all() == []
```

- [ ] **Step 2: 运行测试**

Run: `uv run pytest tests/test_repo.py -v`
Expected: 3 passed

---

### Task 12: 重写 README.md

**Files:**
- Modify: `README.md`（全量重写）

- [ ] **Step 1: 全量替换 README.md**

````markdown
# Bilibili Tag Group

一个完全本地运行的 B 站订阅管理工具：手动维护 UP 主列表，用标签给 UP 主分组，按标签浏览未看视频，并在本地记录观看状态与同步日志。

## 功能概述

- **标签视图**：按标签分组展示 UP 主的未看视频，支持逐条/批量标记已看、不看
- **UP 主管理**：单个/批量添加 UP 主，编辑名称、别名、标签、启用状态，查看每个 UP 主的视频列表
- **视频同步**：定时 + 手动从 B 站抓取 UP 主公开视频，异步后台执行，前端轮询进度
- **观看状态**：本地记录每条视频的未看/已看/不看状态
- **立即同步标签**：将标签设为"立即同步"后，其下 UP 主使用更短的同步间隔

## 技术栈

- **后端**：FastAPI + Pydantic v2 + JSON 文件存储 + Playwright
- **前端**：Vite + React + TypeScript + Lucide Icons
- **部署**：完全本地运行，无需外部服务

## 快速开始

### 后端

```bash
# 安装依赖（需要 uv）
uv sync --extra dev

# 首次使用安装 Playwright 浏览器
uv run playwright install chromium

# 启动 API（首次启动自动创建数据目录与 logs/）
uv run uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend && npm install
cd frontend && npm run dev
```

开发环境下前端 `/api` 请求由 Vite 代理到 `http://localhost:8000`，需先启动后端。

### Windows 一键启停

`start.bat` / `stop.bat`（内部调用 `start.ps1` / `stop.ps1`）用于 Windows 环境一键启停前后端，PID 写入 `logs/*.pid`。

## 数据与日志

- 数据以 JSON 文件存储在 `../private-data/bilibili-tag-group/`（可用 `DATA_DIR` 环境变量覆盖），用户自行在该目录用 git 管理数据版本
- 时间字段统一使用 naive UTC 存储，API 响应序列化为北京时间
- **`logs/*.log` 有意纳入本仓库 git 管理**：作为系统的有效运行日志，便于跨机器排查问题；`logs/*.pid` 不入库

## API 接口

### UP 主

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/creators` | UP 主列表（含未看数等统计） |
| POST | `/api/creators` | 添加 UP 主（可关联标签） |
| POST | `/api/creators/batch` | 批量添加（按 uid，自动抓取昵称头像、按名建标签） |
| GET | `/api/creators/resolve-name` | 根据空间 URL 抓取昵称和头像 |
| GET | `/api/creators/{id}` | 单个 UP 主详情 |
| PATCH | `/api/creators/{id}` | 编辑 UP 主（名称/别名/enabled/标签） |
| GET | `/api/creators/{id}/videos` | 该 UP 主的视频列表（含观看状态） |
| PATCH | `/api/creators/{id}/videos/status` | 将该 UP 主所有未看视频批量置为指定状态 |

### 标签

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tags` | 标签列表 |
| POST | `/api/tags` | 创建标签 |
| GET | `/api/tags/{id}/videos` | 该标签下 UP 主的未看视频 |
| GET | `/api/tags/untagged/videos` | 无标签 UP 主的未看视频 |

### 视频

| 方法 | 路径 | 说明 |
|------|------|------|
| PATCH | `/api/videos/{id}/status` | 更新观看状态（0=未看, 1=已看, 2=不看） |

### 同步

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sync/latest` | 最近一次全量同步任务 |
| POST | `/api/sync/run` | 手动触发全量同步（幂等：运行中则返回现有任务） |
| GET | `/api/sync/task/current` | 当前（或最近一次）任务进度（前端每 3 秒轮询） |
| GET | `/api/sync/settings` | 定时同步调度配置 |
| GET | `/api/sync/immediate-tags` | 立即同步标签列表 |
| POST | `/api/sync/immediate-tags?tag_id=N` | 将标签设为立即同步 |
| DELETE | `/api/sync/immediate-tags/{tag_id}` | 取消标签的立即同步 |

## 核心数据模型

- **Creator**：UP 主（名称、别名、空间 URL、头像、enabled、最近同步时间）
- **Tag**：标签（挂在 UP 主上，不挂在视频上）
- **CreatorTag**：UP 主与标签的多对多关联
- **Video**：视频（bvid、标题、发布时间、时长、封面）
- **VideoStatus**：观看状态（video_id、状态、标记时间）
- **SyncTask**：全量同步任务（进度、当前 UP 主、心跳、错误信息）
- **TagSyncConfig**：立即同步标签配置

## 同步行为

- 定时同步由 asyncio 调度循环按 `SYNC_INTERVAL_MINUTES`（默认 60 分钟）触发；`POST /api/sync/run` 手动触发，二者共用同一入口且幂等（运行中不重复启动）
- 单个 UP 主的抓取频率由 `last_synced_at` 控制：普通 UP 主约 50 分钟内不重复抓取，立即同步标签下的 UP 主约 5 分钟
- `enabled=false` 的 UP 主不参与同步
- 抓取层有内存缓存（视频 1 小时、昵称 24 小时）

## 运行测试

```bash
# 后端（默认跳过需要真实网络的集成测试）
uv run pytest

# 后端集成测试（真实浏览器 + 真实 B 站接口）
uv run pytest -m integration

# 前端
cd frontend && npm test
```

## 配置

通过 `.env` 或环境变量（见 `app/config.py`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | `../private-data/bilibili-tag-group/` | JSON 数据目录 |
| `SYNC_INTERVAL_MINUTES` | `60` | 定时同步间隔（分钟） |
| `BILIBILI_COOKIE` | （空） | B 站登录 Cookie，提高反爬成功率 |

## 目录结构

```
.
├── app/                       # 后端应用（详见 app/README.md）
├── frontend/                  # 前端应用
│   ├── src/
│   │   ├── App.tsx            # 路由（/ → /tags、/creators、/creators/:id、/sync）
│   │   ├── api/client.ts      # API 请求封装与类型
│   │   ├── components/        # VideoCard、CreatorForm、BatchImportModal 等
│   │   ├── hooks/             # useTags、useSync
│   │   └── pages/             # TagsPage、CreatorsPage、CreatorDetailPage、SyncPage
│   └── tests/                 # vitest 测试
├── tests/                     # 后端 pytest
├── docs/                      # 需求与设计文档
├── logs/                      # 运行日志（有意入库，见上文）
├── start.ps1 / stop.ps1       # Windows 启停脚本
├── start.bat / stop.bat       # Windows 启停入口
├── pyproject.toml             # Python 项目配置（uv）
└── uv.lock
```
````

- [ ] **Step 2: 自查**

逐项核对：无 SQLAlchemy/Alembic/SQLite/APScheduler 字样；API 表与 `app/routers/` 实际端点一致；目录结构与实际文件一致。

---

### Task 13: 更新 app/README.md、CLAUDE.md、docs/docs.md

**Files:**
- Modify: `app/README.md`
- Modify: `CLAUDE.md`
- Modify: `docs/docs.md`

- [ ] **Step 1: 更新 app/README.md**

改动点（其余保留）：
- 目录结构：新增 `utils/time.py`、`logging_config.py`、`schemas/sync.py`、`store/` 已有；确认 routers/services 描述与新职责一致（路由只做参数解析与错误映射）
- "抓取器"一节：`window.__INITIAL_STATE__` 描述替换为——通过 Playwright 无头浏览器打开 UP 主空间投稿页，从 DOM 视频卡片逐页提取数据，绕过 WBI 签名风控；带内存缓存（视频 1h、昵称 24h）
- API 端点表：补齐 `POST /api/creators/batch`、`GET /api/creators/{id}`、`GET /api/creators/{id}/videos`、`PATCH /api/creators/{id}/videos/status`、`GET /api/tags/untagged/videos`、immediate-tags 三个端点；`PATCH /api/videos/{id}/status` 保留
- "启动"一节命令改为 `uv sync --extra dev` / `uv run uvicorn app.main:app --reload`

- [ ] **Step 2: 更新 CLAUDE.md**

改动点：
- 常用命令（后端）：替换为 `uv sync --extra dev`、`uv run uvicorn app.main:app --reload`、`uv run pytest --tb=short`、`uv run pytest tests/test_routers.py -v`；补一行集成测试 `uv run pytest -m integration`
- 联调顺序："首次启动会自动创建 `data/` 目录"改为"首次启动会自动创建数据目录（默认 `../private-data/bilibili-tag-group/`）与 `logs/`"
- 架构概览："数据存储在 `data/` 目录下的 JSON 文件中（`creators.json`…），纳入 git 版本管理"改为"数据以 JSON 文件存储在 `../private-data/bilibili-tag-group/`（`creators.json` 等），由用户自行用 git 管理版本；`logs/*.log` 有意纳入本仓库 git，用于跨机器排查问题"
- 项目约束："运行测试和脚本时优先使用仓库内 `.venv`…"改为"使用 uv 管理依赖，运行测试和脚本统一用 `uv run` 前缀"
- 其余（页面约定、抓取链路、naive UTC）保留

- [ ] **Step 3: 标注 docs/docs.md**

文件顶部（`# 需求` 之前）插入：

```markdown
> 本文档为项目原始需求草稿，留存作为背景参考。功能现状以 `README.md` 与代码为准。

```

- [ ] **Step 4: 自查**

Grep 确认：`grep -rn "SQLAlchemy\|Alembic\|alembic\|SQLite\|APScheduler\|my_bilibili.db" README.md app/README.md CLAUDE.md` 无输出（`docs/docs.md` 等历史文档除外）。

---

### Task 14: 全量验证与 ruff 清理

**Files:**
- Modify: 视 ruff 报告而定（仅修确定安全的项：import 排序、未使用 import、类型标注现代化）

- [ ] **Step 1: ruff 自动修复安全项**

Run: `uv run ruff check app tests --fix`
Expected: import 排序等自动修复；剩余问题逐条人工判断（不确定的一律不改）

- [ ] **Step 2: 后端全量测试**

Run: `uv run pytest --tb=short -q`
Expected: 全部通过，2 deselected

- [ ] **Step 3: 前端测试与构建**

Run: `cd frontend && npm test && npm run build`
Expected: 测试全过，构建成功

- [ ] **Step 4: 手动冒烟**

启动 `uv run uvicorn app.main:app --reload` 与 `cd frontend && npm run dev`，依次打开 `/tags`、`/creators`、`/sync`：
- /tags：标签列表加载，切换标签视频列表刷新
- /creators：UP 主列表统计正常，点进详情视频列表正常
- /sync：最近同步时间显示为北京时间（不是少 8 小时的 UTC），点"立即同步"进度条推进

- [ ] **Step 5: 汇总改动清单交给用户提交**

Run: `git status && git diff --stat`
输出改动摘要，提示用户审查后自行 commit。

---

## Self-Review 记录

- **Spec 覆盖**：阶段 1→Task 1；阶段 2→Task 2/3/5(await)/6（重复触发）/7；阶段 3→Task 4/5/6/8；阶段 4→Task 9/10；阶段 5→Task 3/5/6/7 回归测试 + Task 11；阶段 6→Task 12/13。D1-D4 约束分布在 Global Constraints 与 Task 10/12/13
- **Placeholder 扫描**：无 TBD/TODO；所有代码步骤含完整代码
- **类型一致性**：`start_sync -> tuple[SyncTask, bool]`、`run_sync_task(task_id, store)`、`to_read(store, creator)`、`batch_create(store, fetcher, items)`、`init_app(store, fetcher, sync_service)` 在 Task 4/5/6 间一致；conftest 的 `mock_fetcher` fixture 在 Task 4 定义、Task 5 使用
- **D4 边界复核**：Task 7 只加跳过分支；`sync_creator` 的 TTL/抓取流程无改动；`_any_known`、fetcher 缓存未触碰
