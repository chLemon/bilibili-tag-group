# app — B 站订阅管理后端

基于 FastAPI + Pydantic + JSON 文件存储的 B 站 UP 主订阅管理后端，提供 UP 主管理、标签分组、视频同步与观看状态追踪功能。

## 目录结构

```
app/
├── main.py                  # FastAPI 应用入口，lifespan 管理调度器
├── config.py                # 配置（数据目录、同步间隔、Cookie）
├── dependencies.py          # FastAPI 依赖注入（get_store / get_fetcher / get_sync_service）
├── logging_config.py        # 日志配置：文件（logs/app.log，滚动）+ 控制台双输出
├── scheduler.py             # asyncio 定时同步调度器
├── utils/
│   └── time.py              # now_utc()：统一 naive UTC 时间工具
├── models/                  # Pydantic 数据模型
│   ├── creator.py           #   UP 主
│   ├── tag.py               #   标签
│   ├── creator_tag.py       #   UP 主-标签多对多关联
│   ├── video.py             #   视频
│   ├── video_status.py      #   视频观看状态
│   ├── sync_task.py         #   同步任务
│   └── tag_sync_config.py   #   标签同步配置
├── store/                   # JSON 文件存储层
│   ├── repo.py              #   JsonRepo[T] 泛型仓库
│   └── store.py             #   DataStore 聚合所有 repo
├── schemas/                 # Pydantic 请求/响应 Schema
│   ├── _datetime.py         #   北京时间序列化类型
│   ├── creator.py           #   UP 主 schema
│   ├── tag.py               #   标签 schema
│   ├── video.py             #   视频 schema
│   └── sync.py              #   同步任务 schema（SyncTaskRead + BeijingDateTime）
├── routers/                 # HTTP 路由：只做参数解析与错误映射
│   ├── creators.py          #   /api/creators — UP 主管理端点
│   ├── tags.py              #   /api/tags — 标签列表与标签下未看视频
│   ├── videos.py            #   /api/videos — 视频状态更新
│   └── sync.py              #   /api/sync — 同步触发、任务查询、立即同步标签管理
├── services/                # 业务逻辑层
│   ├── creator_service.py   #   UP 主管理
│   ├── tag_service.py       #   标签与未看视频聚合查询
│   ├── video_service.py     #   视频观看状态管理
│   └── sync_service.py      #   同步核心：抓取 → 写入 JSON 文件
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

每个文件对应一个 `JsonRepo[T]` 实例，提供按需 IO 读写。写操作使用 `asyncio.Lock` 保护并发安全。

## 数据模型关系

```
Creator ──many-to-many── Tag    （通过 CreatorTag 记录手动关联）
Creator ──one-to-many─── Video  （通过 Video.creator_id 关联）
Video   ──one-to-one──── VideoStatus（通过 VideoStatus.video_id 关联）
SyncTask（scope="all" 的全量同步记录，含进度追踪与探活心跳）
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
| `GET` | `/api/creators/{id}/videos` | 指定 UP 主的所有视频（含已看状态） |
| `PATCH` | `/api/creators/{id}/videos/status` | 批量标记该 UP 主所有未看视频的状态 |
| `POST` | `/api/tags` | 创建标签 |
| `GET` | `/api/tags` | 标签列表 |
| `GET` | `/api/tags/untagged/videos` | 所有无标签 UP 主的未看视频 |
| `GET` | `/api/tags/{id}/videos` | 指定标签下所有 UP 主的未看视频 |
| `PATCH` | `/api/videos/{id}/status` | 标记单个视频已看/未看/不看 |
| `GET` | `/api/sync/latest` | 最近同步任务 |
| `POST` | `/api/sync/run` | 手动全量同步 |
| `GET` | `/api/sync/task/current` | 当前同步任务进度 |
| `GET` | `/api/sync/settings` | 定时同步配置 |
| `GET` | `/api/sync/immediate-tags` | 查询所有"立即同步"标签 |
| `POST` | `/api/sync/immediate-tags` | 将标签设为"立即同步"模式 |
| `DELETE` | `/api/sync/immediate-tags/{tag_id}` | 从"立即同步"中移除标签 |

## 配置

通过 `.env` 文件或环境变量配置（参见 `config.py`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATA_DIR` | `../private-data/bilibili-tag-group/` | JSON 数据文件目录 |
| `SYNC_INTERVAL_MINUTES` | `60` | 定时同步间隔（分钟） |
| `BILIBILI_COOKIE` | （空） | B 站登录 Cookie，提高反爬成功率 |

## 启动

```bash
# 安装依赖
uv sync --extra dev

# 启动 API（首次启动自动创建数据目录与 logs/）
uv run uvicorn app.main:app --reload
```

## 抓取器

使用 **`PlaywrightBilibiliFetcher`** — 通过 Playwright 无头浏览器打开 UP 主空间投稿页，从 DOM 视频卡片逐页提取数据，绕过 WBI 签名风控；带内存缓存（视频 1h、昵称 24h）。

抓取层是校准过的冻结基准，完整行为描述见 [../docs/fetcher.md](../docs/fetcher.md)，疑点与待确认建议见 [../docs/fetcher-review.md](../docs/fetcher-review.md)。
