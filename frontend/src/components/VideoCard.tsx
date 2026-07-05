/**
 * VideoCard：展示单个视频的卡片组件。
 */
import { useState } from "react";
import { Video } from "../api/client";
import { User, Clock, Calendar, ExternalLink, Eye } from "lucide-react";

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
}

export default function VideoCard({ video, onMarkWatched }: VideoCardProps) {
  const [removing, setRemoving] = useState(false);

  function handleMarkWatched() {
    setRemoving(true);
    setTimeout(() => onMarkWatched(video.id), 200);
  }

  return (
    <div className={`video-card${removing ? " video-card-removing" : ""}`}>
      <div className="video-card-accent" />
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
              <User size={12} />
              {video.creator_name}
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
        <button
          onClick={handleMarkWatched}
          className="btn btn-outline btn-sm"
          style={{ flexShrink: 0 }}
        >
          <Eye size={13} />
          已看
        </button>
      </div>
    </div>
  );
}
