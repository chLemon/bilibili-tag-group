/**
 * SyncPage 页面测试
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { SyncPage } from "../src/features/sync";
import * as client from "../src/api/client";

vi.mock("../src/api/client");

const mockLog: client.SyncLog = {
  id: 1,
  scope: "all",
  status: "success",
  new_videos: 5,
  error_message: null,
  started_at: "2024-06-01T08:00:00",
  finished_at: "2024-06-01T08:01:00",
};

const mockSettings: client.SyncSettings = {
  enabled: true,
  interval_minutes: 60,
  job_id: "sync-all",
};

const mockTags: client.Tag[] = [
  { id: 1, name: "沙雕动画" },
  { id: 2, name: "科技" },
];

const mockImmediateTags: client.ImmediateTag[] = [
  { id: 1, tag_id: 1, sync_mode: "immediate" },
];

const completedTask: client.SyncTask = {
  id: 1,
  status: "completed",
  total_creators: 2,
  completed_creators: 2,
  current_creator_name: null,
  new_videos: 3,
  error_message: null,
  started_at: "2024-06-01T08:00:00",
  finished_at: "2024-06-01T08:05:00",
  heartbeat_at: "2024-06-01T08:05:00",
};

beforeEach(() => {
  vi.mocked(client.fetchLatestSync).mockResolvedValue(mockLog);
  vi.mocked(client.fetchSyncSettings).mockResolvedValue(mockSettings);
  vi.mocked(client.fetchImmediateTags).mockResolvedValue(mockImmediateTags);
  vi.mocked(client.fetchTags).mockResolvedValue(mockTags);
  vi.mocked(client.fetchCurrentTask).mockResolvedValue(completedTask);
  vi.mocked(client.runSync).mockResolvedValue({
    ...completedTask,
    id: 2,
    status: "completed",
  });
});

describe("SyncPage", () => {
  it("加载后展示调度配置", async () => {
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/每 60 分钟执行一次/)).toBeInTheDocument();
    });
  });

  it("展示最近同步记录", async () => {
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/最近同步记录/)).toBeInTheDocument();
      expect(screen.getByText("5 条")).toBeInTheDocument();
    });
  });

  it("展示同步完成状态", async () => {
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("同步完成")).toBeInTheDocument();
    });
  });

  it('展示"立即同步"按钮且可用', async () => {
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByRole("button", { name: "立即同步" }));
    expect(screen.getByRole("button", { name: "立即同步" })).toBeEnabled();
  });

  it("正在同步时按钮禁用", async () => {
    vi.mocked(client.fetchCurrentTask).mockResolvedValue({
      ...completedTask,
      status: "running",
      heartbeat_at: new Date().toISOString(),
    });
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByRole("button", { name: "同步中…" }));
    expect(screen.getByRole("button", { name: "同步中…" })).toBeDisabled();
  });

  it('点击"立即同步"后触发 runSync', async () => {
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByRole("button", { name: "立即同步" }));
    await userEvent.click(screen.getByRole("button", { name: "立即同步" }));
    expect(client.runSync).toHaveBeenCalled();
  });

  it("同步任务终止时展示特殊提示", async () => {
    vi.mocked(client.fetchCurrentTask).mockResolvedValue({
      ...completedTask,
      status: "running",
      heartbeat_at: new Date(Date.now() - 60 * 1000).toISOString(), // 60秒前
    });
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/同步任务已终止/)).toBeInTheDocument();
    });
  });
});
