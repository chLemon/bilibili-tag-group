# Bilibili Tag Group

一个完全本地运行的 B 站订阅管理工具，用于管理关注的 UP 主、用标签分组、查看各标签下的未看视频，并在本地记录已看状态与同步日志。

## 功能概述

- **标签管理**：创建标签，为 UP 主分配标签，按标签浏览未看视频
- **UP 主管理**：手动添加/编辑/删除 UP 主信息
- **视频同步**：定时/手动从 B 站抓取 UP 主的公开视频，自动记录新视频
- **观看状态**：本地记录每条视频的已看/未看状态
- **同步进度**：异步后台同步，前端实时轮询进度条

## 技术栈

- **后端**：FastAPI + SQLAlchemy + SQLite + Alembic + APScheduler + Playwright
- **前端**：Vite + React + TypeScript + Lucide Icons
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

## API 接口

### 标签页 (`/tags`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tags` | 获取所有标签列表 |
| POST | `/api/tags` | 创建新标签 |
| GET | `/api/tags/{tag_id}/videos` | 获取某标签下所有未看视频 |

### UP 主管理页 (`/creators`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/creators` | 获取所有 UP 主列表 |
| POST | `/api/creators` | 添加新 UP 主 |
| PATCH | `/api/creators/{creator_id}` | 编辑 UP 主（名称/enabled/标签） |
| GET | `/api/creators/resolve-name` | 根据空间 URL 从 B 站获取昵称和头像 |
| POST | `/api/creators/{creator_id}/sync` | 手动同步单个 UP 主的视频 |

### 同步状态页 (`/sync`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sync/latest` | 查询最近一次全量同步日志 |
| POST | `/api/sync/run` | 触发异步全量同步，立即返回 SyncTask |
| GET | `/api/sync/task/current` | 轮询当前同步任务进度（前端每 3 秒调用） |
| GET | `/api/sync/settings` | 查询定时同步调度配置 |
| GET | `/api/sync/immediate-tags` | 查询所有"立即同步"标签 |
| POST | `/api/sync/immediate-tags?tag_id=N` | 将指定标签设为立即同步 |
| DELETE | `/api/sync/immediate-tags/{tag_id}` | 移除标签的立即同步模式 |

### 视频操作

| 方法 | 路径 | 说明 |
|------|------|------|
| PATCH | `/api/videos/{video_id}/watched` | 标记视频已看/未看 |

## 核心数据模型

- **Creator**：UP 主信息（名称、空间 URL、头像、最近同步时间）
- **Tag**：标签（用于对 UP 主分组）
- **CreatorTag**：UP 主与标签的多对多关联
- **Video**：视频信息（bvid、标题、发布时间、时长）
- **VideoStatus**：视频观看状态（已看/未看、标记时间）
- **SyncLog**：同步操作历史日志
- **SyncTask**：异步同步任务（进度追踪、探活心跳）
- **TagSyncConfig**：标签同步模式配置（TTL 缓存 / 立即同步）

## 同步模式

同步分为两种模式，通过标签区分：

- **TTL 模式**（默认）：视频数据缓存 1 小时，1 小时内命中缓存则跳过远程请求。适用于无标签或普通标签的 UP 主。
- **立即同步**：绕过 TTL 缓存，直接从 B 站抓取最新数据。在同步状态页将标签设为"立即同步"后，拥有该标签的 UP 主使用此模式。

## 目录结构

```
.
├── app/                            # 后端应用
│   ├── main.py                     # FastAPI 入口，lifespan 启动 APScheduler
│   ├── config.py                   # 配置（数据库 URL、B 站 Cookie 等）
│   ├── database.py                 # SQLAlchemy 引擎与会话（WAL 模式）
│   ├── dependencies.py             # FastAPI 依赖注入
│   ├── scheduler.py                # APScheduler 定时任务
│   ├── fetcher/                    # B 站视频抓取
│   │   ├── playwright_fetcher.py   # Playwright 无头浏览器抓取
│   │   └── models.py               # 抓取数据模型
│   ├── models/                     # SQLAlchemy ORM 模型
│   │   ├── creator.py              # UP 主
│   │   ├── tag.py                  # 标签
│   │   ├── creator_tag.py          # UP 主-标签关联
│   │   ├── video.py                # 视频
│   │   ├── video_status.py         # 视频观看状态
│   │   ├── sync_log.py             # 同步日志
│   │   ├── sync_task.py            # 异步同步任务
│   │   └── tag_sync_config.py      # 标签同步模式配置
│   ├── routers/                    # API 路由
│   │   ├── creators.py             # /api/creators
│   │   ├── tags.py                 # /api/tags
│   │   ├── videos.py               # /api/videos
│   │   └── sync.py                 # /api/sync
│   ├── schemas/                    # Pydantic Schema
│   │   ├── _datetime.py            # 北京时间序列化类型
│   │   ├── creator.py
│   │   ├── tag.py
│   │   ├── video.py
│   │   └── sync.py
│   └── services/                   # 业务逻辑层
│       ├── creator_service.py
│       ├── tag_service.py
│       ├── video_service.py
│       └── sync_service.py
├── frontend/                       # 前端应用
│   ├── src/
│   │   ├── App.tsx                 # 路由（/ → /tags、/creators、/sync）
│   │   ├── main.tsx                # React 入口
│   │   ├── api/client.ts           # API 请求封装
│   │   ├── styles/index.css        # 全局样式
│   │   ├── components/
│   │   │   ├── CreatorForm.tsx     # UP 主添加/编辑表单
│   │   │   ├── SyncStatusPanel.tsx # 同步状态面板
│   │   │   └── VideoCard.tsx       # 视频卡片
│   │   └── pages/
│   │       ├── TagsPage.tsx        # 标签视图
│   │       ├── CreatorsPage.tsx    # UP 主管理
│   │       └── SyncPage.tsx        # 同步状态
│   ├── tests/                      # 前端测试
│   ├── vite.config.ts              # Vite 配置（含 /api 代理）
│   └── package.json
├── alembic/                        # 数据库迁移
│   ├── env.py
│   └── versions/
│       └── *.py
├── tests/                          # 后端测试
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_routers.py
│   ├── test_services.py
│   ├── test_fetcher.py
│   └── test_scheduler.py
├── pyproject.toml                  # Python 项目配置
├── alembic.ini                     # Alembic 配置
├── my_bilibili.db                  # SQLite 数据库文件
└── CLAUDE.md                       # Claude Code 辅助文档
```

## 运行测试

```bash
# 后端测试
.venv/bin/pytest --tb=short

# 前端测试
cd frontend && npm test
```

## 注意事项

- 所有数据完全本地化，不依赖 B 站账号登录状态
- 时间字段统一使用 naive UTC，序列化时转为北京时间
- SQLite 使用 WAL 模式提升并发性能
- Playwright 浏览器实例使用线程本地存储，避免跨线程切换错误
