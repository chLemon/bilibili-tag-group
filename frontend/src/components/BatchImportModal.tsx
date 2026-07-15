import { useState } from "react";
import {
  resolveCreatorName,
  batchCreateCreators,
  Creator,
} from "../api/client";
import { X, Loader2, AlertCircle, CheckCircle2, ChevronLeft } from "lucide-react";

interface ParsedItem {
  uid: string;
  tag_names: string[];
  name: string | null;
  avatar_url: string | null;
  resolving: boolean;
  error: string | null;
}

interface Props {
  onClose: () => void;
  onSuccess: (creators: Creator[]) => void;
}

export default function BatchImportModal({ onClose, onSuccess }: Props) {
  const [text, setText] = useState("");
  const [step, setStep] = useState<"input" | "preview">("input");
  const [items, setItems] = useState<ParsedItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsedCount = text.trim()
    ? text.trim().split("\n").filter((l) => l.trim()).length
    : 0;

  function parseText(): ParsedItem[] {
    return text
      .trim()
      .split("\n")
      .filter((l) => l.trim())
      .map((line) => {
        const parts = line.split(",").map((s) => s.trim()).filter((s) => s !== "");
        const uid = parts[0];
        const tag_names = parts.slice(1);
        return { uid, tag_names, name: null, avatar_url: null, resolving: true, error: null };
      });
  }

  async function handlePreview() {
    const parsed = parseText();
    if (parsed.length === 0) return;
    setItems(parsed);
    setStep("preview");
    setError(null);

    const results = await Promise.allSettled(
      parsed.map((item) =>
        resolveCreatorName(`https://space.bilibili.com/${item.uid}`)
      )
    );

    setItems((prev) =>
      prev.map((item, i) => {
        const result = results[i];
        if (result.status === "fulfilled") {
          return {
            ...item,
            name: result.value.name,
            avatar_url: result.value.avatar_url,
            resolving: false,
          };
        } else {
          return {
            ...item,
            resolving: false,
            error: result.reason instanceof Error ? result.reason.message : "解析失败",
          };
        }
      })
    );
  }

  async function handleSubmit() {
    const validItems = items.filter((item) => item.name && !item.error);
    if (validItems.length === 0) return;

    setSubmitting(true);
    setError(null);
    try {
      const resp = await batchCreateCreators({
        items: validItems.map((item) => ({
          uid: item.uid,
          tag_names: item.tag_names,
          name: item.name!,
        })),
      });
      const newCreators = resp.results
        .filter((r) => r.success && r.creator)
        .map((r) => r.creator!);
      const failedItems = resp.results.filter((r) => !r.success);
      if (failedItems.length > 0) {
        const msgs = failedItems.map((r) => `${r.uid}: ${r.error}`).join("\n");
        setError(`部分添加失败：\n${msgs}`);
      }
      if (newCreators.length > 0) {
        onSuccess(newCreators);
      }
      if (failedItems.length === 0) {
        onClose();
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  const resolvedCount = items.filter((i) => i.name && !i.error).length;
  const errorCount = items.filter((i) => i.error).length;
  const canSubmit = resolvedCount > 0 && !submitting;

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-content" style={{ maxWidth: 600 }}>
        <div className="modal-header">
          <h3>批量添加 UP 主</h3>
          <button className="modal-close" onClick={onClose} title="关闭 (Esc)">
            <X size={18} />
          </button>
        </div>

        {step === "input" ? (
          <>
            <p className="batch-import-hint">
              每行一个 UP 主，格式：<code>uid,标签1,标签2</code>（标签可选）
              {parsedCount > 0 && (
                <span className="batch-import-count">已识别 {parsedCount} 个 UP 主</span>
              )}
            </p>
            <textarea
              className="batch-import-textarea"
              rows={10}
              placeholder={"123456,游戏,科技\n789012,音乐\n345678"}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <div className="batch-import-actions">
              <button
                className="btn btn-primary"
                disabled={parsedCount === 0}
                onClick={handlePreview}
              >
                预览
              </button>
              <button className="btn btn-outline" onClick={onClose}>
                取消
              </button>
            </div>
          </>
        ) : (
          <>
            {error && (
              <div className="error-message">
                <AlertCircle size={16} />
                <span style={{ whiteSpace: "pre-wrap" }}>{error}</span>
              </div>
            )}

            <div className="batch-preview-summary">
              <span className="batch-preview-total">共 {items.length} 个</span>
              <span className="batch-preview-ok">
                <CheckCircle2 size={14} /> {resolvedCount} 成功
              </span>
              {errorCount > 0 && (
                <span className="batch-preview-err">
                  <AlertCircle size={14} /> {errorCount} 失败
                </span>
              )}
            </div>

            <div className="batch-preview-table-wrap">
              <table className="batch-preview-table">
                <thead>
                  <tr>
                    <th style={{ width: 100 }}>UID</th>
                    <th style={{ width: 120 }}>名称</th>
                    <th>标签</th>
                    <th style={{ width: 60 }}>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.uid} className={item.error ? "batch-preview-row-error" : ""}>
                      <td>{item.uid}</td>
                      <td>
                        {item.resolving ? (
                          <span className="batch-preview-resolving">
                            <Loader2 size={12} className="spinner" /> 解析中
                          </span>
                        ) : item.error ? (
                          <span className="batch-preview-error-text">失败</span>
                        ) : (
                          item.name
                        )}
                      </td>
                      <td>
                        {item.tag_names.length > 0
                          ? item.tag_names.map((n) => (
                              <span key={n} className="badge badge-info" style={{ marginRight: 4 }}>
                                {n}
                              </span>
                            ))
                          : "-"}
                      </td>
                      <td>
                        {item.resolving ? (
                          <Loader2 size={14} className="spinner" />
                        ) : item.error ? (
                          <AlertCircle size={14} className="text-error" />
                        ) : (
                          <CheckCircle2 size={14} className="text-success" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="batch-import-actions">
              <button
                className="btn btn-primary"
                disabled={!canSubmit}
                onClick={handleSubmit}
              >
                {submitting ? "添加中…" : `确定（${resolvedCount} 个）`}
              </button>
              <button
                className="btn btn-outline"
                onClick={() => {
                  setStep("input");
                  setError(null);
                }}
                disabled={submitting}
              >
                <ChevronLeft size={14} /> 返回修改
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
