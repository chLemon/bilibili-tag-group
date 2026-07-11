/**
 * SyncLogCard：展示最近一次同步日志记录，无记录时显示空状态。
 */
import { Clock, FileVideo, CalendarClock, CheckCircle2, XCircle } from "lucide-react";
import { SyncLog } from "../../api/client";

/** 格式化为本地时间字符串 */
function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN");
}

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
        {latestLog.status === "success" ? (
          <span className="badge badge-success">
            <CheckCircle2 size={12} /> 成功
          </span>
        ) : (
          <span className="badge badge-error">
            <XCircle size={12} /> 失败
          </span>
        )}
      </div>
      <div className="sync-log-body">
        <div className="sync-log-stat">
          <FileVideo size={14} />
          <span>新增视频</span>
          <strong>{latestLog.new_videos} 条</strong>
        </div>
        <div className="sync-log-stat">
          <CalendarClock size={14} />
          <span>开始时间</span>
          <span>{formatTime(latestLog.started_at)}</span>
        </div>
        {latestLog.finished_at && (
          <div className="sync-log-stat">
            <CalendarClock size={14} />
            <span>结束时间</span>
            <span>{formatTime(latestLog.finished_at)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
