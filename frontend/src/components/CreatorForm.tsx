/**
 * CreatorForm：添加或编辑 UP 主的表单组件。
 * 支持名称、主页 URL、是否启用、关联标签的编辑。
 */
import { useState } from "react";
import { Tag } from "../api/client";

interface FormValues {
  name: string;
  profile_url: string;
  enabled: boolean;
  tag_ids: number[];
}

interface CreatorFormProps {
  /** 初始值（编辑模式时传入） */
  initialValues?: Partial<FormValues>;
  /** 可选标签列表 */
  tags: Tag[];
  /** 提交时的回调，参数为表单当前值 */
  onSubmit: (values: FormValues) => void;
  /** 取消时的回调 */
  onCancel: () => void;
  /** 是否正在提交（用于禁用按钮） */
  submitting?: boolean;
}

export default function CreatorForm({
  initialValues,
  tags,
  onSubmit,
  onCancel,
  submitting = false,
}: CreatorFormProps) {
  const [name, setName] = useState(initialValues?.name ?? "");
  const [profileUrl, setProfileUrl] = useState(
    initialValues?.profile_url ?? ""
  );
  const [enabled, setEnabled] = useState(initialValues?.enabled ?? true);
  const [tagIds, setTagIds] = useState<number[]>(
    initialValues?.tag_ids ?? []
  );

  /** 切换标签选中状态 */
  function toggleTag(id: number) {
    setTagIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({ name, profile_url: profileUrl, enabled, tag_ids: tagIds });
  }

  const labelStyle: React.CSSProperties = {
    display: "block",
    marginBottom: 12,
    fontSize: 14,
  };

  return (
    <form onSubmit={handleSubmit} style={{ minWidth: 320 }}>
      <label style={labelStyle}>
        <span>名称</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          style={{ display: "block", width: "100%", marginTop: 4 }}
          placeholder="UP 主昵称"
        />
      </label>

      <label style={labelStyle}>
        <span>主页 URL</span>
        <input
          value={profileUrl}
          onChange={(e) => setProfileUrl(e.target.value)}
          required
          style={{ display: "block", width: "100%", marginTop: 4 }}
          placeholder="https://space.bilibili.com/..."
        />
      </label>

      <label
        style={{ ...labelStyle, display: "flex", alignItems: "center", gap: 8 }}
      >
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
        />
        <span>启用同步</span>
      </label>

      {tags.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ fontSize: 14 }}>关联标签</span>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
            {tags.map((tag) => (
              <label
                key={tag.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={tagIds.includes(tag.id)}
                  onChange={() => toggleTag(tag.id)}
                />
                {tag.name}
              </label>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <button type="submit" disabled={submitting}>
          {submitting ? "提交中…" : "保存"}
        </button>
        <button type="button" onClick={onCancel}>
          取消
        </button>
      </div>
    </form>
  );
}
