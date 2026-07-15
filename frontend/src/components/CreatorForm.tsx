/**
 * CreatorForm：添加或编辑 UP 主的表单组件。
 * 添加模式：只填 URL，点击按钮自动获取名称和头像。
 * 编辑模式：名称和 URL 只读，可修改启用状态和标签。
 */
import { useEffect, useState } from "react";
import { Plus, AlertCircle, Loader2, Search, User } from "lucide-react";
import { Tag, createTag, resolveCreatorName } from "../api/client";

interface FormValues {
  name: string;
  profile_url: string;
  avatar_url?: string;
  alias?: string;
  tag_ids: number[];
}

interface CreatorFormProps {
  initialValues?: Partial<FormValues>;
  tags: Tag[];
  onSubmit: (values: FormValues) => void;
  onCancel: () => void;
  submitting?: boolean;
}

export default function CreatorForm({
  initialValues,
  tags,
  onSubmit,
  onCancel,
  submitting = false,
}: CreatorFormProps) {
  const isEditing = !!initialValues?.name;

  const [name, setName] = useState(initialValues?.name ?? "");
  const [alias, setAlias] = useState(initialValues?.alias ?? "");
  const [profileUrl, setProfileUrl] = useState(initialValues?.profile_url ?? "");
  const [avatarUrl, setAvatarUrl] = useState(initialValues?.avatar_url ?? "");
  const [tagIds, setTagIds] = useState<number[]>(initialValues?.tag_ids ?? []);
  const [localTags, setLocalTags] = useState<Tag[]>(tags);
  const [newTagName, setNewTagName] = useState("");
  const [tagCreating, setTagCreating] = useState(false);
  const [tagCreateError, setTagCreateError] = useState<string | null>(null);
  const [nameResolving, setNameResolving] = useState(false);
  const [nameResolveError, setNameResolveError] = useState<string | null>(null);

  useEffect(() => {
    setLocalTags(tags);
  }, [tags]);

  /** Esc 关闭表单 */
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  function toggleTag(id: number) {
    setTagIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  }

  async function handleCreateTag() {
    const trimmed = newTagName.trim();
    if (!trimmed) return;

    setTagCreating(true);
    setTagCreateError(null);
    try {
      const createdTag = await createTag({ name: trimmed });
      setLocalTags((prev) => [...prev, createdTag]);
      setTagIds((prev) => [...prev, createdTag.id]);
      setNewTagName("");
    } catch (error) {
      setTagCreateError(error instanceof Error ? error.message : "创建失败");
    } finally {
      setTagCreating(false);
    }
  }

  /** 从 B 站获取 UP 主名称和头像。支持完整 URL 或纯数字 UID。 */
  async function handleFetchInfo() {
    const trimmed = profileUrl.trim();
    if (!trimmed) return;

    const query = /^\d+$/.test(trimmed)
      ? `https://space.bilibili.com/${trimmed}`
      : trimmed;

    setNameResolving(true);
    setNameResolveError(null);
    try {
      const result = await resolveCreatorName(query);
      setName(result.name);
      if (result.avatar_url) setAvatarUrl(result.avatar_url);
    } catch (error) {
      setNameResolveError(
        error instanceof Error ? error.message : "获取昵称失败，请检查 URL 是否正确"
      );
    } finally {
      setNameResolving(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({ name, alias: alias || undefined, profile_url: profileUrl, avatar_url: avatarUrl || undefined, tag_ids: tagIds });
  }

  const canSubmit = !!name.trim() && !!profileUrl.trim();

  return (
    <form onSubmit={handleSubmit} className="creator-form">
      {/* 主页 URL */}
      <div className="form-field">
        <label className="form-label">主页 URL</label>
        {isEditing ? (
          <input
            className="input"
            value={profileUrl}
            readOnly
            disabled
          />
        ) : (
          <div className="form-url-row">
            <div style={{ flex: 1 }}>
              <input
                className="input"
                value={profileUrl}
                onChange={(e) => {
                  setProfileUrl(e.target.value);
                  setNameResolveError(null);
                  if (!name) setName("");
                }}
                required
                placeholder="https://space.bilibili.com/..."
              />
            </div>
            <button
              type="button"
              className="btn btn-outline"
              onClick={handleFetchInfo}
              disabled={!profileUrl.trim() || nameResolving}
            >
              {nameResolving ? (
                <Loader2 size={14} className="spinner" />
              ) : (
                <Search size={14} />
              )}
              {nameResolving ? "获取中…" : "获取信息"}
            </button>
          </div>
        )}
        {nameResolveError && (
          <p className="form-error"><AlertCircle size={12} /> {nameResolveError}</p>
        )}
      </div>

      {/* 名称 + 头像（添加模式下展示） */}
      <div className="form-field">
        <label className="form-label">名称</label>
        {name ? (
          <div className="form-name-display">
            {!isEditing && avatarUrl && (
              <img src={avatarUrl} alt={name} className="form-avatar-preview" referrerPolicy="no-referrer" />
            )}
            {!isEditing && !avatarUrl && (
              <span className="form-avatar-placeholder">
                <User size={18} />
              </span>
            )}
            <input
              className="input"
              value={name}
              readOnly
              disabled
            />
          </div>
        ) : (
          <p className="text-muted text-sm" style={{ padding: "7px 0" }}>
            {isEditing ? "无" : "请输入主页 URL 后点击「获取信息」自动填充"}
          </p>
        )}
      </div>

      {/* 别名 */}
      <div className="form-field">
        <label className="form-label">别名（可选）</label>
        <input
          className="input"
          value={alias}
          onChange={(e) => setAlias(e.target.value)}
          placeholder="便于识别的自定义名称"
        />
      </div>

      {/* 关联标签 */}
      <div className="form-field">
        <label className="form-label">关联标签</label>
        {localTags.length > 0 ? (
          <div className="form-tag-chips">
            {localTags.map((tag) => {
              const isSelected = tagIds.includes(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => toggleTag(tag.id)}
                  className={`form-tag-chip${isSelected ? " form-tag-chip-active" : ""}`}
                >
                  {tag.name}
                </button>
              );
            })}
          </div>
        ) : (
          <p className="text-muted text-sm">暂无标签，请在下方创建</p>
        )}

        {/* 新建标签 */}
        <div className="form-new-tag">
          <div style={{ flex: 1 }}>
            <input
              className="input"
              value={newTagName}
              onChange={(e) => setNewTagName(e.target.value)}
              placeholder="输入新标签名"
            />
          </div>
          <button
            type="button"
            className="btn btn-outline btn-sm"
            onClick={handleCreateTag}
            disabled={!newTagName.trim() || tagCreating}
          >
            {tagCreating ? (
              <Loader2 size={12} className="spinner" />
            ) : (
              <Plus size={12} />
            )}
            {tagCreating ? "创建中…" : "创建并选中"}
          </button>
        </div>
        {tagCreateError && (
          <p className="form-error"><AlertCircle size={12} /> {tagCreateError}</p>
        )}
      </div>

      {/* 提交/取消 */}
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={!canSubmit || submitting}>
          {submitting && <Loader2 size={14} className="spinner" />}
          {submitting ? "提交中…" : "保存"}
        </button>
        <button type="button" className="btn btn-outline" onClick={onCancel}>
          取消
        </button>
      </div>
    </form>
  );
}
