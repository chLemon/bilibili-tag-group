/**
 * UP 主详情页 hook：加载 UP 主、视频列表与标签，维护观看状态切换。
 * 本地同步维护 creator.unwatched_count，避免每次操作后整页刷新。
 */
import { useCallback, useEffect, useState } from "react";
import {
  fetchCreator,
  fetchCreatorVideos,
  fetchTags,
  updateStatus,
  batchUpdateCreatorVideos,
  Creator,
  Tag,
  VideoDetail,
} from "../api/client";
import { formatError } from "../utils/format";

export function useCreatorDetail(creatorId: number) {
  const [creator, setCreator] = useState<Creator | null>(null);
  const [videos, setVideos] = useState<VideoDetail[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<number | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);

  useEffect(() => {
    if (!Number.isInteger(creatorId) || creatorId <= 0) {
      setError("无效的 UP 主 ID");
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([
      fetchCreator(creatorId),
      fetchCreatorVideos(creatorId),
      fetchTags(),
    ])
      .then(([c, v, t]) => {
        if (cancelled) return;
        setCreator(c);
        setVideos(v);
        setTags(t);
      })
      .catch((err) => {
        if (!cancelled) setError(formatError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [creatorId]);

  const setStatus = useCallback(
    async (video: VideoDetail, newStatus: number) => {
      setToggling(video.id);
      try {
        await updateStatus(video.id, newStatus);
        const oldStatus = video.status;
        setVideos((prev) =>
          prev.map((v) => (v.id === video.id ? { ...v, status: newStatus } : v))
        );
        // 只有进出"未看"状态才影响 unwatched_count
        const wasUnwatched = oldStatus === 0;
        const isUnwatched = newStatus === 0;
        if (wasUnwatched !== isUnwatched) {
          setCreator((c) =>
            c ? { ...c, unwatched_count: c.unwatched_count + (isUnwatched ? 1 : -1) } : c
          );
        }
      } catch (err) {
        setError(formatError(err));
      } finally {
        setToggling(null);
      }
    },
    []
  );

  /** 一键标记所有视频为指定状态（后端对所有视频生效，前端直接对齐） */
  const batchSetStatus = useCallback(
    async (newStatus: number) => {
      setBatchLoading(true);
      try {
        await batchUpdateCreatorVideos(creatorId, newStatus);
        setVideos((prev) => {
          const next = prev.map((v) => ({ ...v, status: newStatus }));
          // 用更新后的列表重算未看数，而非简单取 0 或长度
          const unwatched = next.filter((v) => v.status === 0).length;
          setCreator((c) => (c ? { ...c, unwatched_count: unwatched } : c));
          return next;
        });
      } catch (err) {
        setError(formatError(err));
      } finally {
        setBatchLoading(false);
      }
    },
    [creatorId]
  );

  return {
    creator,
    videos,
    tags,
    loading,
    error,
    toggling,
    batchLoading,
    setStatus,
    batchSetStatus,
  };
}
