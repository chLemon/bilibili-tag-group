/**
 * API 客户端：封装对后端 REST 接口的请求。
 * 所有函数返回 Promise，调用方负责错误处理。
 */

// ---- 类型定义 ----

/** 标签 */
export interface Tag {
  id: number;
  name: string;
}

/** UP 主 */
export interface Creator {
  id: number;
  name: string;
  alias: string | null;
  profile_url: string;
  avatar_url: string | null;
  tag_ids: number[];
  video_count: number;
  synced_video_count: number;
  unwatched_count: number;
  last_synced_at: string | null;
}

/** 创建 UP 主请求体 */
export interface CreatorCreate {
  name: string;
  profile_url: string;
  avatar_url?: string;
  alias?: string;
  tag_ids?: number[];
}

/** 编辑 UP 主请求体（PATCH，全部可选） */
export interface CreatorUpdate {
  name?: string;
  alias?: string;
  tag_ids?: number[];
}

/** 视频 */
export interface Video {
  id: number;
  bvid: string;
  title: string;
  creator_id: number;
  creator_name: string;
  creator_alias: string | null;
  creator_avatar_url: string | null;
  video_url: string;
  cover_url: string | null;
  published_at: string;
  duration_seconds: number;
}

/** 视频详情（含已看状态） */
export interface VideoDetail {
  id: number;
  bvid: string;
  title: string;
  creator_id: number;
  creator_name: string;
  creator_alias: string | null;
  creator_avatar_url: string | null;
  video_url: string;
  cover_url: string | null;
  published_at: string;
  duration_seconds: number;
  status: number; // 0=未看, 1=已看, 2=不看
}

/** 同步日志 */
export interface SyncLog {
  id: number;
  scope: string;
  status: string;
  new_videos: number;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
}

/** 同步任务进度 */
export interface SyncTask {
  id: number;
  status: string;
  total_creators: number;
  completed_creators: number;
  current_creator_name: string | null;
  new_videos: number;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
  heartbeat_at: string | null;
}

/** 同步调度配置 */
export interface SyncSettings {
  enabled: boolean;
  interval_minutes: number;
  job_id: string;
}

// ---- 请求基础函数 ----

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  // 204 No Content 无响应体，直接返回 null
  if (res.status === 204) {
    return null as unknown as T;
  }
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) {
    return res.json() as Promise<T>;
  }
  return null as unknown as T;
}

// ---- 标签 API ----

/** 获取所有标签 */
export function fetchTags(): Promise<Tag[]> {
  return request<Tag[]>("/api/tags");
}

/** 获取某标签下的未看视频列表 */
export function fetchTagVideos(tagId: number): Promise<Video[]> {
  return request<Video[]>(`/api/tags/${tagId}/videos`);
}

/** 获取无标签 UP 主的未看视频列表 */
export function fetchUntaggedVideos(): Promise<Video[]> {
  return request<Video[]>("/api/tags/untagged/videos");
}

/** 创建标签 */
export function createTag(payload: { name: string }): Promise<Tag> {
  return request<Tag>("/api/tags", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ---- UP 主 API ----

/** 获取所有 UP 主 */
export function fetchCreators(): Promise<Creator[]> {
  return request<Creator[]>("/api/creators");
}

/** 根据主页 URL 从 B 站获取 UP 主昵称和头像 */
export function resolveCreatorName(
  profileUrl: string
): Promise<{ name: string; avatar_url: string | null }> {
  return request<{ name: string; avatar_url: string | null }>(
    `/api/creators/resolve-name?profile_url=${encodeURIComponent(profileUrl)}`
  );
}

/** 获取单个 UP 主 */
export function fetchCreator(creatorId: number): Promise<Creator> {
  return request<Creator>(`/api/creators/${creatorId}`);
}

/** 获取某 UP 主的所有视频（含已看状态） */
export function fetchCreatorVideos(creatorId: number): Promise<VideoDetail[]> {
  return request<VideoDetail[]>(`/api/creators/${creatorId}/videos`);
}

/** 添加 UP 主 */
export function createCreator(payload: CreatorCreate): Promise<Creator> {
  return request<Creator>("/api/creators", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** 编辑 UP 主 */
export function updateCreator(
  creatorId: number,
  payload: CreatorUpdate
): Promise<Creator> {
  return request<Creator>(`/api/creators/${creatorId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

// ---- 视频 API ----

/** 更新视频状态：0=未看, 1=已看, 2=不看 */
export function updateStatus(
  videoId: number,
  status: number
): Promise<void> {
  return request(`/api/videos/${videoId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

/** 批量更新某 UP 主的所有未看视频状态 */
export function batchUpdateCreatorVideos(
  creatorId: number,
  status: number
): Promise<{ creator_id: number; status: number; updated_count: number }> {
  return request(`/api/creators/${creatorId}/videos/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

// ---- 同步 API ----

/** 获取最近一次全量同步日志（无记录时返回 null） */
export function fetchLatestSync(): Promise<SyncLog | null> {
  return request<SyncLog | null>("/api/sync/latest");
}

/** 手动触发全量同步（异步，立即返回 SyncTask） */
export function runSync(): Promise<SyncTask> {
  return request<SyncTask>("/api/sync/run", { method: "POST" });
}

/** 查询当前（或最近一次）同步任务进度 */
export function fetchCurrentTask(): Promise<SyncTask | null> {
  return request<SyncTask | null>("/api/sync/task/current");
}

/** 获取同步调度配置 */
export function fetchSyncSettings(): Promise<SyncSettings> {
  return request<SyncSettings>("/api/sync/settings");
}

/** 立即同步标签 */
export interface ImmediateTag {
  id: number;
  tag_id: number;
  sync_mode: string;
}

/** 获取所有立即同步标签 */
export function fetchImmediateTags(): Promise<ImmediateTag[]> {
  return request<ImmediateTag[]>("/api/sync/immediate-tags");
}

/** 添加立即同步标签 */
export function addImmediateTag(tagId: number): Promise<ImmediateTag> {
  return request<ImmediateTag>(`/api/sync/immediate-tags?tag_id=${tagId}`, {
    method: "POST",
  });
}

/** 移除立即同步标签 */
export function removeImmediateTag(tagId: number): Promise<void> {
  return request<void>(`/api/sync/immediate-tags/${tagId}`, {
    method: "DELETE",
  });
}
