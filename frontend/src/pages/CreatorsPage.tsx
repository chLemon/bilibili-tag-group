/**
 * CreatorsPage：UP 主管理页面。
 * 展示统计摘要、已添加的 UP 主列表，支持添加、编辑、按标签筛选。
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchCreators,
  fetchTags,
  createCreator,
  updateCreator,
  Creator,
  Tag,
} from "../api/client";
import {
  Plus,
  Loader2,
  AlertCircle,
  RefreshCw,
  Inbox,
  ExternalLink,
  Pencil,
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

type FormMode =
  | { type: "none" }
  | { type: "add" }
  | { type: "edit"; creator: Creator };

export default function CreatorsPage() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [formMode, setFormMode] = useState<FormMode>({ type: "none" });
  const [submitting, setSubmitting] = useState(false);
  const [filterTagId, setFilterTagId] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([fetchCreators(), fetchTags()])
      .then(([c, t]) => {
        setCreators(c);
        setTags(t);
      })
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const filteredCreators = useMemo(() => {
    if (filterTagId === null) return creators;
    return creators.filter((c) => c.tag_ids.includes(filterTagId));
  }, [creators, filterTagId]);

  const totalUnwatched = useMemo(
    () => creators.reduce((sum, c) => sum + c.unwatched_count, 0),
    [creators]
  );

  async function handleAdd(values: {
    name: string;
    profile_url: string;
    avatar_url?: string;
    alias?: string;
    tag_ids: number[];
  }) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createCreator({
        name: values.name,
        profile_url: values.profile_url,
        avatar_url: values.avatar_url,
        alias: values.alias,
        tag_ids: values.tag_ids,
      });
      setCreators((prev) => [...prev, created]);
      setFormMode({ type: "none" });
    } catch (err) {
      setSubmitError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEdit(
    creatorId: number,
    values: {
      name: string;
      profile_url: string;
      alias?: string;
      tag_ids: number[];
    }
  ) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const updated = await updateCreator(creatorId, {
        name: values.name,
        alias: values.alias,
        tag_ids: values.tag_ids,
      });
      setCreators((prev) =>
        prev.map((c) => (c.id === creatorId ? updated : c))
      );
      setFormMode({ type: "none" });
    } catch (err) {
      setSubmitError(String(err));
    } finally {
      setSubmitting(false);
    }
  }

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

  return (
    <div>
      {/* 页面标题 */}
      <div className="page-header">
        <h2>UP 主管理</h2>
        <button
          className="btn btn-primary"
          onClick={() => setFormMode({ type: "add" })}
        >
          <Plus size={16} /> 添加 UP 主
        </button>
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

      {submitError && (
        <div className="error-message">
          <AlertCircle size={16} />
          提交失败：{submitError}
        </div>
      )}

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
                    className="creator-card-name"
                    title={c.profile_url}
                  >
                    {displayName(c)}
                  </a>
                  <ExternalLink size={12} className="creator-card-ext-link" />
                  <span className="creator-card-url" title={c.profile_url}>
                    {c.profile_url}
                  </span>
                </div>

                <div className="creator-card-stats">
                  <span className="creator-card-stat">
                    <Video size={12} />
                    {c.video_count} 视频
                  </span>
                  {c.unwatched_count > 0 && (
                    <>
                      <span className="creator-card-stat-dot" />
                      <span className="creator-card-stat creator-card-unwatched">
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
            if (e.target === e.currentTarget) setFormMode({ type: "none" });
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
                onClick={() => setFormMode({ type: "none" })}
                title="关闭 (Esc)"
              >
                <X size={18} />
              </button>
            </div>
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
              onSubmit={(values) => {
                if (formMode.type === "add") {
                  handleAdd(values);
                } else if (formMode.type === "edit") {
                  handleEdit(formMode.creator.id, values);
                }
              }}
              onCancel={() => setFormMode({ type: "none" })}
              submitting={submitting}
            />
          </div>
        </div>
      )}
    </div>
  );
}

/** 格式化 UP 主显示名称：有别名时显示「别名（原名）」，否则只显示原名 */
function displayName(c: Creator): string {
  return c.alias ? `${c.alias}（${c.name}）` : c.name;
}

/** 将 ISO 时间字符串转换为相对时间描述 */
function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso + "Z").getTime();
  const diffMs = now - then;
  if (diffMs < 0) return "刚刚";

  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;

  const months = Math.floor(days / 30);
  return `${months} 个月前`;
}
