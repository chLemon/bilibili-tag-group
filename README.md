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
