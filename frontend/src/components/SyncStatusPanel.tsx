/**
 * SyncStatusPanel：展示最近一次同步结果与手动触发入口。
 */
import { SyncLog, SyncSettings } from "../api/client";
import {
  Clock,
  CheckCircle2,
  XCircle,
  FileVideo,
  CalendarClock,
} from "lucide-react";

interface SyncStatusPanelProps {
  latestLog: SyncLog | null;
  settings: SyncSettings | null;
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN");
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    success: "成功",
    failed: "失败",
    running: "运行中",
  };
  return map[status] ?? status;
}

export default function SyncStatusPanel({
  latestLog,
  settings,
}: SyncStatusPanelProps) {
  return (
    <div>
      {/* 调度配置信息 */}
      {settings && (
        <div className="status-banner status-banner-info" style={{ marginBottom: "var(--space-5)" }}>
          <CalendarClock size={18} />
          <div>
            <strong>定时同步：</strong>
            {settings.enabled
              ? `已启用，每 ${settings.interval_minutes} 分钟执行一次`
              : "未启用"}
          </div>
        </div>
      )}

      {/* 最近同步日志 */}
      {latestLog ? (
        <div className="card sync-log-card">
          <div className="sync-log-header">
            <Clock size={16} />
            <span>最近同步结果</span>
            {latestLog.status === "success" ? (
              <span className="badge badge-success">
                <CheckCircle2 size={12} /> {statusLabel(latestLog.status)}
              </span>
            ) : (
              <span className="badge badge-error">
                <XCircle size={12} /> {statusLabel(latestLog.status)}
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
              <span>{formatDateTime(latestLog.started_at)}</span>
            </div>
            {latestLog.finished_at && (
              <div className="sync-log-stat">
                <CalendarClock size={14} />
                <span>结束时间</span>
                <span>{formatDateTime(latestLog.finished_at)}</span>
              </div>
            )}
            {latestLog.error_message && (
              <div className="error-message" style={{ marginTop: "var(--space-3)" }}>
                <XCircle size={14} />
                {latestLog.error_message}
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="empty-state" style={{ paddingTop: "var(--space-4)" }}>
          <Clock size={36} />
          <p>暂无同步记录</p>
          <p className="empty-hint">点击下方按钮执行首次同步</p>
        </div>
      )}

    </div>
  );
}
