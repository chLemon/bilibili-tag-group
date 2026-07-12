/**
 * 标签视图模块自定义 hook：标签获取、视频获取与分组、滚动监听。
 */
import { useState, useEffect, useMemo, useCallback } from "react";
import {
  fetchTags,
  fetchTagVideos,
  fetchUntaggedVideos,
  updateStatus,
  Tag,
  Video,
} from "../api/client";

/** 无标签 UP 主的虚拟标识 */
export const UNTAGGED_ID = -1;

/** 按 UP 主分组后的视频集合 */
export interface CreatorGroup {
  creatorId: number;
  creatorName: string;
  creatorAlias: string | null;
  creatorAvatarUrl: string | null;
  videos: Video[];
}

// ── useTags ──────────────────────────────────────────────────────────

/** 获取所有标签列表，管理加载与错误状态 */
export function useTags() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTags()
      .then(setTags)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return { tags, loading, error };
}

// ── useTagVideos ─────────────────────────────────────────────────────

/**
 * 根据选中的标签 ID 获取视频列表，并按 UP 主分组。
 * 返回分组后的列表、原始视频列表、加载状态、错误及标记已看方法。
 */
export function useTagVideos(selectedTagId: number | null) {
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedTagId === null) return;
    setLoading(true);
    setError(null);
    const promise =
      selectedTagId === UNTAGGED_ID
        ? fetchUntaggedVideos()
        : fetchTagVideos(selectedTagId);
    promise
      .then(setVideos)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedTagId]);

  const groupedVideos: CreatorGroup[] = useMemo(() => {
    const map = new Map<number, CreatorGroup>();
    for (const v of videos) {
      if (!map.has(v.creator_id)) {
        map.set(v.creator_id, {
          creatorId: v.creator_id,
          creatorName: v.creator_name,
          creatorAlias: v.creator_alias,
          creatorAvatarUrl: v.creator_avatar_url,
          videos: [],
        });
      }
      map.get(v.creator_id)!.videos.push(v);
    }
    return Array.from(map.values());
  }, [videos]);

  const markWatched = useCallback(async (videoId: number) => {
    try {
      await updateStatus(videoId, 1);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
    } catch (err) {
      setError(String(err));
    }
  }, []);

  const markIgnored = useCallback(async (videoId: number) => {
    try {
      await updateStatus(videoId, 2);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
    } catch (err) {
      setError(String(err));
    }
  }, []);

  return { videos, groupedVideos, loading, error, markWatched, markIgnored };
}

// ── useScrollSpy ─────────────────────────────────────────────────────

/**
 * 使用 IntersectionObserver 监听 UP 主分组区域，
 * 返回当前可见的 creatorId 和 scrollTo 方法。
 */
export function useScrollSpy(groups: CreatorGroup[], enabled: boolean) {
  const [activeCreatorId, setActiveCreatorId] = useState<number | null>(null);

  // 分组变化时重置激活状态
  useEffect(() => {
    setActiveCreatorId(null);
  }, [groups]);

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    if (!enabled || groups.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {
          const id = Number(visible[0].target.id.replace("creator-", ""));
          setActiveCreatorId(id);
        }
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 },
    );

    const timer = setTimeout(() => {
      for (const g of groups) {
        const el = document.getElementById(`creator-${g.creatorId}`);
        if (el) observer.observe(el);
      }
    }, 50);

    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, [groups, enabled]);

  const scrollToCreator = useCallback((creatorId: number) => {
    document
      .getElementById(`creator-${creatorId}`)
      ?.scrollIntoView({ behavior: "smooth" });
  }, []);

  return { activeCreatorId, scrollToCreator };
}
