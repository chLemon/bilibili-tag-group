"""路由集成测试：通过 TestClient 验证 API 端点行为。"""

from datetime import datetime
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.main import app


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

    def test_create_creator_with_plain_uid_normalizes_to_url(self, client):
        """只输入 uid 时，存储的 profile_url 应规范化为空间 URL。"""
        response = client.post(
            "/api/creators",
            json={"name": "影视飓风", "profile_url": "946974"},
        )
        assert response.status_code == 201
        assert response.json()["profile_url"] == "https://space.bilibili.com/946974"


class TestResolveName:
    """GET /api/creators/resolve-name 测试。"""

    def test_resolve_name_returns_info(self, client, mock_fetcher):
        mock_fetcher.fetch_creator_info = AsyncMock(
            return_value={"name": "某UP", "avatar_url": "https://x/a.jpg", "video_count": 10}
        )
        response = client.get(
            "/api/creators/resolve-name",
            params={"profile_url": "https://space.bilibili.com/12345"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "某UP"
        assert response.json()["avatar_url"] == "https://x/a.jpg"

    def test_resolve_name_invalid_url_returns_400(self, client):
        response = client.get("/api/creators/resolve-name", params={"profile_url": "not-a-url"})
        assert response.status_code == 400


class TestBatchCreateCreators:
    """POST /api/creators/batch 测试。"""

    def test_batch_create_success(self, client, mock_fetcher):
        mock_fetcher.fetch_creator_info = AsyncMock(
            return_value={
                "name": "UP1",
                "avatar_url": "https://example.com/avatar.png",
                "video_count": 3,
            }
        )
        response = client.post(
            "/api/creators/batch",
            json={"items": [{"uid": "123", "tag_names": ["游戏"]}]},
        )
        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["success"] is True
        assert result["creator"]["name"] == "UP1"
        assert result["creator"]["tag_ids"] != []

    def test_batch_create_with_name_and_avatar_prefers_user_values(self, client, mock_fetcher):
        """用户传 name + avatar_url 时优先用用户传的值；但仍 fetch 拿 video_count。"""
        mock_fetcher.fetch_creator_info = AsyncMock(
            return_value={
                "name": "FetchedName",
                "avatar_url": "https://example.com/fetched.png",
                "video_count": 7,
            }
        )
        response = client.post(
            "/api/creators/batch",
            json={
                "items": [
                    {
                        "uid": "123",
                        "name": "UP1",
                        "avatar_url": "https://i0.hdslb.com/bfs/face/abc.jpg",
                    }
                ]
            },
        )
        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["success"] is True
        assert result["creator"]["name"] == "UP1"
        assert result["creator"]["avatar_url"] == "https://i0.hdslb.com/bfs/face/abc.jpg"
        assert result["creator"]["video_count"] == 7
        mock_fetcher.fetch_creator_info.assert_called_once()

    def test_batch_create_fetch_failure(self, client, mock_fetcher):
        from app.fetcher.playwright_fetcher import FetchError

        mock_fetcher.fetch_creator_info = AsyncMock(side_effect=FetchError("被风控"))
        response = client.post("/api/creators/batch", json={"items": [{"uid": "123"}]})
        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["success"] is False
        assert "被风控" in result["error"]


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


class TestDeleteCreator:
    """DELETE /api/creators/{creator_id} 测试。"""

    def test_delete_creator_cascades(self, client, store, seeded_data):
        """删除 UP 主应级联清理标签关联、视频与观看状态，但保留标签本身。"""
        response = client.delete(f"/api/creators/{seeded_data.creator_id}")
        assert response.status_code == 204

        assert store.creators.all() == []
        assert store.creator_tags.all() == []
        assert store.videos.all() == []
        assert store.video_statuses.all() == []
        assert len(store.tags.all()) == 1

    def test_delete_creator_not_found(self, client):
        response = client.delete("/api/creators/99999")
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

    def test_list_tags_includes_unwatched_count(self, client, seeded_data):
        """标签列表应包含各标签的未看视频数。"""
        response = client.get("/api/tags")
        assert response.json()[0]["unwatched_count"] == 1


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
            f"/api/videos/{seeded_data.video_id}/status",
            json={"status": 1},
        )
        assert mark_resp.status_code == 200

        list_resp = client.get(f"/api/tags/{seeded_data.tag_id}/videos")
        assert list_resp.json() == []


# ──────────────────────────────────────────────
# Videos 路由
# ──────────────────────────────────────────────


class TestUpdateStatus:
    """PATCH /api/videos/{video_id}/status 测试。"""

    def test_update_status_watched(self, client, seeded_data):
        response = client.patch(
            f"/api/videos/{seeded_data.video_id}/status",
            json={"status": 1},
        )
        assert response.status_code == 200
        assert response.json()["status"] == 1

    def test_update_status_unwatched(self, client, seeded_data):
        """标记回未看后，status 应为 0。"""
        client.patch(
            f"/api/videos/{seeded_data.video_id}/status",
            json={"status": 1},
        )
        response = client.patch(
            f"/api/videos/{seeded_data.video_id}/status",
            json={"status": 0},
        )
        assert response.status_code == 200
        assert response.json()["status"] == 0

    def test_update_status_ignored(self, client, seeded_data):
        """标记为不看后，status 应为 2。"""
        response = client.patch(
            f"/api/videos/{seeded_data.video_id}/status",
            json={"status": 2},
        )
        assert response.status_code == 200
        assert response.json()["status"] == 2

    def test_update_status_not_found(self, client):
        response = client.patch("/api/videos/99999/status", json={"status": 1})
        assert response.status_code == 404


# ──────────────────────────────────────────────
# Sync 路由
# ──────────────────────────────────────────────


class TestSyncLatest:
    """GET /api/sync/latest 测试。"""

    def test_returns_empty_list_when_no_sync_records(self, client):
        response = client.get("/api/sync/latest")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_latest_sync_logs(self, client, store, seeded_data):
        """返回最近若干条任务，按开始时间倒序，含全量与单 UP 主。"""
        from app.domains.sync.models import SyncTask

        all_task = SyncTask(
            scope="all",
            status="completed",
            new_videos=2,
            total_creators=0,
            completed_creators=0,
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            finished_at=datetime(2026, 1, 1, 10, 1, 0),
            heartbeat_at=datetime(2026, 1, 1, 10, 1, 0),
        )
        creator_task = SyncTask(
            scope="creator",
            creator_id=seeded_data.creator_id,
            status="completed",
            new_videos=3,
            total_creators=1,
            completed_creators=1,
            started_at=datetime(2026, 1, 1, 11, 0, 0),
            finished_at=datetime(2026, 1, 1, 11, 0, 30),
            heartbeat_at=datetime(2026, 1, 1, 11, 0, 30),
        )
        await store.sync_tasks.add(all_task)
        await store.sync_tasks.add(creator_task)

        response = client.get("/api/sync/latest")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        # 倒序：creator_task 在前
        assert body[0]["scope"] == "creator"
        assert body[0]["creator_id"] == seeded_data.creator_id
        assert body[0]["creator_name"] == "测试UP主"
        assert body[1]["scope"] == "all"
        assert body[1]["creator_name"] is None

    async def test_limit_param_caps_at_20(self, client, store):
        """limit 超过 20 时上限 20，少于 1 时下限 1。"""
        from app.domains.sync.models import SyncTask

        for i in range(25):
            await store.sync_tasks.add(
                SyncTask(
                    scope="all",
                    status="completed",
                    started_at=datetime(2026, 1, 1, 10, i, 0),
                )
            )

        response = client.get("/api/sync/latest?limit=100")
        assert response.status_code == 200
        assert len(response.json()) == 20

        response = client.get("/api/sync/latest?limit=0")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestSyncRun:
    """POST /api/sync/run 测试。"""

    def test_run_sync_returns_task(self, client):
        """手动触发全量同步，返回 SyncTask。"""
        response = client.post("/api/sync/run")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] in ("running", "completed")

    def test_run_sync_with_real_db_no_creators(self, client):
        """无 creator 时全量同步立即完成。"""
        response = client.post("/api/sync/run")
        assert response.status_code == 200
        body = response.json()
        assert body["total_creators"] == 0


class TestSyncSingleCreator:
    """POST /api/sync/creators/{id} 测试。"""

    async def test_sync_single_creator_returns_task(self, client, store, seeded_data):
        """触发单 UP 主同步返回 scope=creator 的任务。"""
        response = client.post(f"/api/sync/creators/{seeded_data.creator_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["scope"] == "creator"
        assert body["creator_id"] == seeded_data.creator_id
        assert body["status"] in ("running", "completed")

    async def test_sync_single_creator_not_found(self, client):
        """UP 主不存在返回 404。"""
        response = client.post("/api/sync/creators/99999")
        assert response.status_code == 404

    async def test_sync_single_creator_disabled_returns_400(
        self, client, store, seeded_data
    ):
        """停用 UP 主返回 400。"""
        await store.creators.update(seeded_data.creator_id, enabled=False)
        response = client.post(f"/api/sync/creators/{seeded_data.creator_id}")
        assert response.status_code == 400

    async def test_sync_single_creator_idempotent(self, client, store, seeded_data):
        """同 UP 主已有 running 的单 UP 主任务时幂等返回现有。"""
        from datetime import datetime

        from app.domains.sync.models import SyncTask

        existing = SyncTask(
            scope="creator",
            creator_id=seeded_data.creator_id,
            status="running",
            total_creators=1,
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            heartbeat_at=datetime(2026, 1, 1, 10, 0, 0),
        )
        await store.sync_tasks.add(existing)

        response = client.post(f"/api/sync/creators/{seeded_data.creator_id}")
        assert response.status_code == 200
        assert response.json()["id"] == existing.id


class TestSyncConflict:
    """全局只有一个同步任务能 running 的冲突测试。"""

    async def _seed_running(
        self, store, *, scope: str, creator_id: int | None = None
    ):
        """插入一条 running 任务，绕过 service 层直接造状态。"""
        from app.domains.sync.models import SyncTask

        task = SyncTask(
            scope=scope,
            creator_id=creator_id,
            status="running",
            total_creators=1 if scope == "creator" else 0,
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            heartbeat_at=datetime(2026, 1, 1, 10, 0, 0),
        )
        await store.sync_tasks.add(task)
        return task

    async def test_full_sync_conflicts_with_running_single_creator(
        self, client, store, seeded_data
    ):
        """单 UP 主任务在跑时，触发全量同步返回 409。"""
        await self._seed_running(store, scope="creator", creator_id=seeded_data.creator_id)
        response = client.post("/api/sync/run")
        assert response.status_code == 409

    async def test_single_creator_conflicts_with_running_full_sync(
        self, client, store, seeded_data
    ):
        """全量任务在跑时，触发单 UP 主同步返回 409。"""
        await self._seed_running(store, scope="all")
        response = client.post(f"/api/sync/creators/{seeded_data.creator_id}")
        assert response.status_code == 409

    async def test_single_creator_conflicts_with_other_running_single_creator(
        self, client, store, seeded_data
    ):
        """UP 主 A 的单 UP 主任务在跑时，触发 UP 主 B 的同步返回 409。"""
        from app.domains.creators.models import Creator

        other = Creator(
            name="其他UP主",
            profile_url="https://space.bilibili.com/99999",
            avatar_url="https://example.com/avatar2.png",
            video_count=0,
        )
        await store.creators.add(other)

        await self._seed_running(store, scope="creator", creator_id=seeded_data.creator_id)
        response = client.post(f"/api/sync/creators/{other.id}")
        assert response.status_code == 409


class TestSyncSettings:
    """GET /api/sync/settings 测试。"""

    def test_returns_200(self, client):
        """接口应正常返回 200。"""
        response = client.get("/api/sync/settings")
        assert response.status_code == 200

    def test_returns_required_fields(self, client):
        """响应体应包含 enabled、interval_minutes、job_id。"""
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
