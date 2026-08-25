/**
 * CreatorDetailPage：UP 主视频详情页。
 * 展示该 UP 主的所有视频，支持单个/一键标记已看、不看、未看。
 */
import { useState } from "react";
import { useParams, Link } from "react-router-dom";
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
import { useCreatorDetail } from "../hooks/useCreatorDetail";
import { displayName, formatDate, formatDuration } from "../utils/format";
import ConfirmDialog from "../components/ConfirmDialog";

/** 视频状态元信息：状态值 -> 文案与图标 */
const STATUS_META: Record<number, { label: string; Icon: typeof Play }> = {
  0: { label: "未看", Icon: Play },
  1: { label: "已看", Icon: Eye },
  2: { label: "不看", Icon: EyeOff },
};

export default function CreatorDetailPage() {
  const { creatorId } = useParams<{ creatorId: string }>();
  const id = Number(creatorId);

  const {
    creator,
    videos,
    tags,
    loading,
    error,
    toggling,
    batchLoading,
    setStatus,
    batchSetStatus,
  } = useCreatorDetail(id);

  const [batchConfirm, setBatchConfirm] = useState<
    { status: number; label: string } | null
  >(null);

  function handleBatchUpdate(status: number, label: string) {
    setBatchConfirm({ status, label });
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
              className="btn btn-sm btn-muted"
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
          {videos.map((v) => {
            const st = STATUS_META[v.status] ?? STATUS_META[0];
            return (
            <div
              key={v.id}
              className={`video-detail-row video-row-bg-${v.status}${v.status !== 0 ? " video-detail-row-watched" : ""}`}
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
                  <span className="creator-card-stat-dot" />
                  <span className={`creator-card-stat cover-block-text-${v.status}`}>
                    <st.Icon size={11} />
                    {st.label}
                  </span>
                </div>
              </div>
              <div style={{ display: "flex", gap: 4, flexShrink: 0, alignItems: "center" }}>
                {v.mark && <span className="video-card-mark">{v.mark}</span>}
                {v.status !== 1 && (
                  <button
                    className="btn btn-sm btn-primary"
                    onClick={() => setStatus(v, 1)}
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
                    className="btn btn-sm btn-muted"
                    onClick={() => setStatus(v, 2)}
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
                    onClick={() => setStatus(v, 0)}
                    disabled={toggling === v.id}
                  >
                    {toggling === v.id ? (
                      <Loader2 size={12} className="spinner" />
                    ) : (
                      <Undo2 size={12} />
                    )}
                    未看
                  </button>
                )}
              </div>
            </div>
            );
          })}
        </div>
      )}

      {batchConfirm && (
        <ConfirmDialog
          title="批量标记"
          message={`确定将该 UP 主的所有视频标记为${batchConfirm.label}？`}
          confirmText={batchConfirm.label}
          danger={batchConfirm.status === 2}
          onConfirm={async () => {
            await batchSetStatus(batchConfirm.status);
            setBatchConfirm(null);
          }}
          onClose={() => setBatchConfirm(null)}
        />
      )}
    </div>
  );
}
