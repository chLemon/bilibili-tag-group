/**
 * VideoCard：展示单个视频的卡片组件。
 * 包含标题、UP 主、时长、发布时间，以及"标记已看"按钮。
 */
import { Video } from "../api/client";

/** 将秒数格式化为 mm:ss 或 h:mm:ss */
function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** 将 ISO 时间字符串格式化为本地日期 */
function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("zh-CN");
}

interface VideoCardProps {
  video: Video;
  /** 点击"标记已看"时的回调 */
  onMarkWatched: (videoId: number) => void;
}

export default function VideoCard({ video, onMarkWatched }: VideoCardProps) {
  return (
    <div
      style={{
        border: "1px solid #ddd",
        borderRadius: 6,
        padding: "12px 16px",
        marginBottom: 8,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: 8,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* 视频标题，点击跳转到 B 站 */}
        <a
          href={video.video_url}
          target="_blank"
          rel="noreferrer"
          style={{ fontWeight: 600, wordBreak: "break-word" }}
        >
          {video.title}
        </a>
        <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>
          <span>{video.creator_name}</span>
          <span style={{ margin: "0 6px" }}>·</span>
          <span>{formatDuration(video.duration_seconds)}</span>
          <span style={{ margin: "0 6px" }}>·</span>
          <span>{formatDate(video.published_at)}</span>
        </div>
      </div>
      <button
        onClick={() => onMarkWatched(video.id)}
        style={{
          flexShrink: 0,
          padding: "4px 10px",
          cursor: "pointer",
          fontSize: 12,
        }}
      >
        已看
      </button>
    </div>
  );
}
