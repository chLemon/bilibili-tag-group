/**
 * CreatorsPage：UP 主管理页面。
 * 展示已添加的 UP 主列表，支持添加、编辑、同步、按标签筛选。
 */
import { Fragment, useEffect, useMemo, useState } from "react";
import {
  fetchCreators,
  fetchTags,
  createCreator,
  updateCreator,
  syncCreator,
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
  CheckCircle2,
  XCircle,
  X,
  User,
  Filter,
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
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
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

  /** 根据当前筛选标签过滤 UP 主 */
  const filteredCreators = useMemo(() => {
    if (filterTagId === null) return creators;
    return creators.filter((c) => c.tag_ids.includes(filterTagId));
  }, [creators, filterTagId]);

  async function handleAdd(values: {
    name: string;
    profile_url: string;
    avatar_url?: string;
    enabled: boolean;
    tag_ids: number[];
  }) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createCreator({
        name: values.name,
        profile_url: values.profile_url,
        avatar_url: values.avatar_url,
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
      enabled: boolean;
      tag_ids: number[];
    }
  ) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const updated = await updateCreator(creatorId, {
        name: values.name,
        enabled: values.enabled,
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

  async function handleSync(creatorId: number) {
    setSyncingId(creatorId);
    setSyncMsg(null);
    try {
      const result = await syncCreator(creatorId);
      setSyncMsg(`同步完成，新增 ${result.new_videos} 条视频。`);
    } catch (err) {
      setSyncMsg(`同步失败：${err}`);
    } finally {
      setSyncingId(null);
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
        <button className="btn btn-outline btn-sm" onClick={() => window.location.reload()}>
          <RefreshCw size={12} /> 重试
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h2>UP 主管理</h2>
        <button className="btn btn-primary" onClick={() => setFormMode({ type: "add" })}>
          <Plus size={16} /> 添加 UP 主
        </button>
      </div>

      {syncMsg && (
        <div className="status-banner status-banner-success">
          <CheckCircle2 size={16} />
          {syncMsg}
        </div>
      )}
      {submitError && (
        <div className="error-message">
          <AlertCircle size={16} />
          提交失败：{submitError}
        </div>
      )}

      {/* 标签筛选栏 */}
      {tags.length > 0 && (
        <div className="filter-bar">
          <Filter size={14} />
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
              onClick={() => setFilterTagId(tag.id === filterTagId ? null : tag.id)}
            >
              {tag.name}
            </button>
          ))}
          {filterTagId !== null && (
            <span className="text-muted text-sm">
              {filteredCreators.length} 个 UP 主
            </span>
          )}
        </div>
      )}

      {/* 添加表单 */}
      {formMode.type === "add" && (
        <div className="card" style={{ padding: "var(--space-4)", marginBottom: "var(--space-4)" }}>
          <h4 className="mb-3">添加 UP 主</h4>
          <CreatorForm
            tags={tags}
            onSubmit={handleAdd}
            onCancel={() => setFormMode({ type: "none" })}
            submitting={submitting}
          />
        </div>
      )}

      {/* UP 主列表 */}
      {filteredCreators.length === 0 ? (
        <div className="empty-state" style={{ paddingTop: 48 }}>
          <Inbox size={40} />
          <p>{creators.length === 0 ? "暂无 UP 主" : "该标签下暂无 UP 主"}</p>
          <p className="empty-hint">
            {creators.length === 0 ? "点击上方按钮添加第一个 UP 主" : "尝试切换筛选标签"}
          </p>
        </div>
      ) : (
        <div className="creator-list">
          {filteredCreators.map((c) => (
            <Fragment key={c.id}>
              <div className="creator-row">
                {/* 头像 */}
                <div className="creator-avatar">
                  {c.avatar_url ? (
                    <img src={c.avatar_url} alt={c.name} className="creator-avatar-img" />
                  ) : (
                    <span className="creator-avatar-placeholder">
                      <User size={18} />
                    </span>
                  )}
                </div>

                <div className="creator-row-main">
                  <div className="creator-name">
                    <a href={c.profile_url} target="_blank" rel="noreferrer" className="creator-name-link">
                      {c.name}
                      <ExternalLink size={12} />
                    </a>
                    <span className="creator-profile-url" title={c.profile_url}>
                      {c.profile_url}
                    </span>
                  </div>
                  <div className="creator-tags">
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
                <div className="creator-row-actions">
                  {c.enabled ? (
                    <span className="badge badge-success">
                      <CheckCircle2 size={11} /> 启用
                    </span>
                  ) : (
                    <span className="badge badge-muted">
                      <XCircle size={11} /> 停用
                    </span>
                  )}
                  <button
                    className="btn btn-outline btn-sm"
                    onClick={() => setFormMode({ type: "edit", creator: c })}
                  >
                    <Pencil size={12} />
                    编辑
                  </button>
                  <button
                    className="btn btn-outline btn-sm"
                    onClick={() => handleSync(c.id)}
                    disabled={syncingId === c.id}
                  >
                    {syncingId === c.id ? (
                      <Loader2 size={12} className="spinner" />
                    ) : (
                      <RefreshCw size={12} />
                    )}
                    {syncingId === c.id ? "同步中…" : "同步"}
                  </button>
                </div>
              </div>

              {/* 编辑表单内联 */}
              {formMode.type === "edit" && formMode.creator.id === c.id && (
                <div className="edit-card">
                  <button
                    type="button"
                    className="edit-card-close"
                    onClick={() => setFormMode({ type: "none" })}
                    title="关闭 (Esc)"
                  >
                    <X size={22} />
                  </button>
                  <h4 className="mb-3">编辑：{c.name}</h4>
                  <CreatorForm
                    initialValues={{
                      name: c.name,
                      profile_url: c.profile_url,
                      avatar_url: c.avatar_url ?? undefined,
                      enabled: c.enabled,
                      tag_ids: c.tag_ids,
                    }}
                    tags={tags}
                    onSubmit={(values) => handleEdit(c.id, values)}
                    onCancel={() => setFormMode({ type: "none" })}
                    submitting={submitting}
                  />
                </div>
              )}
            </Fragment>
          ))}
        </div>
      )}
    </div>
  );
}
