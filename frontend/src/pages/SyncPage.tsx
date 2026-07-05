/**
 * SyncPage：同步状态页面。
 * 支持异步同步任务、进度轮询、探活检测。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchLatestSync,
  fetchSyncSettings,
  fetchImmediateTags,
  addImmediateTag,
  removeImmediateTag,
  fetchTags,
  fetchCurrentTask,
  runSync,
  SyncLog,
  SyncSettings,
  SyncTask,
  ImmediateTag,
  Tag,
} from "../api/client";
import {
  Loader2,
  AlertCircle,
  Zap,
  Plus,
  X,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  FileVideo,
} from "lucide-react";

const POLL_INTERVAL = 3000;
/** 心跳超过此秒数视为任务终止 */
const DEAD_THRESHOLD_SEC = 30;

export default function SyncPage() {
  const [latestLog, setLatestLog] = useState<SyncLog | null>(null);
  const [settings, setSettings] = useState<SyncSettings | null>(null);
  const [immediateTags, setImmediateTags] = useState<ImmediateTag[]>([]);
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [task, setTask] = useState<SyncTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addingTagId, setAddingTagId] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 是否正在同步中（running 且未终止）
  const isRunning =
    task?.status === "running" &&
    (task.heartbeat_at
      ? Date.now() - new Date(task.heartbeat_at).getTime() < DEAD_THRESHOLD_SEC * 1000
      : true);
  const isDead =
    task?.status === "running" &&
    task.heartbeat_at &&
    Date.now() - new Date(task.heartbeat_at).getTime() >= DEAD_THRESHOLD_SEC * 1000;

  // 初始加载
  useEffect(() => {
    Promise.all([
      fetchLatestSync(),
      fetchSyncSettings(),
      fetchImmediateTags(),
      fetchTags(),
      fetchCurrentTask(),
    ])
      .then(([log, cfg, imTags, tags, curTask]) => {
        setLatestLog(log);
        setSettings(cfg);
        setImmediateTags(imTags);
        setAllTags(tags);
        setTask(curTask);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // 轮询
  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const t = await fetchCurrentTask();
        setTask(t);
        if (!t || t.status !== "running") {
          // 同步已结束，停轮询并刷新日志
          stopPolling();
          const log = await fetchLatestSync();
          setLatestLog(log);
        }
      } catch {
        // 轮询失败静默忽略
      }
    }, POLL_INTERVAL);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // 如果初始任务 running，开始轮询
  useEffect(() => {
    if (task?.status === "running") {
      startPolling();
    }
    return () => stopPolling();
  }, [task?.status, task?.id, startPolling, stopPolling]);

  // 清理
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  async function handleRunSync() {
    setStarting(true);
    setError(null);
    try {
      const t = await runSync();
      setTask(t);
      if (t.status === "running") {
        startPolling();
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setStarting(false);
    }
  }

  async function handleAddImmediateTag(tagId: number) {
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
  }

  async function handleRemoveImmediateTag(tagId: number) {
    setError(null);
    try {
      await removeImmediateTag(tagId);
      setImmediateTags((prev) => prev.filter((t) => t.tag_id !== tagId));
    } catch (err) {
      setError(String(err));
    }
  }

  const immediateTagIds = new Set(immediateTags.map((t) => t.tag_id));
  const availableTags = allTags.filter((t) => !immediateTagIds.has(t.id));
  const progress =
    task && task.total_creators > 0
      ? Math.round((task.completed_creators / task.total_creators) * 100)
      : 0;

  if (loading) {
    return (
      <div className="loading-state">
        <Loader2 size={20} className="spinner" /> 加载同步信息中…
      </div>
    );
  }

  return (
    <div>
      {/* 标题行 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "var(--space-5)",
        }}
      >
        <h2>同步状态</h2>
        <button
          className="btn btn-primary btn-lg"
          onClick={handleRunSync}
          disabled={starting || isRunning}
        >
          {starting ? (
            <Loader2 size={16} className="spinner" />
          ) : (
            <Play size={16} />
          )}
          {starting ? "启动中…" : isRunning ? "同步中…" : "立即同步"}
        </button>
      </div>

      {error && (
        <div className="error-message">
          <AlertCircle size={16} />
          错误：{error}
        </div>
      )}

      {/* 定时同步配置 */}
      {settings && (
        <div className="status-banner status-banner-info" style={{ marginBottom: "var(--space-4)" }}>
          <Clock size={18} />
          <div>
            <strong>定时同步：</strong>
            {settings.enabled
              ? `已启用，每 ${settings.interval_minutes} 分钟执行一次`
              : "未启用"}
          </div>
        </div>
      )}

      {/* 同步进度条 */}
      {task && (isRunning || isDead) && (
        <div className="card" style={{ padding: "var(--space-4)", marginBottom: "var(--space-4)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-2)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", fontSize: "14px", fontWeight: 600 }}>
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
          <div
            style={{
              height: 6,
              background: "var(--color-border-light)",
              borderRadius: 3,
              overflow: "hidden",
              marginBottom: "var(--space-2)",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${isDead ? 100 : progress}%`,
                background: isDead ? "var(--color-error)" : "var(--color-primary)",
                borderRadius: 3,
                transition: "width 0.5s ease",
              }}
            />
          </div>

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
      )}

      {/* 上次同步完成结果 */}
      {task && task.status !== "running" && !isDead && (
        <div
          className={`status-banner ${task.status === "completed" ? "status-banner-success" : "status-banner-error"}`}
          style={{ marginBottom: "var(--space-4)" }}
        >
          {task.status === "completed" ? (
            <CheckCircle2 size={18} style={{ color: "var(--color-success)" }} />
          ) : (
            <XCircle size={18} style={{ color: "var(--color-error)" }} />
          )}
          <div>
            <strong>
              {task.status === "completed" ? "同步完成" : "同步失败"}
            </strong>
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
      )}

      {/* 最近同步日志 */}
      {latestLog && (
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
      )}

      {/* 立即同步标签管理 */}
      <div style={{ marginTop: "var(--space-6)" }}>
        <h3 style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
          <Zap size={18} style={{ color: "var(--color-warning)" }} />
          立即同步标签
        </h3>
        <p className="text-secondary text-sm" style={{ marginBottom: "var(--space-4)" }}>
          拥有这些标签的 UP 主在同步时将绕过 TTL 缓存，直接从 B 站获取最新视频数据。
        </p>

        {immediateTags.length === 0 ? (
          <div className="text-muted text-sm" style={{ marginBottom: "var(--space-2)" }}>
            暂无立即同步标签，点击下方标签添加。
          </div>
        ) : (
          <div className="flex gap-2" style={{ flexWrap: "wrap", marginBottom: "var(--space-3)" }}>
            {immediateTags.map((it) => {
              const tag = allTags.find((t) => t.id === it.tag_id);
              return (
                <span
                  key={it.id}
                  className="badge badge-info"
                  style={{ gap: "var(--space-2)", padding: "5px 12px", fontSize: "13px" }}
                >
                  <Zap size={13} />
                  {tag?.name ?? `标签 #${it.tag_id}`}
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ padding: "1px 2px", marginLeft: "2px" }}
                    onClick={() => handleRemoveImmediateTag(it.tag_id)}
                    title="移除立即同步"
                  >
                    <X size={13} />
                  </button>
                </span>
              );
            })}
          </div>
        )}

        <div className="text-sm text-secondary" style={{ marginBottom: "var(--space-2)" }}>
          点击标签设为"立即同步"：
        </div>
        {availableTags.length > 0 ? (
          <div className="flex gap-2" style={{ flexWrap: "wrap" }}>
            {availableTags.map((tag) => (
              <button
                key={tag.id}
                className="filter-chip"
                onClick={() => handleAddImmediateTag(tag.id)}
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
    </div>
  );
}
