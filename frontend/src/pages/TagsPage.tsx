/**
 * TagsPage：标签视图页面。
 * 左侧标签列表 + UP 主目录锚点，右侧按 UP 主分组的未看视频列表。
 */
import { useState } from "react";
import { Hash, AlertCircle, Inbox, Loader2, RefreshCw, Tag } from "lucide-react";
import { useTags, useTagVideos, useScrollSpy, UNTAGGED_ID } from "../hooks/useTags";
import VideoCard from "../components/VideoCard";
import CreatorAnchorNav from "../components/CreatorAnchorNav";

export default function TagsPage() {
  const { tags, loading: loadingTags, error: tagsError } = useTags();
  const [selectedTagId, setSelectedTagId] = useState<number | null>(null);

  // 标签加载完成后自动选中第一个
  if (selectedTagId === null && tags.length > 0) {
    setSelectedTagId(tags[0].id);
  } else if (selectedTagId === null && !loadingTags) {
    // 标签列表为空时选中"无标签"
    if (selectedTagId === null) setSelectedTagId(UNTAGGED_ID);
  }

  const {
    videos,
    groupedVideos,
    loading: loadingVideos,
    error: videosError,
    markWatched,
    markIgnored,
  } = useTagVideos(selectedTagId);

  const { activeCreatorId, scrollToCreator } = useScrollSpy(
    groupedVideos,
    !loadingVideos,
  );

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
          <span className="badge badge-muted">{videos.length} 个未看</span>
        </h3>

        {loadingVideos ? (
          <div className="loading-state">
            <Loader2 size={20} className="spinner" /> 加载视频中…
          </div>
        ) : videosError ? (
          <div className="error-message">
            <AlertCircle size={16} />
            视频加载失败：{videosError}
            <button className="btn btn-outline btn-sm" onClick={() => setSelectedTagId(selectedTagId)}>
              <RefreshCw size={12} /> 重试
            </button>
          </div>
        ) : videos.length === 0 ? (
          <div className="empty-state">
            <Inbox size={36} />
            <p>
              {selectedTagId === UNTAGGED_ID
                ? "暂无无标签 UP 主的未看视频"
                : "该标签下暂无未看视频"}
            </p>
            <p className="empty-hint">新视频同步后会展示在这里</p>
          </div>
        ) : (
          <div key={selectedTagId}>
            {groupedVideos.map((group, i) => (
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
                </div>
                {group.videos.map((v) => (
                  <VideoCard key={v.id} video={v} onMarkWatched={markWatched} onMarkIgnored={markIgnored} />
                ))}
              </section>
            ))}
          </div>
        )}
      </div>

      {/* 右侧：UP 主列表 */}
      <CreatorAnchorNav
        groups={groupedVideos}
        activeCreatorId={activeCreatorId}
        onSelect={scrollToCreator}
      />
    </div>
  );
}
