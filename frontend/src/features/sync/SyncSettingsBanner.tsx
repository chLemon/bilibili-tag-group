/**
 * SyncSettingsBanner：展示定时同步的启用状态和间隔配置。
 */
import { Clock } from "lucide-react";
import { SyncSettings } from "../../api/client";

interface Props {
  settings: SyncSettings | null;
}

export default function SyncSettingsBanner({ settings }: Props) {
  if (!settings) return null;

  return (
    <div className="status-banner status-banner-info" style={{ marginBottom: "var(--space-4)" }}>
      <Clock size={18} />
      <div>
        <strong>定时同步：</strong>
        {settings.enabled
          ? `已启用，每 ${settings.interval_minutes} 分钟执行一次`
          : "未启用"}
      </div>
    </div>
  );
}
