# SyncPage 重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 SyncPage 从单文件巨组件重构为 feature-folder 结构，拆分为 4 个自定义 hook + 5 个子组件 + 1 个编排组件。

**Architecture:** `frontend/src/features/sync/` 目录聚合所有同步相关代码。4 个 hook 各自管理一个数据域（task、polling、settings、immediateTags），5 个展示组件只接收 props 渲染 UI，SyncPage 作为编排层组合它们。

**Tech Stack:** React 18 + TypeScript, Vite, lucide-react

## Global Constraints

- 所有注释使用中文
- 功能行为 100% 保持一致，不修改任何业务逻辑
- 不修改 `frontend/src/api/client.ts`
- 不修改后端任何文件
- CSS 类名沿用项目已有的命名风格（kebab-case）

---

### Task 1: 创建目录结构 + CSS 样式

**Files:**
- Create: `frontend/src/features/sync/`（目录，后续文件填充）
- Modify: `frontend/src/styles/index.css`（末尾追加 sync 模块 CSS）

**Interfaces:**
- Produces: CSS 类 `.sync-progress`、`.sync-progress-header`、`.sync-progress-status`、`.sync-progress-track`、`.sync-progress-fill`、`.immediate-tags-section`、`.immediate-tags-title`、`.immediate-tags-list`、`.immediate-tag-item`、`.immediate-tag-remove`

- [ ] **Step 1: 创建 features/sync 目录**

```powershell
New-Item -ItemType Directory -Force "frontend/src/features/sync"
```

- [ ] **Step 2: 在 index.css 末尾追加 sync 模块样式**

在 `frontend/src/styles/index.css` 末尾追加以下内容：

```css
/* ===== 同步进度条 ===== */
.sync-progress {
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  margin-bottom: var(--space-4);
}

.sync-progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.sync-progress-status {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 14px;
  font-weight: 600;
}

.sync-progress-track {
  height: 6px;
  background: var(--color-border-light);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: var(--space-2);
}

.sync-progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

/* ===== 立即同步标签 ===== */
.immediate-tags-section {
  margin-top: var(--space-6);
}

.immediate-tags-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.immediate-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.immediate-tag-item {
  gap: var(--space-2);
  padding: 5px 12px;
  font-size: 13px;
}

.immediate-tag-remove {
  padding: 1px 2px;
  margin-left: 2px;
}
```

- [ ] **Step 3: 验证 CSS 文件无语法错误**

```powershell
Get-Content "frontend/src/styles/index.css" | Select-Object -Last 5
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/styles/index.css
git commit -m "style: 添加同步进度条和立即同步标签的 CSS 类

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 创建 hooks.ts — 4 个自定义 hook

**Files:**
- Create: `frontend/src/features/sync/hooks.ts`

**Interfaces:**
- Consumes: `frontend/src/api/client.ts` 中的 `fetchCurrentTask`, `runSync`, `fetchSyncSettings`, `fetchLatestSync`, `fetchImmediateTags`, `fetchTags`, `addImmediateTag`, `removeImmediateTag` 及其类型
- Produces:
  - `useSyncTask()` → `{ task: SyncTask | null, setTask: Dispatch, isStarting: boolean, startSync: () => Promise<void>, error: string | null }`
  - `useSyncPolling(task, onTaskUpdate)` → `{ isRunning: boolean, isDead: boolean, progress: number }`
  - `useSyncSettings()` → `{ settings: SyncSettings | null, latestLog: SyncLog | null, isLoading: boolean, error: string | null }`
  - `useImmediateTags()` → `{ immediateTags: ImmediateTag[], availableTags: Tag[], allTags: Tag[], addingTagId: number | null, addTag: (tagId: number) => Promise<void>, removeTag: (tagId: number) => Promise<void>, error: string | null }`

- [ ] **Step 1: 编写 hooks.ts**

```typescript
/**
 * 同步模块自定义 hook：封装同步任务、轮询、配置、立即同步标签的数据获取与操作逻辑。
 */
import { useState, useEffect, useRef, useCallback } from "react";
import {
  fetchCurrentTask,
  runSync,
  fetchSyncSettings,
  fetchLatestSync,
  fetchImmediateTags,
  fetchTags,
  addImmediateTag,
  removeImmediateTag,
  SyncTask,
  SyncSettings,
  SyncLog,
  ImmediateTag,
  Tag,
} from "../../api/client";

/** 轮询间隔（毫秒） */
const POLL_INTERVAL = 3000;
/** 心跳超过此秒数判定任务已终止 */
const DEAD_THRESHOLD_SEC = 30;

// ── useSyncTask ────────────────────────────────────────────────────

/**
 * 管理同步任务的触发与当前状态。
 * 初始加载时自动获取最近一次任务，并提供 startSync 方法手动触发新任务。
 */
export function useSyncTask() {
  const [task, setTask] = useState<SyncTask | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCurrentTask()
      .then(setTask)
      .catch((err: Error) => setError(err.message));
  }, []);

  const startSync = useCallback(async () => {
    setIsStarting(true);
    setError(null);
    try {
      const t = await runSync();
      setTask(t);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsStarting(false);
    }
  }, []);

  return { task, setTask, isStarting, startSync, error };
}

// ── useSyncPolling ─────────────────────────────────────────────────

/**
 * 根据任务状态自动启停轮询，计算运行态和心跳状态。
 *
 * 参数：
 *   task — 当前同步任务（可能为 null）
 *   onTaskUpdate — 轮询获取到新任务数据时的回调（由 useSyncTask 的 setTask 提供）
 */
export function useSyncPolling(
  task: SyncTask | null,
  onTaskUpdate: (t: SyncTask | null) => void,
) {
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isRunning =
    task?.status === "running" &&
    (task.heartbeat_at
      ? Date.now() - new Date(task.heartbeat_at).getTime() < DEAD_THRESHOLD_SEC * 1000
      : true);

  const isDead =
    task?.status === "running" &&
    task.heartbeat_at != null &&
    Date.now() - new Date(task.heartbeat_at).getTime() >= DEAD_THRESHOLD_SEC * 1000;

  const progress =
    task && task.total_creators > 0
      ? Math.round((task.completed_creators / task.total_creators) * 100)
      : 0;

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current !== null) return;
    pollRef.current = setInterval(async () => {
      try {
        const t = await fetchCurrentTask();
        onTaskUpdate(t);
        if (!t || t.status !== "running") {
          stopPolling();
        }
      } catch {
        // 轮询失败静默忽略，下一轮重试
      }
    }, POLL_INTERVAL);
  }, [onTaskUpdate, stopPolling]);

  // task 变为 running 时启动轮询，结束时或组件卸载时停止
  useEffect(() => {
    if (task?.status === "running") {
      startPolling();
    }
    return () => stopPolling();
  }, [task?.status, task?.id, startPolling, stopPolling]);

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return { isRunning, isDead, progress };
}

// ── useSyncSettings ────────────────────────────────────────────────

/**
 * 加载定时同步配置与最近一次同步日志。
 */
export function useSyncSettings() {
  const [settings, setSettings] = useState<SyncSettings | null>(null);
  const [latestLog, setLatestLog] = useState<SyncLog | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchSyncSettings(), fetchLatestSync()])
      .then(([cfg, log]) => {
        setSettings(cfg);
        setLatestLog(log);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, []);

  return { settings, latestLog, isLoading, error };
}

// ── useImmediateTags ───────────────────────────────────────────────

/**
 * 管理立即同步标签的增删及可用标签列表。
 */
export function useImmediateTags() {
  const [immediateTags, setImmediateTags] = useState<ImmediateTag[]>([]);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [addingTagId, setAddingTagId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchImmediateTags(), fetchTags()])
      .then(([imTags, tags]) => {
        setImmediateTags(imTags);
        setAllTags(tags);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const addTag = useCallback(async (tagId: number) => {
    setAddingTagId(tagId);
    setError(null);
    try {
      const result = await addImmediateTag(tagId);
      setImmediateTags((prev) => [...prev, result]);
    } catch (err) {
      setError(String(err));
    } finally {
      setAddingTagId(null);
    }
  }, []);

  const removeTag = useCallback(async (tagId: number) => {
    setError(null);
    try {
      await removeImmediateTag(tagId);
      setImmediateTags((prev) => prev.filter((t) => t.tag_id !== tagId));
    } catch (err) {
      setError(String(err));
    }
  }, []);

  const immediateTagIds = new Set(immediateTags.map((t) => t.tag_id));
  const availableTags = allTags.filter((t) => !immediateTagIds.has(t.id));

  return { immediateTags, availableTags, allTags, addingTagId, addTag, removeTag, error };
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/features/sync/hooks.ts
git commit -m "feat: 添加同步模块自定义 hook（useSyncTask/useSyncPolling/useSyncSettings/useImmediateTags）

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: SyncSettingsBanner 组件

**Files:**
- Create: `frontend/src/features/sync/SyncSettingsBanner.tsx`

**Interfaces:**
- Consumes: `SyncSettings` from `../../api/client`
- Produces: `export default function SyncSettingsBanner({ settings }: { settings: SyncSettings | null })`

- [ ] **Step 1: 编写 SyncSettingsBanner.tsx**

```typescript
/**
 * SyncSettingsBanner：展示定时同步的启用状态和间隔配置。
 */
import { Clock } from "lucide-react";
import { SyncSettings } from "../../api/client";

interface Props {
  settings: SyncSettings | null;
}

export default function SyncSettingsBanner({ settings }: Props) {
  if (!settings) return null;

  return (
    <div className="status-banner status-banner-info" style={{ marginBottom: "var(--space-4)" }}>
      <Clock size={18} />
      <div>
        <strong>定时同步：</strong>
        {settings.enabled
          ? `已启用，每 ${settings.interval_minutes} 分钟执行一次`
          : "未启用"}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/features/sync/SyncSettingsBanner.tsx
git commit -m "feat: 添加 SyncSettingsBanner 组件 — 定时同步配置展示

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: SyncProgressBar 组件

**Files:**
- Create: `frontend/src/features/sync/SyncProgressBar.tsx`

**Interfaces:**
- Consumes: `SyncTask` from `../../api/client`
- Produces: `export default function SyncProgressBar({ task, isDead, progress }: Props)`

- [ ] **Step 1: 编写 SyncProgressBar.tsx**

```typescript
/**
 * SyncProgressBar：同步进行中的进度条，含正常运行态和心跳终止态。
 */
import { Loader2, XCircle } from "lucide-react";
import { SyncTask } from "../../api/client";

interface Props {
  task: SyncTask;
  isDead: boolean;
  progress: number;
}

export default function SyncProgressBar({ task, isDead, progress }: Props) {
  return (
    <div className="sync-progress">
      {/* 状态头部 */}
      <div className="sync-progress-header">
        <div className="sync-progress-status">
          {isDead ? (
            <>
              <XCircle size={16} style={{ color: "var(--color-error)" }} />
              <span style={{ color: "var(--color-error)" }}>同步任务已终止</span>
            </>
          ) : (
            <>
              <Loader2 size={16} className="spinner" />
              正在同步…
            </>
          )}
        </div>
        <span className="text-sm text-secondary">
          {task.completed_creators} / {task.total_creators} 个 UP 主
        </span>
      </div>

      {/* 进度条 */}
      <div className="sync-progress-track">
        <div
          className="sync-progress-fill"
          style={{
            width: `${isDead ? 100 : progress}%`,
            background: isDead ? "var(--color-error)" : "var(--color-primary)",
          }}
        />
      </div>

      {/* 当前 UP 主或终止提示 */}
      {task.current_creator_name && !isDead && (
        <div className="text-sm text-secondary">
          当前：{task.current_creator_name}
        </div>
      )}
      {isDead && (
        <div className="text-sm" style={{ color: "var(--color-error)" }}>
          任务可能因进程崩溃而终止，请重新点击"立即同步"
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/features/sync/SyncProgressBar.tsx
git commit -m "feat: 添加 SyncProgressBar 组件 — 同步进度条与终止态展示

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: SyncTaskResult 组件

**Files:**
- Create: `frontend/src/features/sync/SyncTaskResult.tsx`

**Interfaces:**
- Consumes: `SyncTask` from `../../api/client`
- Produces: `export default function SyncTaskResult({ task }: { task: SyncTask })`

- [ ] **Step 1: 编写 SyncTaskResult.tsx**

```typescript
/**
 * SyncTaskResult：同步任务完成或失败后的结果横幅。
 */
import { CheckCircle2, XCircle } from "lucide-react";
import { SyncTask } from "../../api/client";

interface Props {
  task: SyncTask;
}

export default function SyncTaskResult({ task }: Props) {
  const isCompleted = task.status === "completed";

  return (
    <div
      className={`status-banner ${isCompleted ? "status-banner-success" : "status-banner-error"}`}
      style={{ marginBottom: "var(--space-4)" }}
    >
      {isCompleted ? (
        <CheckCircle2 size={18} style={{ color: "var(--color-success)" }} />
      ) : (
        <XCircle size={18} style={{ color: "var(--color-error)" }} />
      )}
      <div>
        <strong>{isCompleted ? "同步完成" : "同步失败"}</strong>
        <div className="text-sm">
          新增 {task.new_videos} 个视频 · 同步了 {task.completed_creators} 个 UP 主
          {task.error_message && (
            <span style={{ color: "var(--color-error)", marginLeft: "var(--space-2)" }}>
              ：{task.error_message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/features/sync/SyncTaskResult.tsx
git commit -m "feat: 添加 SyncTaskResult 组件 — 同步完成/失败结果横幅

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: SyncLogCard 组件

**Files:**
- Create: `frontend/src/features/sync/SyncLogCard.tsx`

**Interfaces:**
- Consumes: `SyncLog` from `../../api/client`
- Produces: `export default function SyncLogCard({ latestLog }: { latestLog: SyncLog | null })`

- [ ] **Step 1: 编写 SyncLogCard.tsx**

```typescript
/**
 * SyncLogCard：展示最近一次同步日志记录，无记录时显示空状态。
 */
import { Clock, FileVideo } from "lucide-react";
import { SyncLog } from "../../api/client";

interface Props {
  latestLog: SyncLog | null;
}

export default function SyncLogCard({ latestLog }: Props) {
  if (!latestLog) {
    return (
      <div className="empty-state" style={{ paddingTop: "var(--space-4)", marginBottom: "var(--space-4)" }}>
        <Clock size={36} />
        <p>暂无同步记录</p>
        <p className="empty-hint">点击"立即同步"按钮执行首次同步</p>
      </div>
    );
  }

  return (
    <div className="card sync-log-card" style={{ marginBottom: "var(--space-4)" }}>
      <div className="sync-log-header">
        <Clock size={16} />
        <span>最近同步记录</span>
      </div>
      <div className="sync-log-body">
        <div className="sync-log-stat">
          <FileVideo size={14} />
          <span>新增视频</span>
          <strong>{latestLog.new_videos} 条</strong>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/features/sync/SyncLogCard.tsx
git commit -m "feat: 添加 SyncLogCard 组件 — 最近同步日志卡片与空状态

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: ImmediateTagsSection 组件

**Files:**
- Create: `frontend/src/features/sync/ImmediateTagsSection.tsx`

**Interfaces:**
- Consumes: `ImmediateTag`, `Tag` from `../../api/client`
- Produces: `export default function ImmediateTagsSection({ immediateTags, availableTags, allTags, addingTagId, onAdd, onRemove }: Props)`

- [ ] **Step 1: 编写 ImmediateTagsSection.tsx**

```typescript
/**
 * ImmediateTagsSection：管理立即同步标签——展示已设置的标签，提供添加/移除操作。
 */
import { Zap, Plus, X, Loader2 } from "lucide-react";
import { ImmediateTag, Tag } from "../../api/client";

interface Props {
  immediateTags: ImmediateTag[];
  availableTags: Tag[];
  allTags: Tag[];
  addingTagId: number | null;
  onAdd: (tagId: number) => Promise<void>;
  onRemove: (tagId: number) => Promise<void>;
}

export default function ImmediateTagsSection({
  immediateTags,
  availableTags,
  allTags,
  addingTagId,
  onAdd,
  onRemove,
}: Props) {
  return (
    <div className="immediate-tags-section">
      {/* 标题 */}
      <h3 className="immediate-tags-title">
        <Zap size={18} style={{ color: "var(--color-warning)" }} />
        立即同步标签
      </h3>

      {/* 说明 */}
      <p className="text-secondary text-sm" style={{ marginBottom: "var(--space-4)" }}>
        拥有这些标签的 UP 主在同步时将绕过 TTL 缓存，直接从 B 站获取最新视频数据。
      </p>

      {/* 已设置的立即同步标签列表 */}
      {immediateTags.length === 0 ? (
        <div className="text-muted text-sm" style={{ marginBottom: "var(--space-2)" }}>
          暂无立即同步标签，点击下方标签添加。
        </div>
      ) : (
        <div className="immediate-tags-list">
          {immediateTags.map((it) => {
            const tag = allTags.find((t) => t.id === it.tag_id);
            return (
              <span key={it.id} className="badge badge-info immediate-tag-item">
                <Zap size={13} />
                {tag?.name ?? `标签 #${it.tag_id}`}
                <button
                  className="btn btn-ghost btn-sm immediate-tag-remove"
                  onClick={() => onRemove(it.tag_id)}
                  title="移除立即同步"
                >
                  <X size={13} />
                </button>
              </span>
            );
          })}
        </div>
      )}

      {/* 可添加的标签选择器 */}
      <div className="text-sm text-secondary" style={{ marginBottom: "var(--space-2)" }}>
        点击标签设为"立即同步"：
      </div>
      {availableTags.length > 0 ? (
        <div className="flex gap-2" style={{ flexWrap: "wrap" }}>
          {availableTags.map((tag) => (
            <button
              key={tag.id}
              className="filter-chip"
              onClick={() => onAdd(tag.id)}
              disabled={addingTagId === tag.id}
            >
              {addingTagId === tag.id ? (
                <Loader2 size={12} className="spinner" />
              ) : (
                <Plus size={12} />
              )}
              {tag.name}
            </button>
          ))}
        </div>
      ) : (
        <div className="text-muted text-sm">
          {allTags.length === 0
            ? "暂无标签，请先在 UP 主管理页面创建标签。"
            : "所有标签已设为立即同步。"}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/features/sync/ImmediateTagsSection.tsx
git commit -m "feat: 添加 ImmediateTagsSection 组件 — 立即同步标签管理

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: SyncPage 编排组件 + index.ts

**Files:**
- Create: `frontend/src/features/sync/SyncPage.tsx`
- Create: `frontend/src/features/sync/index.ts`

**Interfaces:**
- Consumes: All hooks from `./hooks`, all child components, `AlertCircle`, `Play`, `Loader2` from `lucide-react`
- Produces: `export { default as SyncPage } from "./SyncPage"` via `index.ts`

- [ ] **Step 1: 编写 SyncPage.tsx**

```typescript
/**
 * SyncPage：同步状态页面——编排 hook 和子组件，处理加载态与错误展示。
 */
import { Loader2, AlertCircle, Play } from "lucide-react";
import { useSyncTask, useSyncPolling, useSyncSettings, useImmediateTags } from "./hooks";
import SyncSettingsBanner from "./SyncSettingsBanner";
import SyncProgressBar from "./SyncProgressBar";
import SyncTaskResult from "./SyncTaskResult";
import SyncLogCard from "./SyncLogCard";
import ImmediateTagsSection from "./ImmediateTagsSection";

export default function SyncPage() {
  // ── 数据与操作 ──
  const { task, setTask, isStarting, startSync, error: taskError } = useSyncTask();
  const { isRunning, isDead, progress } = useSyncPolling(task, setTask);
  const { settings, latestLog, isLoading: settingsLoading, error: settingsError } = useSyncSettings();
  const {
    immediateTags,
    availableTags,
    allTags,
    addingTagId,
    addTag,
    removeTag,
    error: tagsError,
  } = useImmediateTags();

  // ── 聚合状态 ──
  const error = taskError || settingsError || tagsError;
  const loading = settingsLoading;

  // ── 加载态 ──
  if (loading) {
    return (
      <div className="loading-state">
        <Loader2 size={20} className="spinner" /> 加载同步信息中…
      </div>
    );
  }

  // ── 页面主体 ──
  return (
    <div>
      {/* 标题行 + 立即同步按钮 */}
      <div className="page-header">
        <h2>同步状态</h2>
        <button
          className="btn btn-primary btn-lg"
          onClick={startSync}
          disabled={isStarting || isRunning}
        >
          {isStarting ? (
            <Loader2 size={16} className="spinner" />
          ) : (
            <Play size={16} />
          )}
          {isStarting ? "启动中…" : isRunning ? "同步中…" : "立即同步"}
        </button>
      </div>

      {/* 错误横幅 */}
      {error && (
        <div className="error-message">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* 定时同步配置 */}
      <SyncSettingsBanner settings={settings} />

      {/* 同步进度条（运行中或已终止） */}
      {(isRunning || isDead) && task && (
        <SyncProgressBar task={task} isDead={isDead} progress={progress} />
      )}

      {/* 任务完成/失败结果 */}
      {task && task.status !== "running" && !isDead && (
        <SyncTaskResult task={task} />
      )}

      {/* 最近同步记录 */}
      <SyncLogCard latestLog={latestLog} />

      {/* 立即同步标签管理 */}
      <ImmediateTagsSection
        immediateTags={immediateTags}
        availableTags={availableTags}
        allTags={allTags}
        addingTagId={addingTagId}
        onAdd={addTag}
        onRemove={removeTag}
      />
    </div>
  );
}
```

- [ ] **Step 2: 编写 index.ts**

```typescript
export { default as SyncPage } from "./SyncPage";
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/features/sync/SyncPage.tsx frontend/src/features/sync/index.ts
git commit -m "feat: 添加 SyncPage 编排组件与 index.ts 导出

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: 更新 App.tsx + 删除旧文件

**Files:**
- Modify: `frontend/src/App.tsx`（import 路径从 `./pages/SyncPage` 改为 `./features/sync`）
- Delete: `frontend/src/pages/SyncPage.tsx`
- Delete: `frontend/src/components/SyncStatusPanel.tsx`

**Interfaces:**
- Consumes: `SyncPage` from `./features/sync`（通过 index.ts 的命名导出）
- Produces: App 路由 `/sync` 渲染新的 SyncPage

- [ ] **Step 1: 修改 App.tsx 的 import 路径**

将第 8 行：
```typescript
import SyncPage from "./pages/SyncPage";
```

改为：
```typescript
import { SyncPage } from "./features/sync";
```

- [ ] **Step 2: 删除旧文件**

```powershell
Remove-Item "frontend/src/pages/SyncPage.tsx"
Remove-Item "frontend/src/components/SyncStatusPanel.tsx"
```

- [ ] **Step 3: 验证 TypeScript 编译**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/App.tsx
git rm frontend/src/pages/SyncPage.tsx frontend/src/components/SyncStatusPanel.tsx
git commit -m "refactor: 迁移 SyncPage 到 features/sync/，删除死代码 SyncStatusPanel

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: 验证功能完整性

**Files:** 无新建/修改

- [ ] **Step 1: 启动后端 API**

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload &
```

- [ ] **Step 2: 启动前端开发服务器**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: 手动验证以下功能**

在浏览器中访问同步状态页面，验证：
1. 页面正常加载，显示加载中状态
2. 定时同步配置横幅正确显示
3. 最近同步日志卡片正确显示（或空状态）
4. 点击"立即同步"按钮，进度条正常展示
5. 同步完成后，结果显示横幅正确
6. 立即同步标签：添加/移除操作正常
7. 页面无控制台报错

- [ ] **Step 4: 提交（如有 lint 修复等小改动）**

```bash
git status
```
