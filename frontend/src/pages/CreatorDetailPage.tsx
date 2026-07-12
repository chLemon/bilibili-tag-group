/**
 * CreatorDetailPage：UP 主视频详情页。
 * 展示该 UP 主的所有视频，支持标记已看/未看切换。
 */
import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  fetchCreator,
  fetchCreatorVideos,
  fetchTags,
  updateStatus,
  batchUpdateCreatorVideos,
  Creator,
  Tag,
  VideoDetail,
} from "../api/client";
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  Inbox,
  ExternalLink,
  User,
  Video,
  Clock,
  Calendar,
  Eye,
  EyeOff,
  ArrowLeft,
  Play,
  Image,
  Film,
  CheckCheck,
  Undo2,
} from "lucide-react";

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

function displayName(c: Creator): string {
  return c.alias ? `${c.alias}（${c.name}）` : c.name;
}

export default function CreatorDetailPage() {
  const { creatorId } = useParams<{ creatorId: string }>();
  const id = Number(creatorId);

  const [creator, setCreator] = useState<Creator | null>(null);
  const [videos, setVideos] = useState<VideoDetail[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<number | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);

  async function handleBatchUpdate(status: number, label: string) {
    if (!window.confirm(`确定将该 UP 主的所有视频标记为${label}？`)) return;
    setBatchLoading(true);
    try {
      await batchUpdateCreatorVideos(id, status);
      setVideos((prev) =>
        prev.map((v) => ({ ...v, status }))
      );
      if (creator) {
        setCreator({
          ...creator,
          unwatched_count: status === 0 ? creator.video_count : 0,
        });
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setBatchLoading(false);
    }
  }

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([fetchCreator(id), fetchCreatorVideos(id), fetchTags()])
      .then(([c, v, t]) => {
        setCreator(c);
        setVideos(v);
        setTags(t);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleSetStatus(video: VideoDetail, newStatus: number) {
    setToggling(video.id);
    try {
      await updateStatus(video.id, newStatus);
      const oldStatus = video.status;
      setVideos((prev) =>
        prev.map((v) =>
          v.id === video.id ? { ...v, status: newStatus } : v
        )
      );
      if (creator) {
        // 只有进出"未看"状态才影响 unwatched_count
        const wasUnwatched = oldStatus === 0;
        const isUnwatched = newStatus === 0;
        if (wasUnwatched !== isUnwatched) {
          setCreator({
            ...creator,
            unwatched_count: creator.unwatched_count + (isUnwatched ? 1 : -1),
          });
        }
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setToggling(null);
    }
  }

  if (loading) {
    return (
      <div className="loading-state">
        <Loader2 size={20} className="spinner" /> 加载中…
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-message">
        <AlertCircle size={16} />
        加载失败：{error}
        <button className="btn btn-outline btn-sm" onClick={() => window.location.reload()}>
          <RefreshCw size={12} /> 重试
        </button>
      </div>
    );
  }

  if (!creator) {
    return (
      <div className="empty-state">
        <Inbox size={40} />
        <p>UP 主不存在</p>
        <Link to="/creators" className="btn btn-outline btn-sm mt-3">
          返回 UP 主管理
        </Link>
      </div>
    );
  }

  const watchedCount = videos.filter((v) => v.status === 1).length;
  const ignoredCount = videos.filter((v) => v.status === 2).length;

  return (
    <div>
      {/* 返回链接 */}
      <Link to="/creators" className="detail-back">
        <ArrowLeft size={16} />
        返回 UP 主管理
      </Link>

      {/* UP 主信息头部 */}
      <div className="detail-header">
        <div className="creator-avatar">
          {creator.avatar_url ? (
            <img
              src={creator.avatar_url}
              alt={creator.name}
              className="creator-avatar-img detail-avatar-lg"
              referrerPolicy="no-referrer"
            />
          ) : (
            <span className="creator-avatar-placeholder detail-avatar-lg">
              <User size={28} />
            </span>
          )}
        </div>
        <div className="detail-header-info">
          <h2>{displayName(creator)}</h2>
          <a
            href={creator.profile_url}
            target="_blank"
            rel="noreferrer"
            className="creator-card-url"
            style={{ fontSize: 13, marginTop: 4 }}
          >
            {creator.profile_url}
            <ExternalLink size={11} style={{ marginLeft: 4 }} />
          </a>
          <div className="detail-header-stats">
            <span className="creator-card-stat">
              <Video size={13} />
              {creator.video_count} 个视频
            </span>
            <span className="creator-card-stat-dot" />
            <span className="creator-card-stat">
              <Film size={13} />
              已同步 {creator.synced_video_count}
            </span>
            <span className="creator-card-stat-dot" />
            <span className="creator-card-stat creator-card-unwatched">
              <Play size={13} />
              {creator.unwatched_count} 未看
            </span>
            <span className="creator-card-stat-dot" />
            <span className="creator-card-stat">
              <Eye size={13} />
              {watchedCount} 已看
            </span>
            <span className="creator-card-stat-dot" />
            <span className="creator-card-stat">
              <EyeOff size={13} />
              {ignoredCount} 不看
            </span>
          </div>
          <div className="creator-card-tags" style={{ marginTop: 6 }}>
            {creator.tag_ids.length > 0 ? (
              creator.tag_ids.map((tid) => (
                <span key={tid} className="badge badge-info">
                  {tags.find((t) => t.id === tid)?.name ?? `#${tid}`}
                </span>
              ))
            ) : (
              <span className="text-muted text-sm">无标签</span>
            )}
          </div>
        </div>
        {videos.length > 0 && (
          <div className="detail-header-actions">
            <button
              className="btn btn-sm btn-primary"
              disabled={batchLoading}
              onClick={() => handleBatchUpdate(1, "已看")}
            >
              {batchLoading ? <Loader2 size={14} className="spinner" /> : <CheckCheck size={14} />}
              一键已看
            </button>
            <button
              className="btn btn-sm btn-danger"
              disabled={batchLoading}
              onClick={() => handleBatchUpdate(2, "不看")}
            >
              {batchLoading ? <Loader2 size={14} className="spinner" /> : <EyeOff size={14} />}
              一键不看
            </button>
            <button
              className="btn btn-sm btn-info"
              disabled={batchLoading}
              onClick={() => handleBatchUpdate(0, "未看")}
            >
              {batchLoading ? <Loader2 size={14} className="spinner" /> : <Undo2 size={14} />}
              一键未看
            </button>
          </div>
        )}
      </div>

      {/* 视频列表 */}
      {videos.length === 0 ? (
        <div className="empty-state">
          <Inbox size={36} />
          <p>暂无视频</p>
          <p className="empty-hint">同步后视频会展示在这里</p>
        </div>
      ) : (
        <div className="creator-list">
          {videos.map((v) => (
            <div
              key={v.id}
              className={`video-detail-row${v.status !== 0 ? " video-detail-row-watched" : ""}`}
            >
              <a
                href={v.video_url}
                target="_blank"
                rel="noreferrer"
                className="video-card-cover"
              >
                {v.cover_url ? (
                  <img src={v.cover_url} alt={v.title} loading="lazy" referrerPolicy="no-referrer" />
                ) : (
                  <span className="video-card-cover-placeholder">
                    <Image size={20} />
                  </span>
                )}
              </a>
              <div className="video-detail-info">
                <a
                  href={v.video_url}
                  target="_blank"
                  rel="noreferrer"
                  className="creator-card-name"
                  title={v.title}
                >
                  {v.title}
                  <ExternalLink size={11} style={{ marginLeft: 4, opacity: 0.4 }} />
                </a>
                <div className="creator-card-stats" style={{ marginTop: 2 }}>
                  <span className="creator-card-stat">
                    <Clock size={11} />
                    {formatDuration(v.duration_seconds)}
                  </span>
                  <span className="creator-card-stat-dot" />
                  <span className="creator-card-stat">
                    <Calendar size={11} />
                    {formatDate(v.published_at)}
                  </span>
                  {v.status === 1 && (
                    <>
                      <span className="creator-card-stat-dot" />
                      <span className="creator-card-stat" style={{ color: "var(--color-success)" }}>
                        <Eye size={11} />
                        已看
                      </span>
                    </>
                  )}
                  {v.status === 2 && (
                    <>
                      <span className="creator-card-stat-dot" />
                      <span className="creator-card-stat" style={{ color: "var(--color-text-muted)" }}>
                        <EyeOff size={11} />
                        不看
                      </span>
                    </>
                  )}
                </div>
              </div>
              <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                {v.status !== 1 && (
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={() => handleSetStatus(v, 1)}
                    disabled={toggling === v.id}
                  >
                    {toggling === v.id ? (
                      <Loader2 size={12} className="spinner" />
                    ) : (
                      <Eye size={12} />
                    )}
                    已看
                  </button>
                )}
                {v.status !== 2 && (
                  <button
                    className="btn btn-sm btn-outline"
                    onClick={() => handleSetStatus(v, 2)}
                    disabled={toggling === v.id}
                  >
                    {toggling === v.id ? (
                      <Loader2 size={12} className="spinner" />
                    ) : (
                      <EyeOff size={12} />
                    )}
                    不看
                  </button>
                )}
                {v.status !== 0 && (
                  <button
                    className="btn btn-sm btn-info"
                    onClick={() => handleSetStatus(v, 0)}
                    disabled={toggling === v.id}
                  >
                    未看
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
