# API 接口文档

FastAPI 后端全部接口。基础路径 `/api`，开发环境由前端 Vite 代理到 `http://localhost:8000`。

通用约定：

- 请求/响应均为 JSON，字段为 `snake_case`
- 时间字段在响应中序列化为**北京时间** ISO8601 字符串（无时区后缀，如 `2026-07-22T18:00:00`）；存储层为 naive UTC
- 错误响应为 FastAPI 标准 `{"detail": "..."}` 格式
- 视频观看状态取值：`0`=未看，`1`=已看，`2`=不看

## 健康检查

### `GET /health`

响应：`{"status": "ok"}`

## UP 主 `/api/creators`

### `POST /api/creators` — 添加 UP 主

请求体（`CreatorCreate`）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | UP 主名称 |
| `profile_url` | string | 是 | 空间 URL，如 `https://space.bilibili.com/12345` |
| `avatar_url` | string \| null | 否 | 头像 URL |
| `alias` | string \| null | 否 | 别名 |
| `tag_ids` | int[] | 否 | 关联标签 id 列表，默认 `[]` |

响应 `201`：`CreatorRead`。

### `POST /api/creators/batch` — 批量添加

按 uid 批量添加：自动抓取昵称头像、按标签名自动建标签。单条失败不影响其他条目。

请求体（`BatchCreatorRequest`）：

```json
{
  "items": [
    {"uid": "12345", "tag_names": ["编程", "前端"], "name": "可选显示名"}
  ]
}
```

- `uid`：必填，去空白后非空
- `tag_names`：标签名数组，自动去空白、去空串；不存在的标签自动创建
- `name`：可选，缺省用抓取到的昵称

响应 `200`（`BatchCreatorResponse`）：

```json
{
  "results": [
    {"uid": "12345", "success": true, "creator": { "…CreatorRead…" }, "error": null},
    {"uid": "99999", "success": false, "creator": null, "error": "失败原因"}
  ]
}
```

### `GET /api/creators` — UP 主列表

响应 `200`：`CreatorRead[]`。

### `GET /api/creators/resolve-name?profile_url=...` — 抓取昵称头像

根据空间 URL 实时抓取 B 站昵称和头像（用于添加 UP 主时预填）。

响应 `200`：`{"name": "...", "avatar_url": "..." 或 null}`

错误：`400` URL 无法解析出 uid；`502` 抓取失败（B 站侧问题）。

### `GET /api/creators/{id}` — 单个 UP 主

响应 `200`：`CreatorRead`。错误：`404` 不存在。

### `PATCH /api/creators/{id}` — 编辑 UP 主

请求体（`CreatorUpdate`，所有字段可选，传什么改什么）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string \| null | 名称 |
| `alias` | string \| null | 别名 |
| `enabled` | bool \| null | 是否参与同步 |
| `tag_ids` | int[] \| null | 标签关联（传入则整体替换） |

响应 `200`：`CreatorRead`。错误：`404` 不存在。

### `GET /api/creators/{id}/videos` — 该 UP 主的视频列表

响应 `200`：`VideoDetail[]`，按发布时间倒序，含观看状态。错误：`404` UP 主不存在。

### `PATCH /api/creators/{id}/videos/status` — 批量标记状态

将该 UP 主所有**未看**视频批量置为指定状态。

请求体：`{"status": 1}`

响应 `200`：`{"creator_id": 1, "status": 1, "updated_count": 12}`。错误：`404` UP 主不存在。

## 标签 `/api/tags`

### `POST /api/tags` — 创建标签

请求体：`{"name": "编程"}`（去空白，空串报 422）。

响应 `201`：`TagRead`。

### `GET /api/tags` — 标签列表

响应 `200`：`TagRead[]`。

### `GET /api/tags/{id}/videos` — 标签下未看视频

该标签下所有 UP 主的未看视频，按发布时间倒序。响应 `200`：`VideoRead[]`。

### `GET /api/tags/untagged/videos` — 无标签 UP 主的未看视频

响应 `200`：`VideoRead[]`，按发布时间倒序。

## 视频 `/api/videos`

### `PATCH /api/videos/{id}/status` — 更新观看状态

请求体：`{"status": 1}`（0=未看, 1=已看, 2=不看；置为已看时记录 `watched_at`，其他状态清空）。

响应 `200`：`{"video_id": 1, "status": 1}`。错误：`404` 视频不存在。

## 同步 `/api/sync`

### `GET /api/sync/latest` — 最近一次全量同步

响应 `200`：`SyncTaskRead` 或 `null`（从未同步过）。

### `POST /api/sync/run` — 手动触发全量同步

幂等：已有运行中任务时直接返回现有任务，不重复启动。任务由后台协程执行，接口立即返回。

响应 `200`：`SyncTaskRead`（刚创建或现有的运行中任务）。

### `GET /api/sync/task/current` — 当前任务进度

前端每 3 秒轮询此接口。响应 `200`：`SyncTaskRead` 或 `null`。

### `GET /api/sync/settings` — 调度配置

响应 `200`：

```json
{"enabled": true, "interval_minutes": 60, "job_id": "sync-all"}
```

### `GET /api/sync/immediate-tags` — 立即同步标签列表

响应 `200`：`[{"id": 1, "tag_id": 2, "sync_mode": "immediate"}]`。

### `POST /api/sync/immediate-tags?tag_id=N` — 设为立即同步

tag_id 通过查询参数传递。已配置时返回现有配置（幂等）。

响应 `201`：`{"id": 1, "tag_id": 2, "sync_mode": "immediate"}`。错误：`404` 标签不存在。

### `DELETE /api/sync/immediate-tags/{tag_id}` — 取消立即同步

响应 `204` 无响应体。错误：`404` 该标签未配置立即同步。

## 响应模型字段

### `CreatorRead`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | |
| `name` | string | B 站昵称（同步时自动更新） |
| `alias` | string \| null | 别名 |
| `profile_url` | string | |
| `avatar_url` | string \| null | |
| `tag_ids` | int[] | 关联标签 |
| `enabled` | bool | 是否参与同步，默认 true |
| `video_count` | int | B 站侧视频总数（抓取得到） |
| `synced_video_count` | int | 本地已同步视频数 |
| `unwatched_count` | int | 未看视频数 |
| `last_synced_at` | string \| null | 最近同步时间（北京时间 ISO） |

### `TagRead`

`{"id": int, "name": string}`

### `VideoRead`（标签视图）

`id`、`bvid`、`title`、`creator_id`、`creator_name`、`creator_alias`、`creator_avatar_url`、`video_url`、`cover_url`、`published_at`（北京时间）、`duration_seconds`

### `VideoDetail`（UP 主详情）

`VideoRead` 全部字段 + `status`（观看状态，默认 0）

### `SyncTaskRead`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | |
| `scope` | string | 目前恒为 `"all"` |
| `status` | string | `running` / `completed` / `failed` |
| `total_creators` | int | UP 主总数 |
| `completed_creators` | int | 已完成数 |
| `current_creator_name` | string \| null | 正在同步的 UP 主 |
| `new_videos` | int | 本轮新视频数 |
| `error_message` | string \| null | 失败原因（多 UP 主错误按行拼接） |
| `started_at` | string | 北京时间 |
| `finished_at` | string \| null | 北京时间 |
| `heartbeat_at` | string \| null | 北京时间；执行中每 15s 更新，45s 未更新视为进程崩溃 |
