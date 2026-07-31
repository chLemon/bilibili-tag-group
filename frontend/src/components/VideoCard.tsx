/**
 * VideoCard：展示单个视频的卡片组件。
 */
import { useEffect, useRef, useState } from "react";
import { Video } from "../api/client";
import { Clock, Calendar, ExternalLink, Eye, EyeOff, Image } from "lucide-react";

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("zh-CN");
}

interface VideoCardProps {
  video: Video;
  onMarkWatched: (videoId: number) => void;
  onMarkIgnored: (videoId: number) => void;
}

export default function VideoCard({ video, onMarkWatched, onMarkIgnored }: VideoCardProps) {
  const [removing, setRemoving] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 卸载时清理未触发的定时器，避免组件移除后仍回调
  useEffect(() => {
    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
    };
  }, []);

  function handleAction(callback: (id: number) => void) {
    setRemoving(true);
    timerRef.current = setTimeout(() => callback(video.id), 200);
  }

  return (
    <div className={`video-card${removing ? " video-card-removing" : ""}`}>
      <div className="video-card-accent" />
      <a
        href={video.video_url}
        target="_blank"
        rel="noreferrer"
        className="video-card-cover"
      >
        {video.cover_url ? (
          <img src={video.cover_url} alt={video.title} loading="lazy" referrerPolicy="no-referrer" />
        ) : (
          <span className="video-card-cover-placeholder">
            <Image size={20} />
          </span>
        )}
      </a>
      <div className="video-card-body">
        <div className="video-card-info">
          <a
            href={video.video_url}
            target="_blank"
            rel="noreferrer"
            className="video-card-title"
            title={video.title}
          >
            {video.title}
            <ExternalLink size={12} className="video-card-title-icon" />
          </a>
          <div className="video-card-meta">
            <span className="video-card-meta-item">
              {video.creator_avatar_url ? (
                <img
                  src={video.creator_avatar_url}
                  alt={video.creator_name}
                  className="video-card-creator-avatar"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <span className="video-card-creator-avatar video-card-creator-avatar-placeholder">
                  {video.creator_name.charAt(0)}
                </span>
              )}
              {video.creator_alias ? `${video.creator_alias}（${video.creator_name}）` : video.creator_name}
            </span>
            <span className="video-card-meta-sep">·</span>
            <span className="video-card-meta-item">
              <Clock size={12} />
              {formatDuration(video.duration_seconds)}
            </span>
            <span className="video-card-meta-sep">·</span>
            <span className="video-card-meta-item">
              <Calendar size={12} />
              {formatDate(video.published_at)}
            </span>
          </div>
        </div>
        <div className="video-card-actions" style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          <button
            onClick={() => handleAction(onMarkWatched)}
            className="btn btn-sm btn-primary"
          >
            <Eye size={13} />
            已看
          </button>
          <button
            onClick={() => handleAction(onMarkIgnored)}
            className="btn btn-sm btn-muted"
          >
            <EyeOff size={13} />
            不看
          </button>
        </div>
      </div>
    </div>
  );
}
