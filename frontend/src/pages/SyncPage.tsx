/**
 * SyncPage：同步状态页面——编排 hook 和子组件，处理加载态与错误展示。
 */
import { Loader2, AlertCircle, Play, Clock, XCircle, CheckCircle2 } from "lucide-react";
import { useSyncTask, useSyncPolling, useSyncSettings, useImmediateTags } from "../hooks/useSync";
import SyncLogCard from "../components/SyncLogCard";
import ImmediateTagsSection from "../components/ImmediateTagsSection";

export default function SyncPage() {
  // ── 数据与操作 ──
  const { task, setTask, isStarting, startSync, error: taskError } = useSyncTask();
  const { settings, latestLog, isLoading: settingsLoading, error: settingsError, refreshLatestLog } = useSyncSettings();
  const { isRunning, isDead, progress } = useSyncPolling(task, setTask, refreshLatestLog);
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

      {/* 同步进度条（运行中或已终止） */}
      {(isRunning || isDead) && task && (
        <div className="sync-progress">
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

          <div className="sync-progress-track">
            <div
              className="sync-progress-fill"
              style={{
                width: `${isDead ? 100 : progress}%`,
                background: isDead ? "var(--color-error)" : "var(--color-primary)",
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

      {/* 任务完成/失败结果 */}
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
            <strong>{task.status === "completed" ? "同步完成" : "同步失败"}</strong>
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
