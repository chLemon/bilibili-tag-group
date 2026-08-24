/**
 * SyncLogCard：展示最近若干条同步日志（全量 + 单 UP 主），无记录时显示空状态。
 */
import { Clock, FileVideo, CheckCircle2, XCircle, User } from "lucide-react";
import { SyncTask } from "../api/client";
import { formatLocalDateTime } from "../utils/time";

interface Props {
  latestTasks: SyncTask[];
}

export default function SyncLogCard({ latestTasks }: Props) {
  if (latestTasks.length === 0) {
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
      <div className="sync-log-list">
        {latestTasks.map((task) => (
          <div key={task.id} className="sync-log-row">
            <div className="sync-log-row-head">
              <span className={`badge ${task.scope === "all" ? "badge-info" : "badge-warning"}`}>
                {task.scope === "all" ? "全量" : "单个"}
              </span>
              {task.scope === "creator" && (
                <span className="sync-log-creator">
                  <User size={12} />
                  {task.creator_name ?? `#${task.creator_id}`}
                </span>
              )}
              {task.status === "completed" ? (
                <span className="badge badge-success">
                  <CheckCircle2 size={12} /> 成功
                </span>
              ) : task.status === "running" ? (
                <span className="badge badge-info">进行中</span>
              ) : (
                <span className="badge badge-error">
                  <XCircle size={12} /> 失败
                </span>
              )}
              <span className="sync-log-time">{formatLocalDateTime(task.started_at)}</span>
            </div>
            <div className="sync-log-row-body">
              <span className="sync-log-stat">
                <FileVideo size={12} />
                新增 {task.new_videos} 条
              </span>
              {task.scope === "all" && (
                <span className="sync-log-stat">
                  {task.completed_creators} / {task.total_creators} 个 UP 主
                </span>
              )}
              {task.error_message && (
                <span className="sync-log-stat sync-log-error">
                  {task.error_message}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
