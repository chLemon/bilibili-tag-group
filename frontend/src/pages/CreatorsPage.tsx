/**
 * CreatorsPage：UP 主管理页面。
 * 展示统计摘要、已添加的 UP 主列表，支持添加、编辑、按标签筛选。
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { Creator } from "../api/client";
import {
  Plus,
  ListPlus,
  Loader2,
  AlertCircle,
  RefreshCw,
  Inbox,
  ExternalLink,
  Pencil,
  Trash2,
  X,
  User,
  Filter,
  Users,
  Hash,
  Video,
  Play,
  Film,
} from "lucide-react";
import CreatorForm from "../components/CreatorForm";
import BatchImportModal from "../components/BatchImportModal";
import ConfirmDialog from "../components/ConfirmDialog";
import { useCreators } from "../hooks/useCreators";
import { displayName } from "../utils/format";
import { formatRelativeTime } from "../utils/time";

type FormMode =
  | { type: "none" }
  | { type: "add" }
  | { type: "edit"; creator: Creator };

export default function CreatorsPage() {
  const {
    tags,
    loading,
    loadError,
    submitError,
    submitting,
    filterTagId,
    setFilterTagId,
    filteredCreators,
    creators,
    totalUnwatched,
    addCreator,
    editCreator,
    removeCreator,
    appendCreators,
    clearSubmitError,
  } = useCreators();

  const [formMode, setFormMode] = useState<FormMode>({ type: "none" });
  const [showBatchModal, setShowBatchModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Creator | null>(null);

  if (loading) {
    return (
      <div className="loading-state">
        <Loader2 size={20} className="spinner" /> 加载中…
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="error-message">
        <AlertCircle size={16} />
        加载失败：{loadError}
        <button
          className="btn btn-outline btn-sm"
          onClick={() => window.location.reload()}
        >
          <RefreshCw size={12} /> 重试
        </button>
      </div>
    );
  }

  const isModalOpen = formMode.type !== "none";

  function closeModal() {
    setFormMode({ type: "none" });
    clearSubmitError();
  }

  async function handleSubmit(values: {
    name: string;
    profile_url: string;
    avatar_url?: string;
    alias?: string;
    tag_ids: number[];
  }) {
    const ok =
      formMode.type === "add"
        ? await addCreator(values)
        : formMode.type === "edit"
          ? await editCreator(formMode.creator.id, values)
          : false;
    if (ok) setFormMode({ type: "none" });
  }

  return (
    <div>
      {/* 页面标题 */}
      <div className="page-header">
        <h2>UP 主管理</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn btn-primary"
            onClick={() => setFormMode({ type: "add" })}
          >
            <Plus size={16} /> 添加 UP 主
          </button>
          <button
            className="btn btn-outline"
            onClick={() => setShowBatchModal(true)}
          >
            <ListPlus size={16} /> 批量添加
          </button>
        </div>
      </div>

      {/* 统计摘要栏 */}
      <div className="stats-bar">
        <div className="stat-card">
          <div className="stat-card-icon stat-card-icon-pink">
            <Users size={18} />
          </div>
          <div className="stat-card-body">
            <div className="stat-card-value">{creators.length}</div>
            <div className="stat-card-label">UP 主总数</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card-icon stat-card-icon-blue">
            <Hash size={18} />
          </div>
          <div className="stat-card-body">
            <div className="stat-card-value">{tags.length}</div>
            <div className="stat-card-label">标签总数</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card-icon stat-card-icon-orange">
            <Play size={18} />
          </div>
          <div className="stat-card-body">
            <div className="stat-card-value">{totalUnwatched}</div>
            <div className="stat-card-label">未看视频</div>
          </div>
        </div>
      </div>

      {/* 标签筛选栏 */}
      {tags.length > 0 && (
        <div className="filter-bar">
          <span className="filter-bar-label">
            <Filter size={13} />
            筛选
          </span>
          <button
            className={`filter-chip${filterTagId === null ? " filter-chip-active" : ""}`}
            onClick={() => setFilterTagId(null)}
          >
            全部
          </button>
          {tags.map((tag) => (
            <button
              key={tag.id}
              className={`filter-chip${filterTagId === tag.id ? " filter-chip-active" : ""}`}
              onClick={() =>
                setFilterTagId(tag.id === filterTagId ? null : tag.id)
              }
            >
              {tag.name}
            </button>
          ))}
          <span className="filter-count">
            {filteredCreators.length} 个 UP 主
          </span>
        </div>
      )}

      {/* UP 主列表 */}
      {filteredCreators.length === 0 ? (
        <div className={creators.length === 0 ? "empty-state" : "empty-state-filter"}>
          {creators.length === 0 ? (
            <>
              <Inbox size={40} />
              <p>暂无 UP 主</p>
              <p className="empty-hint">点击上方「添加 UP 主」按钮开始添加</p>
            </>
          ) : (
            <>
              <Filter size={40} />
              <p>该标签下暂无 UP 主</p>
              <p className="empty-hint">尝试切换其他标签或清除筛选</p>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => setFilterTagId(null)}
              >
                清除筛选
              </button>
            </>
          )}
        </div>
      ) : (
        <div className="creator-list">
          {filteredCreators.map((c) => (
            <div key={c.id} className="creator-card">
              {/* 头像 */}
              <div className="creator-avatar">
                {c.avatar_url ? (
                  <img
                    src={c.avatar_url}
                    alt={c.name}
                    className="creator-avatar-img"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <span className="creator-avatar-placeholder">
                    <User size={18} />
                  </span>
                )}
              </div>

              {/* 主信息区 */}
              <div className="creator-card-main">
                <div className="creator-card-header">
                  <a
                    href={c.profile_url}
                    target="_blank"
                    rel="noreferrer"
                    className="creator-card-identity"
                    title={c.profile_url}
                  >
                    <span className="creator-card-name">{displayName(c)}</span>
                    <span className="creator-card-url">{c.profile_url}</span>
                    <ExternalLink size={12} className="creator-card-ext-link" />
                  </a>
                </div>

                <div className="creator-card-stats">
                  <span className="creator-card-stat">
                    <Video size={12} />
                    {c.video_count} 个视频
                  </span>
                  <span className="creator-card-stat-dot" />
                  <span className="creator-card-stat">
                    <Film size={12} />
                    已同步 {c.synced_video_count}
                  </span>
                  {c.unwatched_count > 0 && (
                    <>
                      <span className="creator-card-stat-dot" />
                      <span className="creator-card-stat creator-card-unwatched">
                        <Play size={12} />
                        {c.unwatched_count} 未看
                      </span>
                    </>
                  )}
                  {c.last_synced_at && (
                    <>
                      <span className="creator-card-stat-dot" />
                      <span className="creator-card-stat">
                        <RefreshCw size={11} />
                        {formatRelativeTime(c.last_synced_at)}
                      </span>
                    </>
                  )}
                </div>

                <div className="creator-card-tags">
                  {c.tag_ids.length > 0 ? (
                    c.tag_ids.map((tid) => (
                      <span key={tid} className="badge badge-info">
                        {tags.find((t) => t.id === tid)?.name ?? `#${tid}`}
                      </span>
                    ))
                  ) : (
                    <span className="text-muted text-sm">无标签</span>
                  )}
                </div>
              </div>

              {/* 操作按钮 */}
              <div className="creator-card-actions">
                <Link to={`/creators/${c.id}`} className="btn-edit">
                  <Film size={12} />
                  视频
                </Link>
                <button
                  className="btn-edit"
                  onClick={() => setFormMode({ type: "edit", creator: c })}
                >
                  <Pencil size={12} />
                  编辑
                </button>
                <button
                  className="btn-edit"
                  onClick={() => setDeleteTarget(c)}
                >
                  <Trash2 size={12} />
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal：添加/编辑 UP 主 */}
      {isModalOpen && (
        <div
          className="modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeModal();
          }}
        >
          <div className="modal-content">
            <div className="modal-header">
              <h3>
                {formMode.type === "add"
                  ? "添加 UP 主"
                  : `编辑：${formMode.type === "edit" ? displayName(formMode.creator) : ""}`}
              </h3>
              <button
                className="modal-close"
                onClick={closeModal}
                title="关闭 (Esc)"
              >
                <X size={18} />
              </button>
            </div>
            {submitError && (
              <div className="error-message" style={{ margin: "0 var(--space-4)" }}>
                <AlertCircle size={16} />
                提交失败：{submitError}
              </div>
            )}
            <CreatorForm
              initialValues={
                formMode.type === "edit"
                  ? {
                      name: formMode.creator.name,
                      profile_url: formMode.creator.profile_url,
                      avatar_url: formMode.creator.avatar_url ?? undefined,
                      alias: formMode.creator.alias ?? undefined,
                      tag_ids: formMode.creator.tag_ids,
                    }
                  : undefined
              }
              tags={tags}
              onSubmit={handleSubmit}
              onCancel={closeModal}
              submitting={submitting}
            />
          </div>
        </div>
      )}

      {/* 批量导入弹窗 */}
      {showBatchModal && (
        <BatchImportModal
          onClose={() => setShowBatchModal(false)}
          onSuccess={(newCreators) => {
            appendCreators(newCreators);
            setShowBatchModal(false);
          }}
        />
      )}

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <ConfirmDialog
          title="删除 UP 主"
          message={`删除 UP 主「${displayName(deleteTarget)}」？其视频与观看记录将一并删除。`}
          confirmText="删除"
          danger
          onConfirm={async () => {
            await removeCreator(deleteTarget.id);
            setDeleteTarget(null);
          }}
          onClose={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
