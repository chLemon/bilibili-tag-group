/**
 * 展示格式化工具：时长、日期、UP 主显示名、错误消息。
 * 日期解析统一走 parseUtc（后端时间是 naive UTC，直接 new Date 会差 8 小时）。
 */
import { parseUtc } from "./time";

/** 秒数格式化为 mm:ss 或 h:mm:ss */
export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

/** naive UTC ISO 字符串格式化为本地日期 */
export function formatDate(iso: string): string {
  return new Date(parseUtc(iso)).toLocaleDateString("zh-CN");
}

/** UP 主显示名：有别名时显示「别名（原名）」，否则只显示原名 */
export function displayName(c: { name: string; alias?: string | null }): string {
  return c.alias ? `${c.alias}（${c.name}）` : c.name;
}

/** 统一错误消息提取：Error 取 message，其余 String 化 */
export function formatError(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}
