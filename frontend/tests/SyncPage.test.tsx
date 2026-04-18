/**
 * SyncPage 页面测试
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SyncPage from "../src/pages/SyncPage";
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

beforeEach(() => {
  vi.mocked(client.fetchLatestSync).mockResolvedValue(mockLog);
  vi.mocked(client.fetchSyncSettings).mockResolvedValue(mockSettings);
  vi.mocked(client.runSync).mockResolvedValue({
    ...mockLog,
    id: 2,
    new_videos: 2,
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

  it("展示最近同步日志", async () => {
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/最近同步结果/)).toBeInTheDocument();
      expect(screen.getByText(/新增视频：5 条/)).toBeInTheDocument();
    });
  });

  it('展示"立即同步"按钮', async () => {
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByRole("button", { name: "立即同步" }));
    expect(screen.getByRole("button", { name: "立即同步" })).toBeEnabled();
  });

  it('点击"立即同步"后更新日志（new_videos 变为 2）', async () => {
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText(/新增视频：5 条/));
    await userEvent.click(screen.getByRole("button", { name: "立即同步" }));
    await waitFor(() => {
      expect(screen.getByText(/新增视频：2 条/)).toBeInTheDocument();
    });
  });

  it('同步状态为 failed 时展示中文"失败"', async () => {
    vi.mocked(client.fetchLatestSync).mockResolvedValueOnce({
      ...mockLog,
      status: "failed",
      error_message: "网络超时",
    });
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("失败")).toBeInTheDocument();
    });
  });

  it("无同步记录时展示提示文字", async () => {
    vi.mocked(client.fetchLatestSync).mockResolvedValueOnce(null);
    render(
      <MemoryRouter>
        <SyncPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/暂无同步记录/)).toBeInTheDocument();
    });
  });
});
