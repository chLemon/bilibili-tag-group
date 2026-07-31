/**
 * 时间工具：后端时间字段统一为 naive UTC（无时区后缀的 ISO 字符串）。
 * 直接 new Date(iso) 会被当作本地时间解析，必须补 "Z" 按 UTC 解析。
 */

/** 将 naive UTC ISO 字符串解析为时间戳（毫秒） */
export function parseUtc(iso: string): number {
  const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasTz ? iso : iso + "Z").getTime();
}

/** 格式化为本地日期时间字符串 */
export function formatLocalDateTime(iso: string): string {
  return new Date(parseUtc(iso)).toLocaleString("zh-CN");
}

/** 转换为相对时间描述（刚刚 / N 分钟前 / N 小时前 / N 天前 / N 个月前） */
export function formatRelativeTime(iso: string): string {
  const diffMs = Date.now() - parseUtc(iso);
  if (diffMs < 60_000) return "刚刚";

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes} 分钟前`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;

  return `${Math.floor(days / 30)} 个月前`;
}
