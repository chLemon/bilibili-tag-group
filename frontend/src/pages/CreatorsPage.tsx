/**
 * CreatorsPage：UP 主管理页面。
 * 展示已添加的 UP 主列表，支持添加、编辑（启用/禁用、标签）、手动同步。
 */
import { Fragment, useEffect, useState } from "react";
import {
  fetchCreators,
  fetchTags,
  createCreator,
  updateCreator,
  syncCreator,
  Creator,
  Tag,
} from "../api/client";
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

  useEffect(() => {
    Promise.all([fetchCreators(), fetchTags()])
      .then(([c, t]) => {
        setCreators(c);
        setTags(t);
      })
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setLoading(false));
  }, []);

  /** 添加 UP 主 */
  async function handleAdd(values: {
    name: string;
    profile_url: string;
    enabled: boolean;
    tag_ids: number[];
  }) {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createCreator({
        name: values.name,
        profile_url: values.profile_url,
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

  /** 编辑 UP 主 */
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

  /** 手动同步单个 UP 主 */
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

  if (loading) return <p>加载中…</p>;
  if (loadError) return <p style={{ color: "red" }}>错误：{loadError}</p>;

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h2 style={{ margin: 0 }}>UP 主管理</h2>
        <button onClick={() => setFormMode({ type: "add" })}>+ 添加 UP 主</button>
      </div>

      {syncMsg && (
        <p style={{ color: "green", marginBottom: 12 }}>{syncMsg}</p>
      )}
      {submitError && (
        <p style={{ color: "red", marginBottom: 12 }}>提交失败：{submitError}</p>
      )}

      {/* 添加表单 */}
      {formMode.type === "add" && (
        <div
          style={{
            border: "1px solid #ddd",
            borderRadius: 6,
            padding: 16,
            marginBottom: 16,
          }}
        >
          <h4 style={{ margin: "0 0 12px" }}>添加 UP 主</h4>
          <CreatorForm
            tags={tags}
            onSubmit={handleAdd}
            onCancel={() => setFormMode({ type: "none" })}
            submitting={submitting}
          />
        </div>
      )}

      {/* UP 主列表 */}
      {creators.length === 0 ? (
        <p style={{ color: "#888" }}>暂无 UP 主，点击上方按钮添加。</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #ddd", textAlign: "left" }}>
              <th style={{ padding: "8px 10px" }}>名称</th>
              <th style={{ padding: "8px 10px" }}>状态</th>
              <th style={{ padding: "8px 10px" }}>标签</th>
              <th style={{ padding: "8px 10px" }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {creators.map((c) => (
              <Fragment key={c.id}>
                <tr
                  style={{ borderBottom: "1px solid #eee", verticalAlign: "top" }}
                >
                  <td style={{ padding: "8px 10px" }}>
                    <a href={c.profile_url} target="_blank" rel="noreferrer">
                      {c.name}
                    </a>
                  </td>
                  <td style={{ padding: "8px 10px" }}>
                    {c.enabled ? "启用" : "停用"}
                  </td>
                  <td style={{ padding: "8px 10px" }}>
                    {c.tag_ids
                      .map(
                        (tid) => tags.find((t) => t.id === tid)?.name ?? `#${tid}`
                      )
                      .join(", ") || "-"}
                  </td>
                  <td style={{ padding: "8px 10px", display: "flex", gap: 6 }}>
                    <button
                      onClick={() => setFormMode({ type: "edit", creator: c })}
                    >
                      编辑
                    </button>
                    <button
                      onClick={() => handleSync(c.id)}
                      disabled={syncingId === c.id}
                    >
                      {syncingId === c.id ? "同步中…" : "同步"}
                    </button>
                  </td>
                </tr>
                {/* 编辑表单内联展示 */}
                {formMode.type === "edit" && formMode.creator.id === c.id && (
                  <tr>
                    <td
                      colSpan={4}
                      style={{
                        padding: 16,
                        background: "#fafafa",
                        border: "1px solid #eee",
                      }}
                    >
                      <CreatorForm
                        initialValues={{
                          name: c.name,
                          profile_url: c.profile_url,
                          enabled: c.enabled,
                          tag_ids: c.tag_ids,
                        }}
                        tags={tags}
                        onSubmit={(values) => handleEdit(c.id, values)}
                        onCancel={() => setFormMode({ type: "none" })}
                        submitting={submitting}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
