/**
 * VideoCard 组件测试
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import VideoCard from "../src/components/VideoCard";
import { Video } from "../src/api/client";

const sampleVideo: Video = {
  id: 1,
  bvid: "BV1xx411c7mD",
  title: "测试视频标题",
  creator_id: 10,
  creator_name: "测试UP主",
  creator_alias: null,
  creator_avatar_url: null,
  video_url: "https://www.bilibili.com/video/BV1xx411c7mD",
  cover_url: null,
  published_at: "2024-06-01T12:00:00",
  duration_seconds: 185,
};

describe("VideoCard", () => {
  it("渲染视频标题与 UP 主名称", () => {
    render(<VideoCard video={sampleVideo} onMarkWatched={vi.fn()} onMarkIgnored={vi.fn()} />);
    expect(screen.getByText("测试视频标题")).toBeInTheDocument();
    expect(screen.getByText("测试UP主")).toBeInTheDocument();
  });

  it("渲染视频时长（3分5秒 = 03:05）", () => {
    render(<VideoCard video={sampleVideo} onMarkWatched={vi.fn()} onMarkIgnored={vi.fn()} />);
    expect(screen.getByText("03:05")).toBeInTheDocument();
  });

  it("渲染超过一小时的时长（3725秒 = 1:02:05）", () => {
    const v: Video = { ...sampleVideo, duration_seconds: 3725 };
    render(<VideoCard video={v} onMarkWatched={vi.fn()} onMarkIgnored={vi.fn()} />);
    expect(screen.getByText("1:02:05")).toBeInTheDocument();
  });

  it("标题为跳转链接", () => {
    render(<VideoCard video={sampleVideo} onMarkWatched={vi.fn()} onMarkIgnored={vi.fn()} />);
    const link = screen.getByRole("link", { name: "测试视频标题" });
    expect(link).toHaveAttribute("href", sampleVideo.video_url);
  });

  it('点击"已看"按钮时调用 onMarkWatched 并传入 video.id', async () => {
    const onMarkWatched = vi.fn();
    render(<VideoCard video={sampleVideo} onMarkWatched={onMarkWatched} onMarkIgnored={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "已看" }));
    await waitFor(() => {
      expect(onMarkWatched).toHaveBeenCalledWith(sampleVideo.id);
    });
  });

  it('点击"不看"按钮时调用 onMarkIgnored 并传入 video.id', async () => {
    const onMarkIgnored = vi.fn();
    render(<VideoCard video={sampleVideo} onMarkWatched={vi.fn()} onMarkIgnored={onMarkIgnored} />);
    await userEvent.click(screen.getByRole("button", { name: "不看" }));
    await waitFor(() => {
      expect(onMarkIgnored).toHaveBeenCalledWith(sampleVideo.id);
    });
  });
});
