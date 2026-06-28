# app — B 站订阅管理后端

基于 FastAPI + SQLAlchemy + SQLite 的 B 站 UP 主订阅管理后端，提供 UP 主管理、标签分组、视频同步与观看状态追踪功能。

## 目录结构

```
app/
├── main.py                  # FastAPI 应用入口，lifespan 管理调度器
├── config.py                # 配置（数据库 URL、同步间隔、Cookie）
├── database.py              # SQLAlchemy 引擎与 Session 工厂
├── dependencies.py          # FastAPI 依赖注入（get_db）
├── scheduler.py             # APScheduler 定时同步调度器
├── models/                  # ORM 数据模型（SQLAlchemy）
│   ├── creator.py           #   UP 主
│   ├── tag.py               #   标签
│   ├── creator_tag.py       #   UP 主-标签多对多关联表
│   ├── video.py             #   视频
│   ├── video_status.py      #   视频观看状态
│   └── sync_log.py          #   同步日志
├── schemas/                 # Pydantic 请求/响应 Schema
│   ├── _datetime.py         #   北京时间序列化类型
│   ├── creator.py           #   UP 主 schema
│   ├── tag.py               #   标签 schema
│   ├── video.py             #   视频 schema
│   └── sync.py              #   同步日志 schema
├── routers/                 # HTTP 路由（API 端点）
│   ├── creators.py          #   /api/creators — UP 主 CRUD + 单 UP 主同步
│   ├── tags.py              #   /api/tags — 标签 CRUD + 标签下未看视频
│   ├── videos.py            #   /api/videos — 标记已看状态
│   └── sync.py              #   /api/sync — 全量同步触发 + 同步日志查询
├── services/                # 业务逻辑层
│   ├── creator_service.py   #   UP 主管理
│   ├── tag_service.py       #   标签与未看视频聚合查询
│   ├── video_service.py     #   视频观看状态管理
│   └── sync_service.py      #   同步核心：抓取 → 写入数据库
└── fetcher/                 # B 站数据抓取层
    ├── models.py            #   FetchedVideo dataclass
    └── playwright_fetcher.py #  基于 Playwright 无头浏览器的抓取器
```

## 数据模型关系

```
Creator ──many-to-many── Tag    （通过 CreatorTag 关联表）
Creator ──one-to-many─── Video
Video   ──one-to-one──── VideoStatus（watched / watched_at）
SyncLog （scope="all" 的全量同步记录）
```

- **标签挂在 UP 主上**，不挂在视频上
- 标签页展示的是"该标签下所有 UP 主的未看视频"
- 时间字段统一使用 naive UTC
- 新视频同步时自动创建 `watched=False` 的 `VideoStatus`

## API 端点概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/api/creators` | 添加 UP 主 |
| `GET` | `/api/creators` | UP 主列表 |
| `GET` | `/api/creators/resolve-name` | 根据 URL 获取昵称 |
| `PATCH` | `/api/creators/{id}` | 编辑 UP 主 |
| `POST` | `/api/creators/{id}/sync` | 同步单个 UP 主 |
| `POST` | `/api/tags` | 创建标签 |
| `GET` | `/api/tags` | 标签列表 |
| `GET` | `/api/tags/{id}/videos` | 标签下未看视频 |
| `PATCH` | `/api/videos/{id}/watched` | 标记已看/未看 |
| `GET` | `/api/sync/latest` | 最近同步日志 |
| `POST` | `/api/sync/run` | 手动全量同步 |
| `GET` | `/api/sync/settings` | 定时同步配置 |

## 配置

通过 `.env` 文件或环境变量配置（参见 `config.py`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./my_bilibili.db` | 数据库连接 |
| `SYNC_INTERVAL_MINUTES` | `60` | 定时同步间隔（分钟） |
| `BILIBILI_COOKIE` | （空） | B 站登录 Cookie，提高反爬成功率 |

## 启动

```bash
# 安装依赖
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 执行数据库迁移
.venv/bin/alembic upgrade head

# 启动 API
.venv/bin/uvicorn app.main:app --reload
```

## 抓取器

使用 **`PlaywrightBilibiliFetcher`** — 通过 Playwright 无头浏览器打开 UP 主空间页面，从 `window.__INITIAL_STATE__` 中提取服务端渲染的视频数据，无需经过 WBI 签名 API，可有效绕过 B 站风控。
