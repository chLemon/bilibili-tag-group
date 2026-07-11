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
          错误：{error}
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
