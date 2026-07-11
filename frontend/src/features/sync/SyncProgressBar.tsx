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
