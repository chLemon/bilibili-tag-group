/**
 * SyncStatusPanel：展示最近一次同步结果与手动触发入口。
 */
import { SyncLog, SyncSettings } from "../api/client";

interface SyncStatusPanelProps {
  /** 最近同步日志（null 表示尚无记录） */
  latestLog: SyncLog | null;
  /** 调度配置 */
  settings: SyncSettings | null;
  /** 是否正在执行同步 */
  syncing: boolean;
  /** 点击"立即同步"时的回调 */
  onRunSync: () => void;
}

/** 格式化 ISO 时间字符串为本地时间 */
function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-CN");
}

/** 根据状态返回中文标签 */
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
  syncing,
  onRunSync,
}: SyncStatusPanelProps) {
  return (
    <div>
      {/* 调度配置信息 */}
      {settings && (
        <div
          style={{
            marginBottom: 16,
            padding: "10px 14px",
            background: "#f5f5f5",
            borderRadius: 6,
            fontSize: 13,
          }}
        >
          <strong>定时同步：</strong>
          {settings.enabled
            ? `已启用，每 ${settings.interval_minutes} 分钟执行一次`
            : "未启用"}
        </div>
      )}

      {/* 最近同步日志 */}
      {latestLog ? (
        <div
          style={{
            padding: "12px 16px",
            border: "1px solid #ddd",
            borderRadius: 6,
            marginBottom: 16,
          }}
        >
          <div style={{ marginBottom: 6, fontWeight: 600 }}>最近同步结果</div>
          <div style={{ fontSize: 13, lineHeight: 1.8 }}>
            <div>
              状态：
              <span
                style={{
                  color: latestLog.status === "success" ? "green" : "red",
                  fontWeight: 600,
                }}
              >
                {statusLabel(latestLog.status)}
              </span>
            </div>
            <div>新增视频：{latestLog.new_videos} 条</div>
            <div>开始时间：{formatDateTime(latestLog.started_at)}</div>
            {latestLog.finished_at && (
              <div>结束时间：{formatDateTime(latestLog.finished_at)}</div>
            )}
            {latestLog.error_message && (
              <div style={{ color: "red" }}>错误：{latestLog.error_message}</div>
            )}
          </div>
        </div>
      ) : (
        <p style={{ color: "#888", marginBottom: 16 }}>暂无同步记录。</p>
      )}

      {/* 手动触发 */}
      <button onClick={onRunSync} disabled={syncing}>
        {syncing ? "同步中…" : "立即同步"}
      </button>
    </div>
  );
}
