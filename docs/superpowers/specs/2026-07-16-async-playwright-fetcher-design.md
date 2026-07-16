# 将 PlaywrightBilibiliFetcher 改为异步

## 概述

将 `app/fetcher/playwright_fetcher.py` 从 Playwright 同步 API 迁移到异步 API，并连带改造调用链路（sync_service、调度层），实现全链路异步。

## 1. fetcher 层 — `app/fetcher/playwright_fetcher.py`

### 导入变更

- `from playwright.sync_api import Browser, BrowserContext, sync_playwright` → `from playwright.async_api import Browser, BrowserContext, async_playwright`
- 移除 `import threading`，新增 `import asyncio`

### 浏览器生命周期

- 移除 `_thread_local: threading.local` 类属性，浏览器实例改为实例变量：
  - `self._playwright` — Playwright 实例
  - `self._browser` — 浏览器实例
- `_get_browser()`：实例方法，改为 `async`，内部使用 `async_playwright().start()` 和 `await pw.chromium.launch()`
- `close_browser()`：实例方法，改为 `async`，`await self._browser.close()` 和 `await self._playwright.stop()`
- 移除 `@classmethod` 装饰器

### 浏览器上下文

- `_create_context()` → 改为 `async`，`await self._get_browser()`，`browser.new_context()` 改为 `await browser.new_context()`
- `context.add_cookies()` → `await context.add_cookies()`

### 公开方法

三个公开方法全部加 `async` 前缀，内部调用链同步改为 `await`：

```python
async def fetch_videos(self, uid: str, ttl_cache: bool = True) -> list[FetchedVideo]:
async def fetch_creator_info(self, uid: str, ttl_cache: bool = True) -> dict:
async def fetch_creator_name(self, uid: str, ttl_cache: bool = True) -> str:
```

### 页面交互

- `page.goto()` → `await page.goto()`
- `page.wait_for_selector()` → `await page.wait_for_selector()`
- `page.reload()` → `await page.reload()`
- `page.locator()` → `await page.locator()`
- `locator.text_content()` → `await locator.text_content()`
- `locator.get_attribute()` → `await locator.get_attribute()`
- `locator.first` → `await locator.first`
- `locator.nth()` → `await locator.nth()`
- `locator.count()` → `await locator.count()`
- `next_btn.click()` → `await next_btn.click()`
- `time.sleep()` → `await asyncio.sleep()`

### 缓存方法

`_get_cached()`, `_set_cache()`, `_any_known()` 保持同步（纯 SQLite 操作，不涉及 Playwright），`_cache_key()` 也不变。

### 模块级函数

`_parse_card()`, `_parse_date()`, `_parse_duration()` 保持同步（纯数据处理）。

### context/page 资源管理

当前使用 `try/finally` + `page.close()` / `context.close()` 手动管理。改为异步后，可用 `try/finally` + `await page.close()` / `await context.close()`，保持显式管理。

---

## 2. sync_service 层 — `app/services/sync_service.py`

### 方法签名变更

```python
async def sync_creator(self, db_session: Session, creator: Creator) -> int:
async def sync_all(self, db_session: Session) -> SyncLog:
```

内部：
- `self._fetcher.fetch_creator_info()` → `await self._fetcher.fetch_creator_info()`
- `self._fetcher.fetch_videos()` → `await self._fetcher.fetch_videos()`
- `_time.sleep(1)` → `await asyncio.sleep(1)`

### 后台同步重构

当前三个方法的关系：`start_async_sync()` → `_run_async_sync()`（线程）+ `_heartbeat_loop()`（独立心跳线程）

改为异步后：
- `start_async_sync()`：创建 SyncTask 后返回一个 `asyncio.Task`（由调用方在事件循环中 `create_task` 管理）
- `_run_async_sync()`：改为 `async` 函数，内部 `await asyncio.sleep()` 替代 `_time.sleep()`
- `_heartbeat_loop()`：改为 `async` 函数，用 `asyncio.sleep()` 循环更新 `heartbeat_at`，通过 `asyncio.Event` 控制停止

停止信号传递：`asyncio.Event` 替代 `threading.Event`，其他逻辑不变。

---

## 3. 调度层 — `app/scheduler.py` + `app/main.py`

### scheduler.py

移除 APScheduler 导入，提供简单的 asyncio 调度 loop：

```python
import asyncio

async def run_sync_loop(sync_service, session_factory, interval_minutes):
    """每隔 interval_minutes 分钟执行一次全量同步。"""
    while True:
        await asyncio.sleep(interval_minutes * 60)
        db = session_factory()
        try:
            await sync_service.sync_all(db)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
```

移除 `build_scheduler()` 和 `get_sync_job_info()`。

### main.py

- `lifespan`：`run_migrations()` 后创建 `_sync_loop_task = asyncio.create_task(run_sync_loop(...))`
- 关闭时：`_sync_loop_task.cancel()` + `await _fetcher.close_browser()`
- `set_scheduler_context()` 调用需要更新（改用自定义类型保存调度信息）
- 移除 `_make_sync_job` 闭包

---

## 4. 路由层 — `app/routers/sync.py`

### `POST /api/sync/run` 端点

改为 `async def`：

```python
@router.post("/run", response_model=SyncTaskRead)
async def run_sync(db: Annotated[Session, Depends(get_db)]) -> SyncTaskRead:
    task = _sync_svc.start_async_sync(db)
    # 在事件循环中启动后台同步协程
    asyncio.create_task(_sync_svc._run_async_sync(task.id, SessionLocal))
    return _to_sync_task_read(task)
```

`start_async_sync()` 本身只负责创建数据库记录（同步），协程启动由路由负责。

### `GET /api/sync/settings` 端点

移除 APScheduler 调用，改为返回模块级变量：

```python
@router.get("/settings", response_model=dict[str, Any])
def get_sync_settings() -> dict[str, Any]:
    return {
        "enabled": _sync_loop_running,
        "interval_minutes": _sync_interval_minutes,
        "job_id": "sync-all",
    }
```

`set_scheduler_context()` 替换为 `set_sync_context(loop_running: bool, interval_minutes: int)`。

### 其他端点

- `GET /api/sync/latest`、`GET /api/sync/task/current`：保持 `def`（同步，仅数据库查询）
- 立即同步标签 CRUD：保持 `def`（同步，仅数据库操作）

### 模块级 fetcher 实例

当前 `sync.py` 第20行自己创建了一个 `_sync_svc`，与 `main.py` 第53行的实例是独立的。这个重复是本项目已有的现状，不在本次改动范围内，保持不变。

---

## 5. 项目依赖变更

- 移除 `apscheduler` 依赖（`pyproject.toml` 和 `requirements.txt`）
- `playwright` 包不变（同步和异步 API 都在同一个包里）

---

## 6. 测试层 — `tests/test_fetcher.py`

- 所有对 fetcher 方法的调用改为 `await`
- mock 方式不变（仍通过 `unittest.mock.patch` mock fetcher 内部方法）
- 测试函数本身改为 `async def`

---

## 影响范围总结

| 文件 | 变更类型 |
|---|---|
| `app/fetcher/playwright_fetcher.py` | 重写：sync API → async API |
| `app/services/sync_service.py` | 改为 async 方法，线程模型替换为 asyncio |
| `app/scheduler.py` | 简化：移除 APScheduler，改用 asyncio 循环 |
| `app/main.py` | lifespan 中管理 asyncio task |
| `app/routers/sync.py` | 端点改为 async |
| `pyproject.toml` | 移除 apscheduler 依赖 |
| `tests/test_fetcher.py` | 测试函数改为 async |
