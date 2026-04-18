/**
 * TagsPage 页面测试
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import TagsPage from "../src/pages/TagsPage";
import * as client from "../src/api/client";

// 模拟 API 模块
vi.mock("../src/api/client");

const mockTags: client.Tag[] = [
  { id: 1, name: "科技" },
  { id: 2, name: "音乐" },
];

const mockVideos: client.Video[] = [
  {
    id: 10,
    bvid: "BVabc",
    title: "科技视频1",
    creator_id: 1,
    creator_name: "科技UP",
    video_url: "https://bilibili.com/video/BVabc",
    published_at: "2024-01-01T00:00:00",
    duration_seconds: 60,
  },
];

beforeEach(() => {
  vi.mocked(client.fetchTags).mockResolvedValue(mockTags);
  vi.mocked(client.fetchTagVideos).mockResolvedValue(mockVideos);
  vi.mocked(client.updateWatched).mockResolvedValue(undefined);
});

describe("TagsPage", () => {
  it("加载后展示标签列表", async () => {
    render(
      <MemoryRouter>
        <TagsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("科技")).toBeInTheDocument();
      expect(screen.getByText("音乐")).toBeInTheDocument();
    });
  });

  it("默认选中第一个标签并加载视频", async () => {
    render(
      <MemoryRouter>
        <TagsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("科技视频1")).toBeInTheDocument();
    });
    expect(client.fetchTagVideos).toHaveBeenCalledWith(1);
  });

  it("点击其他标签时加载对应视频", async () => {
    render(
      <MemoryRouter>
        <TagsPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText("音乐"));
    await userEvent.click(screen.getByText("音乐"));
    await waitFor(() => {
      expect(client.fetchTagVideos).toHaveBeenCalledWith(2);
    });
  });

  it('点击"已看"后视频从列表消失', async () => {
    render(
      <MemoryRouter>
        <TagsPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText("科技视频1"));
    await userEvent.click(screen.getByRole("button", { name: "已看" }));
    await waitFor(() => {
      expect(screen.queryByText("科技视频1")).not.toBeInTheDocument();
    });
  });

  it("视频加载失败时标签列表仍显示，右侧展示错误信息", async () => {
    vi.mocked(client.fetchTagVideos).mockRejectedValueOnce(new Error("网络超时"));
    render(
      <MemoryRouter>
        <TagsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      // 标签列表仍保留
      expect(screen.getByText("科技")).toBeInTheDocument();
      expect(screen.getByText("音乐")).toBeInTheDocument();
      // 右侧展示视频加载错误
      expect(screen.getByText(/视频加载失败/)).toBeInTheDocument();
    });
  });

  it("无标签时展示引导提示", async () => {
    vi.mocked(client.fetchTags).mockResolvedValueOnce([]);
    render(
      <MemoryRouter>
        <TagsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/暂无标签/)).toBeInTheDocument();
    });
  });
});
