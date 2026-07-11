/**
 * ImmediateTagsSection：管理立即同步标签——展示已设置的标签，提供添加/移除操作。
 */
import { Zap, Plus, X, Loader2 } from "lucide-react";
import { ImmediateTag, Tag } from "../../api/client";

interface Props {
  immediateTags: ImmediateTag[];
  availableTags: Tag[];
  allTags: Tag[];
  addingTagId: number | null;
  onAdd: (tagId: number) => Promise<void>;
  onRemove: (tagId: number) => Promise<void>;
}

export default function ImmediateTagsSection({
  immediateTags,
  availableTags,
  allTags,
  addingTagId,
  onAdd,
  onRemove,
}: Props) {
  return (
    <div className="immediate-tags-section">
      {/* 标题 */}
      <h3 className="immediate-tags-title">
        <Zap size={18} style={{ color: "var(--color-warning)" }} />
        立即同步标签
      </h3>

      {/* 说明 */}
      <p className="text-secondary text-sm" style={{ marginBottom: "var(--space-4)" }}>
        拥有这些标签的 UP 主在同步时将绕过 TTL 缓存，直接从 B 站获取最新视频数据。
      </p>

      {/* 已设置的立即同步标签列表 */}
      {immediateTags.length === 0 ? (
        <div className="text-muted text-sm" style={{ marginBottom: "var(--space-2)" }}>
          暂无立即同步标签，点击下方标签添加。
        </div>
      ) : (
        <div className="immediate-tags-list">
          {immediateTags.map((it) => {
            const tag = allTags.find((t) => t.id === it.tag_id);
            return (
              <span key={it.id} className="badge badge-info immediate-tag-item">
                <Zap size={13} />
                {tag?.name ?? `标签 #${it.tag_id}`}
                <button
                  className="btn btn-ghost btn-sm immediate-tag-remove"
                  onClick={() => onRemove(it.tag_id)}
                  title="移除立即同步"
                >
                  <X size={13} />
                </button>
              </span>
            );
          })}
        </div>
      )}

      {/* 可添加的标签选择器 */}
      <div className="text-sm text-secondary" style={{ marginBottom: "var(--space-2)" }}>
        点击标签设为"立即同步"：
      </div>
      {availableTags.length > 0 ? (
        <div className="flex gap-2" style={{ flexWrap: "wrap" }}>
          {availableTags.map((tag) => (
            <button
              key={tag.id}
              className="filter-chip"
              onClick={() => onAdd(tag.id)}
              disabled={addingTagId === tag.id}
            >
              {addingTagId === tag.id ? (
                <Loader2 size={12} className="spinner" />
              ) : (
                <Plus size={12} />
              )}
              {tag.name}
            </button>
          ))}
        </div>
      ) : (
        <div className="text-muted text-sm">
          {allTags.length === 0
            ? "暂无标签，请先在 UP 主管理页面创建标签。"
            : "所有标签已设为立即同步。"}
        </div>
      )}
    </div>
  );
}
