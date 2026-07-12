# 视频三态（未看/已看/不看）改造设计

## 概述

视频状态从二态（`watched: bool`）改为三态整数：`0`=未看 / `1`=已看 / `2`=不看。

## 数据库

- `VideoStatus` 表新增 `status` 整数字段（default 0），删除 `watched` 布尔列
- 迁移：`watched=1` → `status=1`，其余 → `status=0`
- `watched_at` 行为不变：`status=1` 时写入当前时间，其他状态清空

## API

- `PATCH /api/videos/{video_id}/status` 替代 `/watched`，请求体 `{status: 0 | 1 | 2}`
- 标签视图视频查询：`WHERE status = 0`（未看）
- `CreatorRead`：`unwatched_count` 只统计 `status=0`
- `VideoDetail`：`watched: bool` → `status: int`

## 前端

- `client.ts`：`updateWatched()` → `updateStatus(videoId, status)`
- `VideoCard`：新增"不看"按钮（与"已看"并列）
- `CreatorDetailPage`：视频行支持三态切换，顶部统计新增"不看"计数
