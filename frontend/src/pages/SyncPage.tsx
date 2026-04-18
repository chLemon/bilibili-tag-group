/**
 * SyncPage：同步状态页面。
 * 展示最近一次全量同步日志，以及手动触发全量同步的入口。
 */
import { useEffect, useState } from "react";
import {
  fetchLatestSync,
  fetchSyncSettings,
  runSync,
  SyncLog,
  SyncSettings,
} from "../api/client";
import SyncStatusPanel from "../components/SyncStatusPanel";

export default function SyncPage() {
  const [latestLog, setLatestLog] = useState<SyncLog | null>(null);
  const [settings, setSettings] = useState<SyncSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([fetchLatestSync(), fetchSyncSettings()])
      .then(([log, cfg]) => {
        setLatestLog(log);
        setSettings(cfg);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  /** 手动触发全量同步，完成后刷新日志 */
  async function handleRunSync() {
    setSyncing(true);
    setError(null);
    try {
      const log = await runSync();
      setLatestLog(log);
    } catch (err) {
      setError(String(err));
    } finally {
      setSyncing(false);
    }
  }

  if (loading) return <p>加载同步信息中…</p>;

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>同步状态</h2>
      {error && (
        <p style={{ color: "red", marginBottom: 12 }}>错误：{error}</p>
      )}
      <SyncStatusPanel
        latestLog={latestLog}
        settings={settings}
        syncing={syncing}
        onRunSync={handleRunSync}
      />
    </div>
  );
}
