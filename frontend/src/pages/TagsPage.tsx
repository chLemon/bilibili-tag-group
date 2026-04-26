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
import VideoCard from "../components/VideoCard";

export default function TagsPage() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTagId, setSelectedTagId] = useState<number | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loadingTags, setLoadingTags] = useState(true);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [tagsError, setTagsError] = useState<string | null>(null);
  const [videosError, setVideosError] = useState<string | null>(null);

  // 初次加载标签列表
  useEffect(() => {
    fetchTags()
      .then((data) => {
        setTags(data);
        if (data.length > 0) {
          setSelectedTagId(data[0].id);
        }
      })
      .catch((err: Error) => setTagsError(err.message))
      .finally(() => setLoadingTags(false));
  }, []);

  // 选中标签变化时加载视频
  useEffect(() => {
    if (selectedTagId === null) return;
    setLoadingVideos(true);
    setVideosError(null);
    fetchTagVideos(selectedTagId)
      .then(setVideos)
      .catch((err: Error) => setVideosError(err.message))
      .finally(() => setLoadingVideos(false));
  }, [selectedTagId]);

  /** 标记已看后从列表中移除 */
  async function handleMarkWatched(videoId: number) {
    try {
      await updateWatched(videoId, true);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
    } catch (err) {
      setVideosError(String(err));
    }
  }

  if (loadingTags) return <p>加载标签中…</p>;
  if (tagsError) return <p style={{ color: "red" }}>错误：{tagsError}</p>;
  if (tags.length === 0) return <p>暂无标签，请先在"UP 主管理"中添加 UP 主并关联标签。</p>;

  return (
    <div style={{ display: "flex", gap: 24, height: "100%" }}>
      {/* 标签列表 */}
      <div style={{ width: 180, flexShrink: 0 }}>
        <h3 style={{ margin: "0 0 12px" }}>标签</h3>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {tags.map((tag) => (
            <li
              key={tag.id}
              onClick={() => setSelectedTagId(tag.id)}
              style={{
                padding: "8px 10px",
                cursor: "pointer",
                borderRadius: 4,
                background: selectedTagId === tag.id ? "#e0e7ff" : "transparent",
                fontWeight: selectedTagId === tag.id ? 600 : 400,
              }}
            >
              {tag.name}
            </li>
          ))}
        </ul>
      </div>

      {/* 视频列表 */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {loadingVideos ? (
          <p>加载视频中…</p>
        ) : videosError ? (
          <p style={{ color: "red" }}>视频加载失败：{videosError}</p>
        ) : videos.length === 0 ? (
          <p style={{ color: "#888" }}>该标签下暂无未看视频。</p>
        ) : (
          <>
            <h3 style={{ margin: "0 0 12px" }}>未看视频（{videos.length}）</h3>
            {videos.map((v) => (
              <VideoCard key={v.id} video={v} onMarkWatched={handleMarkWatched} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
