"""路由集成测试：通过 TestClient 验证 API 端点行为。"""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.fetcher.models import FetchedVideo
from datetime import datetime


def test_healthcheck_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ──────────────────────────────────────────────
# Creators 路由
# ──────────────────────────────────────────────

class TestCreateCreator:
    """POST /api/creators 测试。"""

    def test_create_creator_returns_201(self, client):
        response = client.post(
            "/api/creators",
            json={"name": "影视飓风", "profile_url": "https://space.bilibili.com/946974"},
        )
        assert response.status_code == 201

    def test_create_creator_response_fields(self, client):
        response = client.post(
            "/api/creators",
            json={"name": "影视飓风", "profile_url": "https://space.bilibili.com/946974"},
        )
        body = response.json()
        assert body["name"] == "影视飓风"
        assert body["profile_url"] == "https://space.bilibili.com/946974"
        assert body["enabled"] is True
        assert "id" in body

    def test_create_creator_with_tag_ids(self, client, seeded_data):
        """创建 UP 主时可以同时关联标签。"""
        response = client.post(
            "/api/creators",
            json={
                "name": "新UP主",
                "profile_url": "https://space.bilibili.com/999888",
                "tag_ids": [seeded_data.tag_id],
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert seeded_data.tag_id in body["tag_ids"]


class TestListCreators:
    """GET /api/creators 测试。"""

    def test_list_creators_empty(self, client):
        response = client.get("/api/creators")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_creators_returns_all(self, client, seeded_data):
        response = client.get("/api/creators")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == seeded_data.creator_id


class TestUpdateCreator:
    """PATCH /api/creators/{creator_id} 测试。"""

    def test_update_creator_name(self, client, seeded_data):
        response = client.patch(
            f"/api/creators/{seeded_data.creator_id}",
            json={"name": "改名后的UP主"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "改名后的UP主"

    def test_update_creator_enabled(self, client, seeded_data):
        response = client.patch(
            f"/api/creators/{seeded_data.creator_id}",
            json={"enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False

    def test_update_creator_tag_ids(self, client, seeded_data):
        """更新 tag_ids 应完整替换现有标签关联。"""
        response = client.patch(
            f"/api/creators/{seeded_data.creator_id}",
            json={"tag_ids": []},
        )
        assert response.status_code == 200
        assert response.json()["tag_ids"] == []

    def test_update_creator_not_found(self, client):
        response = client.patch("/api/creators/99999", json={"name": "不存在"})
        assert response.status_code == 404


class TestSyncCreatorRoute:
    """POST /api/creators/{creator_id}/sync 测试。"""

    def test_sync_creator_returns_new_videos_count(self, client, seeded_data):
        """手动同步 UP 主时返回新增视频数量。"""
        with patch("app.routers.creators._sync_svc") as mock_svc:
            mock_svc.sync_creator.return_value = 3
            response = client.post(f"/api/creators/{seeded_data.creator_id}/sync")
        assert response.status_code == 200
        body = response.json()
        assert body["creator_id"] == seeded_data.creator_id
        assert body["new_videos"] == 3

    def test_sync_creator_not_found(self, client):
        response = client.post("/api/creators/99999/sync")
        assert response.status_code == 404


# ──────────────────────────────────────────────
# Tags 路由
# ──────────────────────────────────────────────

class TestListTags:
    """GET /api/tags 测试。"""

    def test_list_tags_empty(self, client):
        response = client.get("/api/tags")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_tags_returns_existing(self, client, seeded_data):
        response = client.get("/api/tags")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["id"] == seeded_data.tag_id


class TestCreateTag:
    """POST /api/tags 测试。"""

    def test_create_tag_returns_201(self, client):
        response = client.post("/api/tags", json={"name": "科技"})
        assert response.status_code == 201

    def test_create_tag_response_fields(self, client):
        response = client.post("/api/tags", json={"name": "生活"})
        body = response.json()
        assert body["name"] == "生活"
        assert "id" in body

    def test_create_tag_rejects_blank_name(self, client):
        response = client.post("/api/tags", json={"name": "   "})
        assert response.status_code == 422


class TestTagVideos:
    """GET /api/tags/{tag_id}/videos 测试。"""

    def test_returns_unwatched_videos_for_tag(self, client, seeded_data):
        """标签页返回该标签下 UP 主的未看视频。"""
        response = client.get(f"/api/tags/{seeded_data.tag_id}/videos")
        assert response.status_code == 200
        videos = response.json()
        assert len(videos) == 1
        assert videos[0]["id"] == seeded_data.video_id
        assert videos[0]["title"] == "种子视频"
        assert videos[0]["creator_name"] == "测试UP主"

    def test_tag_videos_includes_required_fields(self, client, seeded_data):
        """视频条目至少包含标题、UP 主名、发布时间、时长。"""
        response = client.get(f"/api/tags/{seeded_data.tag_id}/videos")
        video = response.json()[0]
        assert "title" in video
        assert "creator_name" in video
        assert "published_at" in video
        assert "duration_seconds" in video

    def test_returns_empty_for_unknown_tag(self, client):
        response = client.get("/api/tags/99999/videos")
        assert response.status_code == 200
        assert response.json() == []

    def test_mark_video_watched_removes_from_tag_feed(self, client, seeded_data):
        """标记已看后，该视频不再出现在标签未看列表中。"""
        mark_resp = client.patch(
            f"/api/videos/{seeded_data.video_id}/watched",
            json={"watched": True},
        )
        assert mark_resp.status_code == 200

        list_resp = client.get(f"/api/tags/{seeded_data.tag_id}/videos")
        assert list_resp.json() == []


# ──────────────────────────────────────────────
# Videos 路由
# ──────────────────────────────────────────────

class TestMarkWatched:
    """PATCH /api/videos/{video_id}/watched 测试。"""

    def test_mark_watched_true(self, client, seeded_data):
        response = client.patch(
            f"/api/videos/{seeded_data.video_id}/watched",
            json={"watched": True},
        )
        assert response.status_code == 200
        assert response.json()["watched"] is True

    def test_mark_watched_false(self, client, seeded_data):
        """标记回未看后，watched 应为 False。"""
        # 先标记已看
        client.patch(
            f"/api/videos/{seeded_data.video_id}/watched",
            json={"watched": True},
        )
        # 再标记回未看
        response = client.patch(
            f"/api/videos/{seeded_data.video_id}/watched",
            json={"watched": False},
        )
        assert response.status_code == 200
        assert response.json()["watched"] is False

    def test_mark_watched_not_found(self, client):
        response = client.patch("/api/videos/99999/watched", json={"watched": True})
        assert response.status_code == 404


# ──────────────────────────────────────────────
# Sync 路由
# ──────────────────────────────────────────────

class TestSyncLatest:
    """GET /api/sync/latest 测试。"""

    def test_returns_null_when_no_sync_records(self, client):
        response = client.get("/api/sync/latest")
        assert response.status_code == 200
        assert response.json() is None

    def test_returns_latest_sync_log(self, client, db_session, seeded_data):
        """有同步记录时返回最近一条。"""
        from app.models.sync_log import SyncLog
        log = SyncLog(
            scope="all",
            status="success",
            new_videos=2,
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            finished_at=datetime(2026, 1, 1, 10, 1, 0),
        )
        db_session.add(log)
        db_session.commit()

        response = client.get("/api/sync/latest")
        assert response.status_code == 200
        body = response.json()
        assert body["scope"] == "all"
        assert body["status"] == "success"
        assert body["new_videos"] == 2


class TestSyncRun:
    """POST /api/sync/run 测试（异步模式：后台线程执行，立即返回 SyncTask）。"""

    def test_run_sync_returns_task(self, client):
        """手动触发全量同步，返回 SyncTask（异步模式）。"""
        with patch("app.routers.sync._sync_svc") as mock_svc:
            from app.models.sync_task import SyncTask
            fake_task = SyncTask(
                id=1,
                status="running",
                total_creators=0,
                completed_creators=0,
                new_videos=0,
                started_at=datetime(2026, 4, 18, 0, 0, 0),
            )
            mock_svc.start_async_sync.return_value = fake_task
            response = client.post("/api/sync/run")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "running"

    def test_run_sync_with_real_db_no_creators(self, client):
        """无 creator 时全量同步立即完成。"""
        response = client.post("/api/sync/run")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("running", "completed")
        assert body["total_creators"] == 0


class TestSyncSettings:
    """GET /api/sync/settings 测试：返回调度配置与状态。"""

    def test_returns_200(self, client):
        """接口应正常返回 200。"""
        response = client.get("/api/sync/settings")
        assert response.status_code == 200

    def test_returns_required_fields(self, client):
        """响应体应包含 enabled、interval_minutes、job_id 三个字段。"""
        response = client.get("/api/sync/settings")
        body = response.json()
        assert "enabled" in body
        assert "interval_minutes" in body
        assert "job_id" in body

    def test_enabled_is_bool(self, client):
        """enabled 字段应为布尔值。"""
        response = client.get("/api/sync/settings")
        body = response.json()
        assert isinstance(body["enabled"], bool)

    def test_interval_minutes_is_int(self, client):
        """interval_minutes 字段应为整数。"""
        response = client.get("/api/sync/settings")
        body = response.json()
        assert isinstance(body["interval_minutes"], int)
        assert body["interval_minutes"] > 0

    def test_job_id_is_sync_all(self, client):
        """job_id 应为 'sync-all'。"""
        response = client.get("/api/sync/settings")
        body = response.json()
        assert body["job_id"] == "sync-all"
