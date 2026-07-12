/**
 * CreatorsPage 页面测试
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import CreatorsPage from "../src/pages/CreatorsPage";
import * as client from "../src/api/client";

vi.mock("../src/api/client");

const mockTags: client.Tag[] = [
  { id: 1, name: "科技" },
];

const mockCreators: client.Creator[] = [
  {
    id: 1,
    name: "测试UP主",
    alias: null,
    profile_url: "https://space.bilibili.com/123",
    avatar_url: null,
    tag_ids: [1],
    video_count: 5,
    unwatched_count: 2,
    last_synced_at: "2026-07-12T08:00:00",
  },
];

beforeEach(() => {
  vi.mocked(client.fetchCreators).mockResolvedValue(mockCreators);
  vi.mocked(client.fetchTags).mockResolvedValue(mockTags);
  vi.mocked(client.createCreator).mockResolvedValue({
    id: 2,
    name: "新UP主",
    alias: null,
    profile_url: "https://space.bilibili.com/456",
    avatar_url: null,
    tag_ids: [],
    video_count: 0,
    unwatched_count: 0,
    last_synced_at: null,
  });
  vi.mocked(client.updateCreator).mockResolvedValue({
    ...mockCreators[0],
    avatar_url: null,
  });
  vi.mocked(client.createTag).mockResolvedValue({
    id: 2,
    name: "游戏",
  });
  vi.mocked(client.resolveCreatorName).mockResolvedValue({
    name: "新UP主",
    avatar_url: null,
  });
});

describe("CreatorsPage", () => {
  it("加载后展示 UP 主列表", async () => {
    render(
      <MemoryRouter>
        <CreatorsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("测试UP主")).toBeInTheDocument();
    });
  });

  it('展示"添加 UP 主"按钮', async () => {
    render(
      <MemoryRouter>
        <CreatorsPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText("测试UP主"));
    expect(screen.getByRole("button", { name: /添加 UP 主/ })).toBeInTheDocument();
  });

  it('点击"添加 UP 主"按钮后展示表单', async () => {
    render(
      <MemoryRouter>
        <CreatorsPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText("测试UP主"));
    await userEvent.click(screen.getByRole("button", { name: /添加 UP 主/ }));
    expect(screen.getByPlaceholderText("https://space.bilibili.com/...")).toBeInTheDocument();
  });

  it("创建 UP 主失败时页面不被整页覆盖，内联展示错误消息", async () => {
    vi.mocked(client.createCreator).mockRejectedValueOnce(new Error("服务器错误"));
    render(
      <MemoryRouter>
        <CreatorsPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText("测试UP主"));
    await userEvent.click(screen.getByRole("button", { name: /添加 UP 主/ }));
    // 填写 URL 并获取信息
    await userEvent.type(
      screen.getByPlaceholderText("https://space.bilibili.com/..."),
      "https://space.bilibili.com/999"
    );
    await userEvent.click(screen.getByRole("button", { name: "获取信息" }));
    await userEvent.click(screen.getByRole("button", { name: "保存" }));
    await waitFor(() => {
      expect(screen.getByText("测试UP主")).toBeInTheDocument();
      expect(screen.getByText(/提交失败/)).toBeInTheDocument();
    });
  });

  it("展示标签名称（关联标签）", async () => {
    render(
      <MemoryRouter>
        <CreatorsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      const badges = screen.getAllByText("科技");
      expect(badges.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("在添加表单中创建新标签后自动选中", async () => {
    render(
      <MemoryRouter>
        <CreatorsPage />
      </MemoryRouter>
    );
    await waitFor(() => screen.getByText("测试UP主"));
    await userEvent.click(screen.getByRole("button", { name: /添加 UP 主/ }));
    await userEvent.type(screen.getByPlaceholderText("输入新标签名"), "游戏");
    await userEvent.click(screen.getByRole("button", { name: "创建并选中" }));

    await waitFor(() => {
      const chip = screen.getByRole("button", { name: "游戏" });
      expect(chip).toBeInTheDocument();
      expect(chip.className).toContain("form-tag-chip-active");
    });
  });
});
