# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 文档与注释

- 本项目的文档、说明、代码注释尽量使用中文。
- 命令、配置键、库名、协议名等技术标识保持原文。

## 常用命令

## 后端

- 安装依赖：`uv sync --extra dev`
- 启动 API：`uv run uvicorn app.main:app --reload`
- 运行后端测试：`uv run pytest --tb=short`
- 运行单个后端测试文件：`uv run pytest tests/test_routers.py -v`
- 运行集成测试：`uv run pytest -m integration`

## 前端

- 安装依赖：`cd frontend && npm install`
- 启动开发服务器：`cd frontend && npm run dev`
- 构建前端：`cd frontend && npm run build`
- 本地预览构建结果：`cd frontend && npm run preview`
- 运行前端测试：`cd frontend && npm test`
- 运行单个前端测试文件：`cd frontend && npx vitest run tests/SyncPage.test.tsx`

## 联调顺序

- 直接启动后端 API：`uv run uvicorn app.main:app --reload`（首次启动会自动创建数据目录（默认 `../private-data/bilibili-tag-group/`）与 `logs/`）
- 再启动前端开发服务器：`cd frontend && npm run dev`
- 前端开发环境依赖 `frontend/vite.config.ts` 的 `/api` 代理到 `http://localhost:8000`，后端未启动时前端请求会失败

## 架构概览

- 这是一个完全本地运行的 B 站订阅管理 MVP：手动维护 UP 主，用标签给 UP 主分组，在本地页面查看各标签下的未看视频，并在本地记录已看状态与同步日志。
- 后端是 FastAPI + Pydantic + JSON 文件存储。应用入口在 `app/main.py`，通过 lifespan 启动 asyncio 定时同步任务；HTTP 路由分布在 `app/routers/creators.py`、`app/routers/tags.py`、`app/routers/videos.py`、`app/routers/sync.py`。
- 数据以 JSON 文件存储在 `../private-data/bilibili-tag-group/`（`creators.json` 等），由用户自行用 git 管理版本；`logs/*.log` 有意纳入本仓库 git，用于跨机器排查问题。模型使用 Pydantic v2 BaseModel，通过 `app/store/repo.py` 的 `JsonRepo[T]` 泛型仓库进行读写。
- 数据模型核心是 `Creator`、`Tag`、`CreatorTag`、`Video`、`VideoStatus`、`SyncTask`。标签挂在 UP 主上，不挂在视频上；标签页展示的是”属于该标签下 UP 主的未看视频”。
- 抓取链路是 `app/fetcher/playwright_fetcher.py` → `app/services/sync_service.py`：抓取 B 站公开视频、写入本地 `Video`，并为新视频创建默认 `watched=False` 的 `VideoStatus`；全量同步结果写入 `SyncTask`。
- 前端是 Vite + React + TypeScript。根路由在 `frontend/src/App.tsx`，只有三个页面：`/tags`、`/creators`、`/sync`，访问 `/` 会直接跳转到 `/tags`。
- 前端 API 封装在 `frontend/src/api/client.ts`，直接复用后端 `snake_case` 字段；开发环境下由 `frontend/vite.config.ts` 将 `/api` 代理到 `http://localhost:8000`。

## 项目约束与注意事项

- 所有个人管理数据都必须本地化：观看状态、标签关系、同步日志都以 JSON 文件存储在 `../private-data/bilibili-tag-group/`（见下条），不依赖 B 站账号状态。
- 第一版不做首页、不做笔记功能，只保留标签视图、UP 主管理、同步状态三个页面。
- 后端声明 `requires-python = ">=3.12"`。使用 uv 管理依赖，运行测试和脚本统一用 `uv run` 前缀。
- `app/config.py` 中 `data_dir` 默认指向项目根目录外的 `../private-data/bilibili-tag-group/`，用户自行在该目录下用 git 管理数据版本。
- 时间字段统一使用 naive UTC；不要再引入 `datetime.utcnow()`。
- `app/fetcher/` 与 `sync_creator` 的抓取逻辑是用户校准过的冻结基准，不要擅动；改动前先读 `docs/fetcher.md`（行为基准）与 `docs/fetcher-review.md`（疑点与待确认建议），并与用户确认。
