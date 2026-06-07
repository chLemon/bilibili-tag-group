# Bilibili Tag Group

一个完全本地运行的 B 站订阅管理工具，用于管理关注的 UP 主、用标签分组、查看各标签下的未看视频，并在本地记录已看状态与同步日志。

## 功能概述

- **标签管理**：创建标签，为 UP 主分配标签，按标签浏览未看视频
- **UP 主管理**：手动添加/编辑/删除 UP 主信息
- **视频同步**：定时从 B 站抓取 UP 主的公开视频，自动记录新视频
- **观看状态**：本地记录每条视频的已看/未看状态
- **同步日志**：记录每次同步操作的结果

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite + Alembic + APScheduler
- **前端**：Vite + React + TypeScript
- **部署**：完全本地运行，无需外部服务

## 快速开始

### 后端

```bash
# 安装依赖
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 执行数据库迁移
.venv/bin/alembic upgrade head

# 启动 API
.venv/bin/uvicorn app.main:app --reload
```

### 前端

```bash
# 安装依赖
cd frontend && npm install

# 启动开发服务器
cd frontend && npm run dev
```

开发环境下，前端 `/api` 请求会自动代理到 `http://localhost:8000`。

## 目录结构

```
.
├── app/                          # 后端应用
│   ├── main.py                   # FastAPI 入口，lifespan 启动 APScheduler
│   ├── config.py                 # 配置（数据库 URL 等）
│   ├── database.py               # SQLAlchemy 数据库会话
│   ├── dependencies.py           # FastAPI 依赖注入
│   ├── scheduler.py              # APScheduler 定时任务调度
│   ├── fetcher/                  # B 站视频抓取
│   │   ├── bilibili_fetcher.py   # 抓取 B 站公开视频 API
│   │   └── models.py             # 抓取数据模型
│   ├── models/                   # SQLAlchemy ORM 模型
│   │   ├── creator.py            # UP 主
│   │   ├── tag.py                # 标签
│   │   ├── creator_tag.py        # UP 主-标签关联
│   │   ├── video.py              # 视频
│   │   ├── video_status.py       # 视频观看状态
│   │   └── sync_log.py           # 同步日志
│   ├── routers/                  # API 路由
│   │   ├── creators.py           # UP 主相关接口
│   │   ├── tags.py               # 标签相关接口
│   │   ├── videos.py             # 视频相关接口
│   │   └── sync.py               # 同步相关接口
│   ├── schemas/                  # Pydantic 数据模型
│   │   ├── creator.py
│   │   ├── tag.py
│   │   ├── video.py
│   │   └── sync.py
│   └── services/                 # 业务逻辑层
│       ├── creator_service.py
│       ├── tag_service.py
│       ├── video_service.py
│       └── sync_service.py
├── frontend/                     # 前端应用
│   ├── src/
│   │   ├── App.tsx               # 路由配置（/tags、/creators、/sync）
│   │   ├── main.tsx              # React 入口
│   │   ├── api/client.ts         # API 请求封装
│   │   ├── components/           # 通用组件
│   │   │   ├── CreatorForm.tsx
│   │   │   ├── SyncStatusPanel.tsx
│   │   │   └── VideoCard.tsx
│   │   └── pages/                # 页面组件
│   │       ├── TagsPage.tsx      # 标签视图
│   │       ├── CreatorsPage.tsx  # UP 主管理
│   │       └── SyncPage.tsx      # 同步状态
│   ├── tests/                    # 前端测试
│   ├── vite.config.ts            # Vite 配置（含 /api 代理）
│   └── package.json
├── alembic/                      # 数据库迁移
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/                        # 后端测试
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_routers.py
│   ├── test_services.py
│   ├── test_fetcher.py
│   └── test_scheduler.py
├── docs/                         # 项目文档
├── pyproject.toml                # Python 项目配置
├── alembic.ini                   # Alembic 配置
├── my_bilibili.db                # SQLite 数据库文件
└── CLAUDE.md                     # Claude Code 辅助文档
```

## 核心数据模型

- **Creator**：UP 主信息（B 站 UID、名称、头像）
- **Tag**：标签（用于对 UP 主分组）
- **CreatorTag**：UP 主与标签的多对多关联
- **Video**：视频信息（标题、封面、发布时间等）
- **VideoStatus**：视频观看状态（已看/未看）
- **SyncLog**：同步操作日志

## 运行测试

```bash
# 后端测试
.venv/bin/pytest --tb=short

# 前端测试
cd frontend && npm test
```

## 注意事项

- 所有数据完全本地化，不依赖 B 站账号登录状态
- 首页、笔记功能暂不实现，只保留标签视图、UP 主管理、同步状态三个页面
- 时间字段统一使用 naive UTC
