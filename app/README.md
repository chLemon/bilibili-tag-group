# app — B 站订阅管理后端

基于 FastAPI + Pydantic + JSON 文件存储的 B 站 UP 主订阅管理后端，提供 UP 主管理、标签分组、视频同步与观看状态追踪功能。

## 目录结构

```
app/
├── main.py                  # FastAPI 应用入口，lifespan 管理调度器
├── config.py                # 配置：读项目根 config.json，暴露 settings
├── dependencies.py          # FastAPI 依赖注入（get_store / get_fetcher / get_sync_service）
├── logging_config.py        # 日志配置：输出到 stderr，由 manage.py 重定向到 logs/backend.log
├── scheduler.py             # asyncio 定时同步调度器
├── domains/                 # 按领域组织的业务层（model + schema + service 合一）
│   ├── creators/            #   UP 主领域
│   │   ├── models.py        #     Creator + CreatorTag
│   │   ├── schemas.py       #     CreatorCreate / CreatorRead / Batch*
│   │   └── service.py       #     CreatorService
│   ├── tags/                #   标签领域
│   │   ├── models.py        #     Tag + TagSyncConfig
│   │   ├── schemas.py       #     TagCreate / TagRead
│   │   └── service.py       #     TagService
│   ├── videos/              #   视频领域
│   │   ├── models.py        #     Video + VideoStatus
│   │   ├── schemas.py       #     VideoRead / VideoDetail / VideoStatusUpdate
│   │   └── service.py       #     VideoService
│   └── sync/                #   同步领域
│       ├── models.py        #     SyncTask
│       ├── schemas.py       #     SyncTaskRead（含 BeijingDateTime）
│       └── service.py       #     SyncService：全量/单 UP 主同步、心跳、TTL 节流、全局互斥
├── shared/                  # 跨领域共享的基础设施
│   ├── repo.py              #   JsonRepo[T] 泛型仓库
│   ├── store.py             #   DataStore 聚合所有 repo
│   └── time.py              #   now_utc() + BeijingDateTime：naive UTC 时间约定 + 北京时间序列化
├── routers/                 # HTTP 路由：只做参数解析与错误映射
│   ├── creators.py          #   /api/creators — UP 主管理端点
│   ├── tags.py              #   /api/tags — 标签列表与标签下未看视频
│   ├── videos.py            #   /api/videos — 视频状态更新
│   └── sync.py              #   /api/sync — 同步触发、任务查询、立即同步标签管理
└── fetcher/                 # B 站数据抓取层（已冻结，勿擅动）
    ├── models.py            #   FetchedVideo dataclass
    └── playwright_fetcher.py #  基于 Playwright 无头浏览器的抓取器
```

## 数据存储

所有数据以 JSON 文件存储在 `../private-data/bilibili-tag-group/` 目录下，用户自行在该目录用 git 管理数据版本：

```
private-data/bilibili-tag-group/
  creators.json
  tags.json
  creator_tags.json
  videos.json
  video_statuses.json
  sync_tasks.json
  tag_sync_configs.json
```

每个文件对应一个 `JsonRepo[T]`（`app/shared/repo.py`）实例，由 `DataStore`（`app/shared/store.py`）聚合，提供按需 IO 读写。写操作使用 `asyncio.Lock` 保护并发安全。

## 数据模型关系

```
Creator ──many-to-many── Tag    （通过 CreatorTag 记录手动关联）
Creator ──one-to-many─── Video  （通过 Video.creator_id 关联）
Video   ──one-to-one──── VideoStatus（通过 VideoStatus.video_id 关联）
SyncTask（scope="all" 全量 / scope="creator" 单 UP 主，含进度追踪与探活心跳）
```

- **标签挂在 UP 主上**，不挂在视频上
- 标签页展示的是"该标签下所有 UP 主的未看视频"
- 时间字段统一使用 naive UTC

## API 端点概览

请求/响应字段的详细说明见 [../docs/api.md](../docs/api.md)。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/creators` | 添加 UP 主 |
| `POST` | `/api/creators/batch` | 批量添加 UP 主 |
| `GET` | `/api/creators` | UP 主列表 |
| `GET` | `/api/creators/resolve-name` | 根据 URL 获取昵称 |
| `GET` | `/api/creators/{id}` | 获取单个 UP 主详情 |
| `PATCH` | `/api/creators/{id}` | 编辑 UP 主 |
| `DELETE` | `/api/creators/{id}` | 删除 UP 主（级联删除标签关联、视频与观看状态） |
| `GET` | `/api/creators/{id}/videos` | 指定 UP 主的所有视频（含已看状态） |
| `PATCH` | `/api/creators/{id}/videos/status` | 批量标记该 UP 主所有未看视频的状态 |
| `POST` | `/api/tags` | 创建标签 |
| `GET` | `/api/tags` | 标签列表 |
| `GET` | `/api/tags/untagged/videos` | 所有无标签 UP 主的未看视频 |
| `GET` | `/api/tags/{id}/videos` | 指定标签下所有 UP 主的未看视频 |
| `PATCH` | `/api/videos/{id}/status` | 标记单个视频已看/未看/不看 |
| `GET` | `/api/sync/latest` | 最近同步任务（默认 3 条，上限 20，含全量与单 UP 主） |
| `POST` | `/api/sync/run` | 手动全量同步 |
| `POST` | `/api/sync/creators/{creator_id}` | 手动同步单个 UP 主（绕过 TTL 节流） |
| `GET` | `/api/sync/task/current` | 当前同步任务进度 |
| `GET` | `/api/sync/settings` | 定时同步配置 |
| `GET` | `/api/sync/immediate-tags` | 查询所有"立即同步"标签 |
| `POST` | `/api/sync/immediate-tags` | 将标签设为"立即同步"模式 |
| `DELETE` | `/api/sync/immediate-tags/{tag_id}` | 从"立即同步"中移除标签 |

## 配置

根目录 `config.json` 是前后端共享的唯一配置源（入 git）：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `backend_host` | `127.0.0.1` | 后端监听地址 |
| `backend_port` | `3333` | 后端端口 |
| `frontend_port` | `2222` | 前端开发服务器端口 |
| `sync_interval_minutes` | `60` | 定时同步间隔（分钟） |

`data_dir` 默认 `../private-data/bilibili-tag-group/`，在 `app/config.py` 里推导，不放 `config.json`。`config.json` 缺失或非法时用代码默认值兜底。

## 启动

```bash
# 安装依赖
uv sync --extra dev

# 启动 API（首次启动自动创建数据目录与 logs/）
uv run uvicorn app.main:app --reload
```

## 抓取器

使用 **`PlaywrightBilibiliFetcher`** — 通过 Playwright 无头浏览器打开 UP 主空间投稿页，从 DOM 视频卡片逐页提取数据，绕过 WBI 签名风控。

抓取层是校准过的冻结基准，完整行为描述见 [../docs/fetcher.md](../docs/fetcher.md)。
