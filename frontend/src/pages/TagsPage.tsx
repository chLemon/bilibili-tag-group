/**
 * TagsPage：标签视图页面。
 * 左侧标签列表 + UP 主目录锚点，右侧按 UP 主分组的未看视频列表。
 */
import { useEffect, useMemo, useState } from "react";
import { Hash, AlertCircle, Inbox, Loader2, RefreshCw, Tag, CheckCheck, EyeOff, ChevronsRight, ChevronsLeft, Zap } from "lucide-react";
import { useTags, useTagVideos, useScrollSpy, UNTAGGED_ID } from "../hooks/useTags";
import VideoCard from "../components/VideoCard";
import CreatorAnchorNav from "../components/CreatorAnchorNav";
import ConfirmDialog from "../components/ConfirmDialog";

export default function TagsPage() {
  const { tags, loading: loadingTags, error: tagsError, refresh: refreshTags } = useTags();
  const [selectedTagId, setSelectedTagId] = useState<number | null>(null);

  // 标签加载完成后自动选中第一个；无标签时选中"无标签"
  useEffect(() => {
    if (selectedTagId === null && !loadingTags) {
      setSelectedTagId(tags.length > 0 ? tags[0].id : UNTAGGED_ID);
    }
  }, [tags, loadingTags, selectedTagId]);

  const {
    videos,
    groupedVideos,
    loading: loadingVideos,
    error: videosError,
    actionError,
    dismissActionError,
    reload,
    markWatched,
    markIgnored,
    markAllWatched,
    markAllIgnored,
  } = useTagVideos(selectedTagId);

  // 标记操作成功后顺带刷新侧栏标签的未看数（失败时不刷新）
  const handleMarkWatched = async (videoId: number) => {
    if (await markWatched(videoId)) refreshTags();
  };
  const handleMarkIgnored = async (videoId: number) => {
    if (await markIgnored(videoId)) refreshTags();
  };

  const [showChargeVideos, setShowChargeVideos] = useState(false);
  const visibleGroups = useMemo(() => {
    if (showChargeVideos) return groupedVideos;
    return groupedVideos
      .map((g) => ({
        ...g,
        videos: g.videos.filter((v) => v.mark !== "充电视频"),
      }))
      .filter((g) => g.videos.length > 0);
  }, [groupedVideos, showChargeVideos]);
  const visibleCount = visibleGroups.reduce((sum, g) => sum + g.videos.length, 0);

  const { activeCreatorId, scrollToCreator } = useScrollSpy(
    visibleGroups,
    !loadingVideos,
  );

  const [expandedCreators, setExpandedCreators] = useState<Set<number>>(new Set());
  const [batchLoadingId, setBatchLoadingId] = useState<number | null>(null);
  const [batchConfirm, setBatchConfirm] = useState<
    { type: "watched" | "ignored"; creatorId: number } | null
  >(null);

  const toggleExpand = (creatorId: number) => {
    setExpandedCreators((prev) => {
      const next = new Set(prev);
      if (next.has(creatorId)) {
        next.delete(creatorId);
      } else {
        next.add(creatorId);
      }
      return next;
    });
  };

  const handleMarkAllWatched = (creatorId: number) => {
    setBatchConfirm({ type: "watched", creatorId });
  };

  const handleMarkAllIgnored = (creatorId: number) => {
    setBatchConfirm({ type: "ignored", creatorId });
  };

  async function runBatchConfirm() {
    if (!batchConfirm) return;
    const { type, creatorId } = batchConfirm;
    const group = visibleGroups.find((g) => g.creatorId === creatorId);
    const videoIds = group ? group.videos.map((v) => v.id) : [];
    if (videoIds.length === 0) {
      setBatchConfirm(null);
      return;
    }
    setBatchLoadingId(creatorId);
    try {
      const ok =
        type === "watched"
          ? await markAllWatched(videoIds)
          : await markAllIgnored(videoIds);
      if (ok) refreshTags();
    } finally {
      setBatchLoadingId(null);
    }
  }

  // ── 标签加载态 ──
  if (loadingTags) {
    return (
      <div className="loading-state">
        <Loader2 size={20} className="spinner" /> 加载标签中…
      </div>
    );
  }

  // ── 标签加载失败 ──
  if (tagsError) {
    return (
      <div className="error-message">
        <AlertCircle size={16} />
        加载失败：{tagsError}
        <button className="btn btn-outline btn-sm" onClick={() => window.location.reload()}>
          <RefreshCw size={12} /> 重试
        </button>
      </div>
    );
  }

  const selectedTag =
    selectedTagId === UNTAGGED_ID
      ? null
      : tags.find((t) => t.id === selectedTagId);

  return (
    <div style={{ display: "flex", gap: 24, minHeight: "calc(100vh - 120px)" }}>
      {/* 左侧：标签列表 */}
      <aside className="tag-sidebar">
        <h3 className="tag-sidebar-title">
          <Hash size={16} /> 标签
        </h3>
        <ul>
          {tags.map((tag) => (
            <li
              key={tag.id}
              onClick={() => setSelectedTagId(tag.id)}
              className={`tag-item${selectedTagId === tag.id ? " tag-item-active" : ""}`}
            >
              <span className="tag-item-name truncate">{tag.name}</span>
              {tag.unwatched_count > 0 && (
                <span className="anchor-badge">{tag.unwatched_count}</span>
              )}
            </li>
          ))}
          <li
            onClick={() => setSelectedTagId(UNTAGGED_ID)}
            className={`tag-item${selectedTagId === UNTAGGED_ID ? " tag-item-active" : ""}`}
          >
            <span className="tag-item-name truncate" style={{ fontStyle: "italic" }}>
              <Tag size={12} /> 无标签
            </span>
          </li>
        </ul>
      </aside>

      {/* 中间：视频列表 */}
      <div className="video-panel">
        <h3 className="video-panel-title">
          {selectedTagId === UNTAGGED_ID ? "无标签 UP 主" : selectedTag?.name ?? ""}
          <span className="badge badge-muted">{visibleCount} 个未看</span>
          <button
            className={`btn btn-sm ${showChargeVideos ? "btn-primary" : "btn-outline"}`}
            onClick={() => setShowChargeVideos((s) => !s)}
            title={showChargeVideos ? "当前显示充电视频，点击隐藏" : "当前隐藏充电视频，点击显示"}
            style={{ marginLeft: "auto" }}
          >
            <Zap size={13} />
            {showChargeVideos ? "不显示充电视频" : "显示充电视频"}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={reload}
            disabled={loadingVideos}
            title="重新加载视频列表"
          >
            <RefreshCw size={14} className={loadingVideos ? "spinner" : ""} />
          </button>
        </h3>

        {actionError && (
          <div className="error-message">
            <AlertCircle size={16} />
            操作失败：{actionError}
            <button className="btn btn-outline btn-sm" onClick={dismissActionError}>
              知道了
            </button>
          </div>
        )}

        {loadingVideos ? (
          <div className="loading-state">
            <Loader2 size={20} className="spinner" /> 加载视频中…
          </div>
        ) : videosError ? (
          <div className="error-message">
            <AlertCircle size={16} />
            视频加载失败：{videosError}
            <button className="btn btn-outline btn-sm" onClick={reload}>
              <RefreshCw size={12} /> 重试
            </button>
          </div>
        ) : visibleCount === 0 ? (
          <div className="empty-state">
            <Inbox size={36} />
            <p>
              {videos.length > 0
                ? "未看视频均为充电视频（右上角可切换显示）"
                : selectedTagId === UNTAGGED_ID
                  ? "暂无无标签 UP 主的未看视频"
                  : "该标签下暂无未看视频"}
            </p>
            {videos.length === 0 && (
              <p className="empty-hint">新视频同步后会展示在这里</p>
            )}
          </div>
        ) : (
          <div key={selectedTagId}>
            {visibleGroups.map((group, i) => (
              <section
                key={group.creatorId}
                id={`creator-${group.creatorId}`}
                className="creator-group"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <div className="creator-group-header">
                  {group.creatorAvatarUrl ? (
                    <img
                      src={group.creatorAvatarUrl}
                      alt={group.creatorName}
                      className="creator-group-avatar"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <span className="creator-group-avatar creator-group-avatar-placeholder">
                      {group.creatorName.charAt(0)}
                    </span>
                  )}
                  <span className="creator-group-name">
                    {group.creatorAlias
                      ? `${group.creatorAlias}（${group.creatorName}）`
                      : group.creatorName}
                  </span>
                  <span className="badge badge-muted">{group.videos.length} 个视频</span>
                  <div className="creator-group-actions">
                    {expandedCreators.has(group.creatorId) ? (
                      <>
                        <button
                          key="watched"
                          className="btn btn-sm btn-primary"
                          disabled={batchLoadingId !== null}
                          onClick={() => handleMarkAllWatched(group.creatorId)}
                        >
                          {batchLoadingId === group.creatorId ? (
                            <Loader2 size={14} className="spinner" />
                          ) : (
                            <CheckCheck size={14} />
                          )}
                          一键已看
                        </button>
                        <button
                          key="ignored"
                          className="btn btn-sm btn-muted"
                          disabled={batchLoadingId !== null}
                          onClick={() => handleMarkAllIgnored(group.creatorId)}
                        >
                          {batchLoadingId === group.creatorId ? (
                            <Loader2 size={14} className="spinner" />
                          ) : (
                            <EyeOff size={14} />
                          )}
                          一键不看
                        </button>
                        <button
                          key="toggle"
                          className="btn btn-sm btn-ghost"
                          onClick={() => toggleExpand(group.creatorId)}
                          title="收起批量操作"
                        >
                          <ChevronsRight size={14} />
                        </button>
                      </>
                    ) : (
                      <button
                        key="toggle"
                        className="btn btn-sm btn-outline"
                        onClick={() => toggleExpand(group.creatorId)}
                        title="展开批量操作"
                      >
                        <ChevronsLeft size={14} />
                      </button>
                    )}
                  </div>
                </div>
                {group.videos.map((v) => (
                  <VideoCard key={v.id} video={v} onMarkWatched={handleMarkWatched} onMarkIgnored={handleMarkIgnored} />
                ))}
              </section>
            ))}
          </div>
        )}
      </div>

      {/* 右侧：UP 主列表 */}
      <CreatorAnchorNav
        groups={visibleGroups}
        activeCreatorId={activeCreatorId}
        onSelect={scrollToCreator}
      />

      {batchConfirm && (
        <ConfirmDialog
          title="批量标记"
          message={
            batchConfirm.type === "watched"
              ? "确定将该 UP 主的所有未看视频标记为已看？"
              : "确定将该 UP 主的所有未看视频标记为不看？"
          }
          confirmText={batchConfirm.type === "watched" ? "标记已看" : "标记不看"}
          danger={batchConfirm.type === "ignored"}
          onConfirm={async () => {
            await runBatchConfirm();
            setBatchConfirm(null);
          }}
          onClose={() => setBatchConfirm(null)}
        />
      )}
    </div>
  );
}
