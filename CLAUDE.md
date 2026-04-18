# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 文档与注释

- 本项目的文档、说明、代码注释尽量使用中文。
- 命令、配置键、库名、协议名等技术标识保持原文。

## 常用命令

## 后端

- 安装依赖：`python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
- 执行数据库迁移：`.venv/bin/alembic upgrade head`
- 启动 API：`.venv/bin/uvicorn app.main:app --reload`
- 运行后端测试：`.venv/bin/pytest --tb=short`
- 运行单个后端测试文件：`.venv/bin/pytest tests/test_routers.py -v`

## 前端

- 安装依赖：`cd frontend && npm install`
- 启动开发服务器：`cd frontend && npm run dev`
- 构建前端：`cd frontend && npm run build`
- 本地预览构建结果：`cd frontend && npm run preview`
- 运行前端测试：`cd frontend && npm test`
- 运行单个前端测试文件：`cd frontend && npx vitest run tests/SyncPage.test.tsx`

## 联调顺序

- 首次启动先执行后端迁移：`.venv/bin/alembic upgrade head`
- 先启动后端 API：`.venv/bin/uvicorn app.main:app --reload`
- 再启动前端开发服务器：`cd frontend && npm run dev`
- 前端开发环境依赖 `frontend/vite.config.ts` 的 `/api` 代理到 `http://localhost:8000`，后端未启动时前端请求会失败

## 架构概览

- 这是一个完全本地运行的 B 站订阅管理 MVP：手动维护 UP 主，用标签给 UP 主分组，在本地页面查看各标签下的未看视频，并在本地记录已看状态与同步日志。
- 后端是 FastAPI + SQLAlchemy + SQLite。应用入口在 `app/main.py`，通过 lifespan 启动 APScheduler 定时任务；HTTP 路由分布在 `app/routers/creators.py`、`app/routers/tags.py`、`app/routers/videos.py`、`app/routers/sync.py`。
- 数据模型核心是 `Creator`、`Tag`、`CreatorTag`、`Video`、`VideoStatus`、`SyncLog`。标签挂在 UP 主上，不挂在视频上；标签页展示的是“属于该标签下 UP 主的未看视频”。
- 抓取链路是 `app/fetcher/bilibili_fetcher.py` → `app/services/sync_service.py`：抓取 B 站公开视频、写入本地 `Video`，并为新视频创建默认 `watched=False` 的 `VideoStatus`；全量同步结果写入 `SyncLog`。
- 前端是 Vite + React + TypeScript。根路由在 `frontend/src/App.tsx`，只有三个页面：`/tags`、`/creators`、`/sync`，访问 `/` 会直接跳转到 `/tags`。
- 前端 API 封装在 `frontend/src/api/client.ts`，直接复用后端 `snake_case` 字段；开发环境下由 `frontend/vite.config.ts` 将 `/api` 代理到 `http://localhost:8000`。

## 项目约束与注意事项

- 所有个人管理数据都必须本地化：观看状态、标签关系、同步日志都落本地数据库，不依赖 B 站账号状态。
- 第一版不做首页、不做笔记功能，只保留标签视图、UP 主管理、同步状态三个页面。
- 后端声明 `requires-python = ">=3.12"`。运行测试和脚本时优先使用仓库内 `.venv`，不要直接依赖 shell 里的 `pytest`，否则可能误用旧 Python 导致 `X | Y` 类型注解在导入期报错。
- `app/config.py` 中默认数据库是 `sqlite:///./my_bilibili.db`，本地开发前如果切换过环境变量，先确认 `database_url` 是否仍指向预期文件。
- 时间字段统一使用 naive UTC；不要再引入 `datetime.utcnow()`。
