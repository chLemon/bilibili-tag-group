/**
 * UP 主管理页 hook：UP 主与标签的获取、筛选、添加、编辑。
 * loadError 用于首次加载失败；submitError 用于表单提交失败（在弹窗内展示）。
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchCreators,
  fetchTags,
  createCreator,
  updateCreator,
  deleteCreator,
  Creator,
  CreatorCreate,
  CreatorUpdate,
  Tag,
} from "../api/client";
import { formatError } from "../utils/format";

export function useCreators() {
  const [creators, setCreators] = useState<Creator[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [filterTagId, setFilterTagId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchCreators(), fetchTags()])
      .then(([c, t]) => {
        if (cancelled) return;
        setCreators(c);
        setTags(t);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(formatError(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // 表单里可能新建了标签，静默刷新标签列表
  const refreshTags = useCallback(() => {
    fetchTags()
      .then(setTags)
      .catch(() => {});
  }, []);

  const filteredCreators = useMemo(() => {
    if (filterTagId === null) return creators;
    return creators.filter((c) => c.tag_ids.includes(filterTagId));
  }, [creators, filterTagId]);

  const totalUnwatched = useMemo(
    () => creators.reduce((sum, c) => sum + c.unwatched_count, 0),
    [creators]
  );

  /** 添加 UP 主，成功返回 true（调用方据此关闭弹窗） */
  const addCreator = useCallback(
    async (values: CreatorCreate): Promise<boolean> => {
      setSubmitting(true);
      setSubmitError(null);
      try {
        const created = await createCreator(values);
        setCreators((prev) => [...prev, created]);
        refreshTags();
        return true;
      } catch (err) {
        setSubmitError(formatError(err));
        return false;
      } finally {
        setSubmitting(false);
      }
    },
    [refreshTags]
  );

  /** 编辑 UP 主，成功返回 true（调用方据此关闭弹窗） */
  const editCreator = useCallback(
    async (creatorId: number, values: CreatorUpdate): Promise<boolean> => {
      setSubmitting(true);
      setSubmitError(null);
      try {
        const updated = await updateCreator(creatorId, values);
        setCreators((prev) =>
          prev.map((c) => (c.id === creatorId ? updated : c))
        );
        refreshTags();
        return true;
      } catch (err) {
        setSubmitError(formatError(err));
        return false;
      } finally {
        setSubmitting(false);
      }
    },
    [refreshTags]
  );

  /** 删除 UP 主，成功返回 true */
  const removeCreator = useCallback(
    async (creatorId: number): Promise<boolean> => {
      setSubmitting(true);
      setSubmitError(null);
      try {
        await deleteCreator(creatorId);
        setCreators((prev) => prev.filter((c) => c.id !== creatorId));
        return true;
      } catch (err) {
        setSubmitError(formatError(err));
        return false;
      } finally {
        setSubmitting(false);
      }
    },
    []
  );

  /** 切换 UP 主 启用/停用，成功返回 true（调用方据此关闭确认弹窗） */
  const toggleCreatorEnabled = useCallback(
    async (creator: Creator): Promise<boolean> => {
      setSubmitting(true);
      setSubmitError(null);
      try {
        const updated = await updateCreator(creator.id, {
          enabled: !creator.enabled,
        });
        setCreators((prev) =>
          prev.map((c) => (c.id === creator.id ? updated : c))
        );
        return true;
      } catch (err) {
        setSubmitError(formatError(err));
        return false;
      } finally {
        setSubmitting(false);
      }
    },
    []
  );

  /** 批量导入成功后追加新 UP 主 */
  const appendCreators = useCallback(
    (newCreators: Creator[]) => {
      setCreators((prev) => [...prev, ...newCreators]);
      refreshTags();
    },
    [refreshTags]
  );

  const clearSubmitError = useCallback(() => setSubmitError(null), []);

  return {
    creators,
    tags,
    loading,
    loadError,
    submitError,
    submitting,
    filterTagId,
    setFilterTagId,
    filteredCreators,
    totalUnwatched,
    addCreator,
    editCreator,
    removeCreator,
    toggleCreatorEnabled,
    appendCreators,
    clearSubmitError,
  };
}
