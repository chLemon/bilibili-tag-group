# Bilibili Tag Group

一个完全本地运行的 B 站订阅管理工具：手动维护 UP 主列表，用标签给 UP 主分组，按标签浏览未看视频，并在本地记录观看状态与同步日志。

## 功能概述

- **标签视图**：按标签分组展示 UP 主的未看视频，支持逐条/批量标记已看、不看
- **UP 主管理**：单个/批量添加 UP 主，编辑名称、别名、标签、启用状态，查看每个 UP 主的视频列表
- **视频同步**：定时 + 手动全量同步 + 手动单 UP 主同步，异步后台执行，前端轮询进度
- **观看状态**：本地记录每条视频的未看/已看/不看状态
- **立即同步标签**：将标签设为"立即同步"后，其下 UP 主使用更短的同步间隔

## 技术栈

- **后端**：FastAPI + Pydantic v2 + JSON 文件存储 + Playwright
- **前端**：Vite + React + TypeScript + Lucide Icons
- **部署**：完全本地运行，无需外部服务

## 快速开始

一键启停（推荐，跨平台）：

```bash
uv run python scripts/manage.py start    # 幂等启动前后端并打开主页（已运行则只开浏览器）
uv run python scripts/manage.py stop     # 停止服务并提交、推送 ../private-data 数据仓库
uv run python scripts/manage.py restart  # 先 stop 再 start
```

首次 `start` 会自动 `uv sync --extra dev` + `npm install` + `playwright install chromium`，之后只启动未运行的服务。Windows 可双击 `scripts/start.bat` / `scripts/stop.bat` / `scripts/restart.bat`，macOS 可用 `./scripts/start.sh` / `./scripts/stop.sh`（均为一行转发）。PID 写入 `logs/*.pid`。

`start` 默认会先 `git pull` 同步 `../private-data` 数据仓库；该仓库无 remote 时改用 `--no-pull` 跳过：

```bash
uv run python scripts/manage.py start --no-pull
```

清空本地数据（类似数据库 truncate，保留 `cookies.json`）：

```bash
./scripts/reset-data.sh        # macOS / Linux
scripts\\reset-data.bat         # Windows
```

### 手动启动（开发用）

```bash
# 后端（首次启动自动创建数据目录与 logs/）
uv sync --extra dev
uv run uvicorn app.main:app --reload

# 前端（另开终端）
cd frontend && npm install
cd frontend && npm run dev
```

开发环境下前端 `/api` 请求由 Vite 代理到 `http://localhost:3333`，需先启动后端。

### 启停行为说明

- `start` 按服务幂等：前后端分别用端口探测检查，只启动未运行的那个；都在运行则只打开浏览器
- 端口等待：后端 15 秒、前端 30 秒
- `stop` 按端口查 PID（`lsof` / `netstat`），先 SIGTERM 终止整棵进程树，5 秒未退出则 SIGKILL 强杀；kill 前打印 PID + 端口供用户确认
- `stop` 的备份前置条件：`../private-data` 需已 `git init` 并配置 remote；不满足则打印警告并跳过备份。备份失败（如 push 失败）只警告、不影响停止，退出码仍为 0
- 备份只提交 `bilibili-tag-group/*.json` 的变更，message 为 `backup: bilibili-tag-group data snapshot (<时间戳>)`
- Windows 端经过静态审查但未实机冒烟，如双击 `scripts/start.bat` 有问题请反馈

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
| DELETE | `/api/creators/{id}` | 删除 UP 主（级联删除标签关联、视频与观看状态） |
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
| GET | `/api/sync/latest?limit=N` | 最近 N 条同步任务（默认 3，上限 20，含全量与单 UP 主） |
| POST | `/api/sync/run` | 手动触发全量同步（幂等：运行中则返回现有任务） |
| POST | `/api/sync/creators/{creator_id}` | 手动同步单个 UP 主（绕过 TTL 节流，同 UP 主幂等） |
| GET | `/api/sync/task/current` | 当前（或最近一次）任务进度（前端每 3 秒轮询） |
| GET | `/api/sync/settings` | 定时同步调度配置 |
| GET | `/api/sync/immediate-tags` | 立即同步标签列表 |
| POST | `/api/sync/immediate-tags?tag_id=N` | 将标签设为立即同步 |
| DELETE | `/api/sync/immediate-tags/{tag_id}` | 取消标签的立即同步 |

全局只有一个同步任务能 running：全量与单 UP 主、单 UP 主之间互斥，冲突返回 409。

## 核心数据模型

- **Creator**：UP 主（名称、别名、空间 URL、头像、enabled、最近同步时间）
- **Tag**：标签（挂在 UP 主上，不挂在视频上）
- **CreatorTag**：UP 主与标签的多对多关联
- **Video**：视频（bvid、标题、发布时间、时长、封面）
- **VideoStatus**：观看状态（video_id、状态、标记时间）
- **SyncTask**：同步任务（`scope="all"` 全量 / `scope="creator"` 单 UP 主，进度、当前 UP 主、心跳、错误信息）
- **TagSyncConfig**：立即同步标签配置

## 同步行为

- 定时同步由 asyncio 调度循环按 `SYNC_INTERVAL_MINUTES`（默认 60 分钟）触发；`POST /api/sync/run` 手动触发，二者共用同一入口且幂等（运行中不重复启动）
- 单个 UP 主的抓取频率由 `last_synced_at` 控制：普通 UP 主约 50 分钟内不重复抓取，立即同步标签下的 UP 主约 5 分钟；`POST /api/sync/creators/{id}` 手动同步绕过节流（`force=True`）
- `enabled=false` 的 UP 主不参与同步
- B 站侧 `video_count=0` 的 UP 主跳过卡片抓取，避免无投稿触发 `FetchError`

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

根目录 `config.json` 是前后端共享的唯一配置源（入 git，改端口只动这一处）：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `backend_host` | `127.0.0.1` | 后端监听地址 |
| `backend_port` | `3333` | 后端端口 |
| `frontend_port` | `2222` | 前端开发服务器端口 |
| `sync_interval_minutes` | `60` | 定时同步间隔（分钟） |

`data_dir` 是 Python 专属路径，默认 `../private-data/bilibili-tag-group/`，不放 `config.json`，在 `app/config.py` 里推导。`config.json` 缺失或非法时用代码默认值兜底。

## 目录结构

```
.
├── app/                       # 后端应用（详见 app/README.md）
├── frontend/                  # 前端应用（详见 frontend/README.md）
│   ├── src/
│   │   ├── App.tsx            # 路由（/ → /tags、/creators、/creators/:id、/sync）
│   │   ├── api/client.ts      # API 请求封装与类型
│   │   ├── components/        # VideoCard、CreatorForm、BatchImportModal、ConfirmDialog、SyncLogCard 等
│   │   ├── hooks/             # useTags、useCreators、useCreatorDetail、useSync
│   │   └── pages/             # TagsPage、CreatorsPage、CreatorDetailPage、SyncPage
│   └── tests/                 # vitest 测试
├── tests/                     # 后端 pytest
├── docs/                      # 项目文档（见下方"文档索引"）
├── logs/                      # 运行日志（有意入库，见上文）
├── scripts/                   # 一键启停：manage.py（跨平台，纯标准库）+ bat/sh 入口 + reset-data 脚本
├── pyproject.toml             # Python 项目配置（uv）
└── uv.lock
```

## 文档索引

- [app/README.md](app/README.md) — 后端架构、目录结构、数据模型、端点概览
- [frontend/README.md](frontend/README.md) — 前端结构、路由、约定、测试
- [docs/requirements.md](docs/requirements.md) — 需求基准
- [docs/api.md](docs/api.md) — 全部接口的请求/响应字段详细说明
- [docs/fetcher.md](docs/fetcher.md) — 抓取层基准行为（已冻结，改动前必读）
- [docs/logging.md](docs/logging.md) — 日志文件与轮替策略
- [docs/dev/](docs/dev/) — 代码层面的设计说明（如 `scripts/README.md`）
