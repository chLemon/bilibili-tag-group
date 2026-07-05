/**
 * TagsPage：标签视图页面。
 * 左侧展示标签列表，右侧展示选中标签下的未看视频。
 */
import { useEffect, useState } from "react";
import {
  fetchTags,
  fetchTagVideos,
  updateWatched,
  Tag,
  Video,
} from "../api/client";
import { Hash, AlertCircle, Inbox, Loader2, RefreshCw } from "lucide-react";
import VideoCard from "../components/VideoCard";

export default function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTagId, setSelectedTagId] = useState<number | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loadingTags, setLoadingTags] = useState(true);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [tagsError, setTagsError] = useState<string | null>(null);
  const [videosError, setVideosError] = useState<string | null>(null);

  useEffect(() => {
    fetchTags()
      .then((data) => {
        setTags(data);
        if (data.length > 0) setSelectedTagId(data[0].id);
      })
      .catch((err: Error) => setTagsError(err.message))
      .finally(() => setLoadingTags(false));
  }, []);

  useEffect(() => {
    if (selectedTagId === null) return;
    setLoadingVideos(true);
    setVideosError(null);
    fetchTagVideos(selectedTagId)
      .then(setVideos)
      .catch((err: Error) => setVideosError(err.message))
      .finally(() => setLoadingVideos(false));
  }, [selectedTagId]);

  async function handleMarkWatched(videoId: number) {
    try {
      await updateWatched(videoId, true);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
    } catch (err) {
      setVideosError(String(err));
    }
  }

  if (loadingTags) {
    return (
      <div className="loading-state">
        <Loader2 size={20} className="spinner" /> 加载标签中…
      </div>
    );
  }

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

  if (tags.length === 0) {
    return (
      <div className="empty-state" style={{ paddingTop: 48 }}>
        <Inbox size={40} />
        <p>暂无标签</p>
        <p className="empty-hint">请先在"UP 主管理"中添加 UP 主并关联标签</p>
      </div>
    );
  }

  const selectedTag = tags.find((t) => t.id === selectedTagId);

  return (
    <div style={{ display: "flex", gap: 24, minHeight: "calc(100vh - 120px)" }}>
      {/* 左侧标签列表 */}
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
        </ul>
      </aside>

      {/* 右侧视频列表 */}
      <div className="video-panel">
        {selectedTag && (
          <h3 className="video-panel-title">
            {selectedTag.name}
            <span className="badge badge-muted">{videos.length} 个未看</span>
          </h3>
        )}

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
            <p>该标签下暂无未看视频</p>
            <p className="empty-hint">新视频同步后会展示在这里</p>
          </div>
        ) : (
          <div>
            {videos.map((v) => (
              <VideoCard key={v.id} video={v} onMarkWatched={handleMarkWatched} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
