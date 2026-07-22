# 工程化重构设计文档

日期：2026-07-22
状态：待用户复核

## 背景

项目从 SQLite + SQLAlchemy 迁移到 JSON 文件存储后，代码与文档中残留了大量不一致，且存在多个真实 bug。本次重构目标：修复所有已知 bug、消除重复逻辑、让仓库卫生与工具链达标、重写全部文档。数据兼容性保持：不改 `private-data/` 下 JSON 文件的结构与字段含义。

## 现状问题清单

### 确认的 bug

1. `routers/creators.py` 两处调用 `fetch_creator_info()` 漏 `await`（批量添加、`resolve-name` 端点实际不可用）
2. `VideoService.set_status` 用 `video_statuses.get(video_id)` 按状态表自身 id 查找，id 错位后"标记已看"失效或改错行；测试按 `VideoStatus.id` 传参，与路由 `/api/videos/{video_id}/status` 的语义矛盾
3. `POST /api/sync/run`：`start_async_sync` 返回已存在的 running 任务后，路由仍再开一个 `_run_async_sync` 协程，同一任务并发执行两遍；且路由调用私有方法
4. `SyncTask.started_at` 默认用本地时间 `datetime.now()`，违反 naive UTC 约定
5. `SyncTask` 序列化未走 `BeijingDateTime`，naive UTC 字符串被前端 `new Date()` 按本地时区解析，心跳死活判断与同步时间显示偏差 8 小时
6. `_parse_date` 可返回 None，但 `FetchedVideo.published_at` 声明为 `datetime`，遇到无法解析的日期会让整个 UP 主同步失败
7. `enabled=False` 的 UP 主照常参与全量同步（该字段无人检查）

### 工程化问题

9. `pyproject.toml` 依赖 `httpx2` 不存在（应为 `httpx`），全新环境测试无法运行；`test` extra 与 `dev` 重复且同样写错
10. ruff 声明了依赖但无任何配置
11. 全量同步存在 `sync_all` 与 `_run_async_sync` 两套实现，进度更新逻辑不一致
12. 三个 `PlaywrightBilibiliFetcher` 实例（main、sync 路由、creators 路由），各自启动浏览器、各自持有内存缓存
13. 业务逻辑泄漏到路由层：`_to_creator_read` 统计、batch 编排、immediate-tags CRUD
14. `test_fetcher.py` 是真实网络 + 真实浏览器集成测试，混在单元测试中默认执行（当前基线 2 failed）
15. `main.py` import 期即创建 logs 目录与 fetcher 实例（模块级副作用）

### 仓库卫生

17. `alembic.ini` 为 SQLite 时代残留（alembic 目录与 SQLAlchemy 均已删除）
18. 前端 `TagsPage` 在 render 期间调用 `setState`（反模式）

### 文档

19. `README.md` 严重过时：仍描述 SQLAlchemy/Alembic/SQLite/APScheduler、不存在的端点（`/api/creators/{id}/sync`、`/api/videos/{id}/watched`）、已删除的文件（`database.py`、`alembic/`、`my_bilibili.db`）
20. `app/README.md` 抓取原理描述过时（`window.__INITIAL_STATE__` → 实际为 DOM 抓取）
21. `CLAUDE.md` 数据目录描述（`data/` 纳入 git）与 `config.py`（`../private-data/`）矛盾；命令基于 `.venv` 但项目实际用 uv（有 `uv.lock`、无 `.venv`）

## 设计决策

### D1. logs 目录约定

`logs/*.log` **有意纳入 git 管理**：这些是系统的有效运行日志，用于跨机器排查问题。`.gitignore` 维持只排除 `logs/*.pid`。此约定写入 README。

### D2. Windows 启动脚本保留

`start.ps1` / `stop.ps1` / `start.bat` / `stop.bat` 保留，用于 Windows 环境一键启停前后端，README 中说明用途。`chrome-win64.zip` 确认为误提交，从 git 移除（`.gitignore` 增加 `*.zip`）。

### D3. 数据兼容

不改 JSON 文件结构与字段含义，`private-data/` 现有数据直接可用，无需迁移。

### D4. 抓取层冻结

`app/fetcher/`（Playwright 抓取、缓存 TTL、重试、翻页、早停）与 `sync_creator` 中获取 UP 主视频的逻辑是用户校准过的基准行为，**不作为重构对象**：不改选择器、延迟、缓存 TTL（1h/24h）、5min/50min 同步间隔、`_any_known` 等。本次仅修正其周边的类型标注（`FetchedVideo.published_at` 标为 `datetime | None` 以反映现实），防护逻辑放在 `sync_service` 侧。唯一允许的生命周期变动是"全应用共享一个 fetcher 实例"（见阶段 3），不改变任何抓取行为。

## 重构方案

### 阶段 1：依赖与测试基线

- `pyproject.toml`：`httpx2` → `httpx`；删除 `test` extra，只留 `dev`；补 `[tool.ruff]`（行宽 100，规则 E/F/I/UP）
- `test_fetcher.py` 两个真实网络测试标记 `@pytest.mark.integration`，注册 marker，默认 `-m "not integration"` 跳过
- 验证：`uv sync --extra dev && uv run pytest -m "not integration"` 全绿

### 阶段 2：后端 bug 修复

- 补两处 `await`（`resolve-name`、batch 添加）
- `VideoService.set_status` 改为 `filter(video_id=...)` 语义；修正测试传参
- `SyncTask.started_at` 默认改 naive UTC；`_now_utc()` 收敛到 `app/utils/time.py` 单一实现
- 同步跳过 `enabled=False` 的 UP 主
- `FetchedVideo.published_at` 类型标注改为 `datetime | None`（仅标注修正）；`sync_service` 侧跳过 `published_at` 为 None 的视频并记日志，不改动 fetcher 抓取逻辑
- 修复 sync 重复触发：`start_sync` 返回已有 running 任务时不再起新协程
- 每项修复配回归测试

### 阶段 3：架构整理

**统一 fetcher 与同步入口**
- 全应用单例 `PlaywrightBilibiliFetcher`，lifespan 创建、经依赖注入分发；删除路由模块级自建实例。纯生命周期收敛，不改动 fetcher 内部任何抓取/缓存行为（见 D4）
- 全量同步收敛为一套：`SyncService.start_sync(store) -> SyncTask`（幂等：已有 running 任务直接返回）+ 公开方法 `run_sync_task(task_id, store)`；调度器与手动触发共用。逐 UP 主抓取与 TTL 判断逻辑原样保留（D4），只统一任务编排
- `sync_all` 删除（其职责由 `run_sync_task` 承接）

**业务逻辑收回 service 层**
- `_to_creator_read` → `CreatorService.to_read(store, creator)`
- batch 编排 → `CreatorService.batch_create(store, items, fetcher)`
- immediate-tags CRUD → `SyncService`（或独立 `TagSyncConfigService`）
- 路由只做参数解析、调 service、错误映射（404/502）

**时区修复**
- 新增 `SyncTaskRead` schema，时间字段走 `BeijingDateTime`；sync 路由 response_model 统一替换

**模块副作用清理**
- 日志配置抽到 `app/logging_config.py`；目录创建、fetcher 实例化移入 lifespan

### 阶段 4：仓库卫生

- git 移除 `alembic.ini`、`chrome-win64.zip`；`.gitignore` 增加 `*.zip`（保留 logs、Windows 脚本，见 D1/D2）
- 前端修 `TagsPage` render 期 `setState`（改 `useEffect`）

### 阶段 5：测试补强

- 回归测试：`set_status` 按 video_id 语义、重复触发不起双协程、disabled UP 主被跳过、`resolve-name` 端点（mock fetcher）
- 新增 `tests/test_repo.py` 覆盖 `JsonRepo` 并发写
- 前端测试维持现状，保证通过

### 阶段 6：文档重写

- `README.md` 全面重写：技术栈、快速开始（uv）、API 表与实际路由逐一对齐（含 batch、immediate-tags、untagged）、目录结构、logs 入库约定（D1）、Windows 脚本说明（D2）
- `app/README.md`：更新抓取原理（DOM 抓取）、目录结构、API 表
- `CLAUDE.md`：修正数据目录描述、命令改 uv 风格、同步现状
- `docs/docs.md`：保留为原始需求草稿并明确标注

## 验证

每阶段完成后执行：

```bash
uv run pytest -m "not integration"
cd frontend && npm test
```

全部完成后手动启动前后端，冒烟三个页面（/tags、/creators、/sync）。

## 明确不做

- 不改 JSON 数据结构（D3）
- 不改动 `app/fetcher/` 的抓取、缓存、重试、翻页、早停行为，不改动 `sync_creator` 的 TTL 语义（D4）
- 不 rewrite git 历史
- 不重构前端整体架构（仅修 bug 与反模式）
- 不引入 CI（本地项目，ruff + pytest 手动执行即可）
