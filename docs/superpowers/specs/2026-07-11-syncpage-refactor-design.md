# SyncPage 重构设计

**日期**：2026-07-11
**状态**：已确认

## 目标

重构 SyncPage 及其相关的同步展示组件，使用 feature 文件夹聚合的模式，拆分自定义 hook 和子组件，提升代码的工程化和可维护性。

## 当前问题

1. `SyncStatusPanel.tsx` 是死代码，未被 SyncPage 引用
2. `SyncPage.tsx`（~390 行）单一组件混合了数据获取、轮询管理、心跳检测、标签 CRUD 和 UI 渲染
3. 轮询逻辑直接写在组件中，无法复用和独立测试
4. 大量内联样式，可读性差
5. 没有自定义 hook，业务逻辑和 UI 强耦合

## 目标结构

```
frontend/src/features/sync/
├── index.ts                    # 统一导出 SyncPage
├── SyncPage.tsx                # 编排组件（~80 行）
├── hooks.ts                    # useSyncPolling, useSyncTask, useSyncSettings, useImmediateTags
├── SyncProgressBar.tsx         # 同步进度条（运行中/已终止）
├── SyncTaskResult.tsx          # 任务完成/失败横幅
├── SyncSettingsBanner.tsx      # 定时同步配置展示
├── SyncLogCard.tsx             # 最近同步日志卡片
└── ImmediateTagsSection.tsx    # 立即同步标签管理
```

### 需要删除的文件

- `frontend/src/pages/SyncPage.tsx`
- `frontend/src/components/SyncStatusPanel.tsx`

### 需要修改的文件

- `frontend/src/App.tsx` — import 路径改为 `./features/sync`
- `frontend/src/styles/index.css` — 新增 sync 模块 CSS 类

## Hook 设计

### useSyncTask()

管理同步任务的触发与状态。

- 初始加载：自动 `fetchCurrentTask()`
- `startSync()`：调用 `runSync()` 并更新本地 task
- 返回：`{ task, isStarting, startSync, error }`

### useSyncPolling(task)

根据 task 状态控制轮询生命周期。

- 常量和逻辑：
  - `POLL_INTERVAL = 3000`（轮询间隔 3 秒）
  - `DEAD_THRESHOLD_SEC = 30`（心跳超时阈值）
  - `isRunning` = `task.status === "running"` 且心跳未超时
  - `isDead` = `task.status === "running"` 且心跳超时 >= 30 秒
  - `progress` = `Math.round(completed / total * 100)`（0-100）
- 轮询逻辑：
  - `task.status === "running"` 时启动 3 秒间隔轮询
  - 每轮调用 `fetchCurrentTask()` 更新 task
  - task 结束时（status !== "running"）自动停止
  - 组件卸载时清理定时器
- 返回：`{ isRunning, isDead, progress }`

### useSyncSettings()

管理定时同步配置和最近同步日志。

- 初始加载：`fetchSyncSettings()` + `fetchLatestSync()`
- 返回：`{ settings, latestLog, isLoading, error }`

### useImmediateTags()

管理立即同步标签的增删和可用标签列表。

- 初始加载：`fetchImmediateTags()` + `fetchTags()`
- `addTag(tagId)`：调用 `addImmediateTag()`，成功后本地追加
- `removeTag(tagId)`：调用 `removeImmediateTag()`，成功后本地移除
- `availableTags`：计算属性，allTags 过滤掉已在 immediateTags 中的
- 返回：`{ immediateTags, availableTags, addTag, removeTag, isAdding, error }`

## 组件设计

### SyncSettingsBanner

纯展示。Props: `{ settings: SyncSettings | null }`

- settings 为 null 时不渲染
- 使用已有 `.status-banner .status-banner-info` CSS 类

### SyncProgressBar

Props: `{ task: SyncTask; isDead: boolean; progress: number }`

- 正常态：蓝色进度条 + Loader2 旋转图标 + `completed/total 个 UP 主` + 当前 UP 主名
- 终止态：红色满条 + XCircle + 错误提示文字
- 专用 CSS 类：`.sync-progress`、`.sync-progress-bar`、`.sync-progress-fill`

### SyncTaskResult

Props: `{ task: SyncTask }`

- 完成：绿色 status-banner-success，"同步完成"，新增视频数 + UP 主数
- 失败：红色 status-banner-error，"同步失败"，错误信息

### SyncLogCard

Props: `{ latestLog: SyncLog | null }`

- null 时显示空状态
- 使用已有 `.sync-log-card` 系列 CSS 类

### ImmediateTagsSection

Props: `{ immediateTags, availableTags, allTags, isAdding, onAdd, onRemove }`

- 标题行 + 说明文字
- 已设置标签：info 徽章 + 闪电图标 + 移除按钮
- 可用标签：filter-chip 按钮列表，点击添加
- 空状态覆盖：无标签 / 无可用标签 / 全部已设置
- 专用 CSS 类：`.immediate-tags`、`.immediate-tags-list`

### SyncPage（编排组件）

```
约 80 行：
1. 调用 4 个 hook
2. 组合子组件
3. 处理加载态
4. 处理顶层错误
```

## 不变内容

- `frontend/src/api/client.ts` — API 类型定义和请求函数保持不变
- 后端 `app/routers/sync.py` 和 `app/services/sync_service.py` 不变
- 功能行为 100% 保持一致
