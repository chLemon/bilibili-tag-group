/**
 * utils/format 单元测试。
 * 重点回归：naive UTC 日期必须按 UTC 解析（东八区差 8 小时的坑）。
 */
import { describe, it, expect } from "vitest";
import { displayName, formatDate, formatDuration, formatError } from "../src/utils/format";

describe("formatDuration", () => {
  it("不足一小时用 mm:ss", () => {
    expect(formatDuration(0)).toBe("00:00");
    expect(formatDuration(65)).toBe("01:05");
    expect(formatDuration(3599)).toBe("59:59");
  });

  it("超过一小时用 h:mm:ss", () => {
    expect(formatDuration(3600)).toBe("1:00:00");
    expect(formatDuration(3661)).toBe("1:01:01");
  });
});

describe("formatDate", () => {
  it("naive UTC 按 UTC 解析，不偏移 8 小时", () => {
    // 2024-01-01 16:30 UTC = 北京时间 2024-01-02 00:30
    // 若被当本地时间解析会显示 1 日，正确应显示 2 日（东八区环境下）
    const result = formatDate("2024-01-01T16:30:00");
    const expected = new Date("2024-01-01T16:30:00Z").toLocaleDateString("zh-CN");
    expect(result).toBe(expected);
  });
});

describe("displayName", () => {
  it("无别名只显示原名", () => {
    expect(displayName({ name: "影视飓风", alias: null })).toBe("影视飓风");
  });

  it("有别名显示「别名（原名）」", () => {
    expect(displayName({ name: "Tim", alias: "影视飓风" })).toBe("影视飓风（Tim）");
  });
});

describe("formatError", () => {
  it("Error 取 message", () => {
    expect(formatError(new Error("boom"))).toBe("boom");
  });

  it("非 Error 转字符串", () => {
    expect(formatError("plain")).toBe("plain");
    expect(formatError(42)).toBe("42");
  });
});
