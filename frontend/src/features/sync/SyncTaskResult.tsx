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
