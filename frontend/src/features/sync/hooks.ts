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
