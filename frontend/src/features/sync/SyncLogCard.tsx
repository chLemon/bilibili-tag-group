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
