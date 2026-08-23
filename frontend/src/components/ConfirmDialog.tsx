/**
 * ConfirmDialog：通用的确认弹窗，替代 window.confirm。
 * onConfirm 为异步操作时，确认按钮会进入 loading 直到操作返回。
 */
import { useState } from "react";
import { X, Loader2 } from "lucide-react";

interface Props {
  title?: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  /** 危险操作（如删除）时用红色确认按钮 */
  danger?: boolean;
  onConfirm: () => Promise<void>;
  onClose: () => void;
}

export default function ConfirmDialog({
  title = "确认操作",
  message,
  confirmText = "确定",
  cancelText = "取消",
  danger = false,
  onConfirm,
  onClose,
}: Props) {
  const [loading, setLoading] = useState(false);

  async function handleConfirm() {
    setLoading(true);
    try {
      await onConfirm();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onClose();
      }}
    >
      <div
        className="modal-content"
        role="dialog"
        aria-label={title}
        style={{ maxWidth: 420 }}
      >
        <div className="modal-header">
          <h3>{title}</h3>
          <button
            className="modal-close"
            onClick={onClose}
            disabled={loading}
            title="关闭"
          >
            <X size={18} />
          </button>
        </div>

        <p style={{ whiteSpace: "pre-wrap", margin: "12px 0 20px" }}>
          {message}
        </p>

        <div
          className="batch-import-actions"
          style={{ justifyContent: "flex-end" }}
        >
          <button
            className={`btn ${danger ? "btn-danger" : "btn-primary"}`}
            disabled={loading}
            onClick={handleConfirm}
          >
            {loading && <Loader2 size={14} className="spinner" />}
            {loading ? "处理中…" : confirmText}
          </button>
          <button
            className="btn btn-outline"
            onClick={onClose}
            disabled={loading}
          >
            {cancelText}
          </button>
        </div>
      </div>
    </div>
  );
}
