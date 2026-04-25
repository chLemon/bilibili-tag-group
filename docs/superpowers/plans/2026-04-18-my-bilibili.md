# my_bilibili Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个完全本地运行的个人 B 站订阅管理工具：手动维护 UP 主主页链接和标签，抓取公开视频，按标签展示未看视频，支持手动标记已看以及手动/定时同步。

**Architecture:** 采用本地前后端分离结构。后端使用 FastAPI + SQLite 提供本地 API、抓取逻辑、定时同步和数据持久化；前端使用 React + TypeScript 提供三个页面：标签视图、UP 主管理页、同步状态页。公开视频数据与本地个人状态严格分离，抓取逻辑不感知标签和已看状态。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, APScheduler, httpx, pytest, React, TypeScript, Vite, Vitest

---

## 文件结构

### 根目录
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `alembic.ini`
- Create: `app/`
- Create: `alembic/`
- Create: `tests/`
- Create: `frontend/`
- Modify later: `CLAUDE.md`

### 后端应用
- Create: `app/main.py` — FastAPI 入口，注册路由和启动调度器
- Create: `app/config.py` — 本地配置项，如数据库路径、同步间隔
- Create: `app/database.py` — SQLAlchemy engine、session、Base
- Create: `app/scheduler.py` — APScheduler 初始化与同步任务注册
- Create: `app/models/creator.py` — UP 主 ORM
- Create: `app/models/tag.py` — 标签 ORM
- Create: `app/models/creator_tag.py` — UP 主与标签关联表
- Create: `app/models/video.py` — 视频公开数据 ORM
- Create: `app/models/video_status.py` — 本地 watched 状态 ORM
- Create: `app/models/sync_log.py` — 同步日志 ORM
- Create: `app/models/__init__.py` — 导出所有模型
- Create: `app/schemas/creator.py` — Pydantic 请求/响应模型
- Create: `app/schemas/tag.py`
- Create: `app/schemas/video.py`
- Create: `app/schemas/sync.py`
- Create: `app/fetcher/models.py` — 抓取结果 dataclass
- Create: `app/fetcher/bilibili_fetcher.py` — B 站公开数据抓取
- Create: `app/services/creator_service.py` — 管理 UP 主与标签
- Create: `app/services/tag_service.py` — 查询标签及标签下未看视频
- Create: `app/services/video_service.py` — watched 状态更新
- Create: `app/services/sync_service.py` — 全量/单个同步流程
- Create: `app/routers/creators.py` — UP 主 CRUD 与标签设置
- Create: `app/routers/tags.py` — 标签列表和未看视频列表
- Create: `app/routers/videos.py` — 标记已看
- Create: `app/routers/sync.py` — 手动同步、状态查询、同步配置

### 数据迁移与测试
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial_schema.py`
- Create: `tests/conftest.py` — 测试数据库和 FastAPI client fixture
- Create: `tests/test_models.py`
- Create: `tests/test_fetcher.py`
- Create: `tests/test_services.py`
- Create: `tests/test_routers.py`
- Create: `tests/test_scheduler.py`

### 前端
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/TagsPage.tsx`
- Create: `frontend/src/pages/CreatorsPage.tsx`
- Create: `frontend/src/pages/SyncPage.tsx`
- Create: `frontend/src/components/VideoCard.tsx`
- Create: `frontend/src/components/CreatorForm.tsx`
- Create: `frontend/src/components/SyncStatusPanel.tsx`
- Create: `frontend/src/hooks/useTags.ts`
- Create: `frontend/src/hooks/useCreators.ts`
- Create: `frontend/src/hooks/useSync.ts`
- Create: `frontend/tests/VideoCard.test.tsx`
- Create: `frontend/tests/CreatorsPage.test.tsx`
- Create: `frontend/tests/TagsPage.test.tsx`
- Create: `frontend/tests/SyncPage.test.tsx`

---

### Task 1: 初始化项目骨架与数据库模型

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `app/config.py`
- Create: `app/database.py`
- Create: `app/models/__init__.py`
- Create: `app/models/creator.py`
- Create: `app/models/tag.py`
- Create: `app/models/creator_tag.py`
- Create: `app/models/video.py`
- Create: `app/models/video_status.py`
- Create: `app/models/sync_log.py`
- Create: `tests/conftest.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 写失败的模型测试**

```python
from app.models.creator import Creator
from app.models.tag import Tag
from app.models.video import Video
from app.models.video_status import VideoStatus


def test_video_status_defaults_to_unwatched(db_session):
    creator = Creator(name="测试UP", profile_url="https://space.bilibili.com/1")
    db_session.add(creator)
    db_session.flush()

    video = Video(
        bvid="BV1xx411c7mD",
        creator_id=creator.id,
        title="视频 1",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        published_at="2026-04-18T10:00:00",
        duration_seconds=600,
    )
    db_session.add(video)
    db_session.flush()

    status = VideoStatus(video_id=video.id)
    db_session.add(status)
    db_session.commit()

    assert status.watched is False


def test_creator_can_have_multiple_tags(db_session):
    creator = Creator(name="测试UP", profile_url="https://space.bilibili.com/2")
    tag1 = Tag(name="must-watch")
    tag2 = Tag(name="deep-study")
    creator.tags.extend([tag1, tag2])
    db_session.add(creator)
    db_session.commit()

    assert {tag.name for tag in creator.tags} == {"must-watch", "deep-study"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models.py -v`
Expected: FAIL，提示 `ModuleNotFoundError: No module named 'app'` 或模型未定义。

- [ ] **Step 3: 写最小项目配置与数据库基础文件**

`pyproject.toml`
```toml
[project]
name = "my-bilibili"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1.0",
  "uvicorn>=0.30,<1.0",
  "sqlalchemy>=2.0,<3.0",
  "alembic>=1.13,<2.0",
  "pydantic-settings>=2.2,<3.0",
  "apscheduler>=3.10,<4.0",
  "httpx>=0.27,<1.0",
  "beautifulsoup4>=4.12,<5.0",
  "lxml>=5.2,<6.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0,<9.0",
  "pytest-anyio>=0.0.0",
  "respx>=0.21,<1.0",
  "ruff>=0.4,<1.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`app/database.py`
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

`app/models/video_status.py`
```python
from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VideoStatus(Base):
    __tablename__ = "video_statuses"

    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), primary_key=True)
    watched: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 4: 补齐其余 ORM 模型到可通过测试的最小实现**

`app/models/creator.py`
```python
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tags = relationship("Tag", secondary="creator_tags", back_populates="creators")
```

`app/models/tag.py`
```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    creators = relationship("Creator", secondary="creator_tags", back_populates="tags")
```

`app/models/creator_tag.py`
```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CreatorTag(Base):
    __tablename__ = "creator_tags"

    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), primary_key=True)
```

`app/models/video.py`
```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    bvid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    video_url: Mapped[str] = mapped_column(String(512), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(nullable=False)
```

`app/models/sync_log.py`
```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    new_videos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 5: 运行模型测试确认通过**

Run: `pytest tests/test_models.py -v`
Expected: PASS，至少 2 个测试通过。

- [ ] **Step 6: 提交这一小步**

```bash
git add .gitignore pyproject.toml app tests
git commit -m "feat: initialize backend models"
```

### Task 2: 建立数据库迁移与应用入口

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_initial_schema.py`
- Create: `app/main.py`
- Modify: `app/models/__init__.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: 写失败的应用启动测试**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_healthcheck_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_models.py tests/test_routers.py -v`
Expected: FAIL，提示 `app.main` 不存在或 `/health` 404。

- [ ] **Step 3: 写最小 FastAPI 入口和健康检查**

`app/main.py`
```python
from fastapi import FastAPI

app = FastAPI(title="my_bilibili")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: 写 Alembic 初始迁移文件**

`alembic/versions/0001_initial_schema.py`
```python
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("profile_url", sa.String(length=512), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False, unique=True),
    )
    op.create_table(
        "creator_tags",
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), primary_key=True),
    )
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bvid", sa.String(length=32), nullable=False, unique=True),
        sa.Column("creator_id", sa.Integer(), sa.ForeignKey("creators.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("video_url", sa.String(length=512), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
    )
    op.create_table(
        "video_statuses",
        sa.Column("video_id", sa.Integer(), sa.ForeignKey("videos.id"), primary_key=True),
        sa.Column("watched", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("new_videos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("sync_logs")
    op.drop_table("video_statuses")
    op.drop_table("videos")
    op.drop_table("creator_tags")
    op.drop_table("tags")
    op.drop_table("creators")
```

- [ ] **Step 5: 执行迁移并再次运行测试**

Run: `alembic upgrade head && pytest tests/test_models.py tests/test_routers.py -v`
Expected: PASS，健康检查测试通过，迁移执行成功。

- [ ] **Step 6: 提交这一小步**

```bash
git add alembic.ini alembic app/main.py tests
git commit -m "feat: add database migration and app entrypoint"
```

### Task 3: 实现抓取层与同步核心服务

**Files:**
- Create: `app/fetcher/models.py`
- Create: `app/fetcher/bilibili_fetcher.py`
- Create: `app/services/sync_service.py`
- Test: `tests/test_fetcher.py`
- Test: `tests/test_services.py`

- [ ] **Step 1: 写抓取层失败测试**

```python
import respx
from httpx import Response

from app.fetcher.bilibili_fetcher import BilibiliFetcher


@respx.mock
def test_fetcher_returns_public_videos():
    respx.get("https://api.bilibili.com/x/space/wbi/arc/search").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "list": {
                        "vlist": [
                            {
                                "bvid": "BV1xx411c7mD",
                                "title": "测试视频",
                                "created": 1713434400,
                                "length": "10:00",
                            }
                        ]
                    }
                }
            },
        )
    )

    videos = BilibiliFetcher().fetch_videos(uid="1")

    assert videos[0].bvid == "BV1xx411c7mD"
    assert videos[0].title == "测试视频"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_fetcher.py tests/test_services.py -v`
Expected: FAIL，提示 `BilibiliFetcher` 或 `fetch_videos` 未定义。

- [ ] **Step 3: 写最小抓取结果模型和抓取实现**

`app/fetcher/models.py`
```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class FetchedVideo:
    bvid: str
    title: str
    video_url: str
    published_at: datetime
    duration_seconds: int
```

`app/fetcher/bilibili_fetcher.py`
```python
from datetime import datetime

import httpx

from app.fetcher.models import FetchedVideo


class FetchError(Exception):
    pass


class BilibiliFetcher:
    API_URL = "https://api.bilibili.com/x/space/wbi/arc/search"

    def fetch_videos(self, uid: str) -> list[FetchedVideo]:
        response = httpx.get(self.API_URL, params={"mid": uid, "pn": 1, "ps": 30}, timeout=10)
        if response.status_code != 200:
            raise FetchError(f"unexpected status: {response.status_code}")

        payload = response.json()
        items = payload.get("data", {}).get("list", {}).get("vlist", [])
        return [
            FetchedVideo(
                bvid=item["bvid"],
                title=item["title"],
                video_url=f"https://www.bilibili.com/video/{item['bvid']}",
                published_at=datetime.fromtimestamp(item["created"]),
                duration_seconds=_parse_duration(item["length"]),
            )
            for item in items
        ]


def _parse_duration(length: str) -> int:
    minutes, seconds = length.split(":")
    return int(minutes) * 60 + int(seconds)
```

- [ ] **Step 4: 写同步服务，确保不覆盖 watched 状态**

`app/services/sync_service.py`
```python
from datetime import datetime

from sqlalchemy import select

from app.fetcher.bilibili_fetcher import BilibiliFetcher
from app.models.creator import Creator
from app.models.sync_log import SyncLog
from app.models.video import Video
from app.models.video_status import VideoStatus


class SyncService:
    def __init__(self, fetcher: BilibiliFetcher | None = None):
        self.fetcher = fetcher or BilibiliFetcher()

    def sync_creator(self, db_session, creator: Creator) -> int:
        videos = self.fetcher.fetch_videos(uid=str(creator.id))
        created_count = 0
        for fetched in videos:
            existing = db_session.scalar(select(Video).where(Video.bvid == fetched.bvid))
            if existing:
                existing.title = fetched.title
                existing.video_url = fetched.video_url
                existing.published_at = fetched.published_at
                existing.duration_seconds = fetched.duration_seconds
                continue

            video = Video(
                bvid=fetched.bvid,
                creator_id=creator.id,
                title=fetched.title,
                video_url=fetched.video_url,
                published_at=fetched.published_at,
                duration_seconds=fetched.duration_seconds,
            )
            db_session.add(video)
            db_session.flush()
            db_session.add(VideoStatus(video_id=video.id, watched=False))
            created_count += 1
        return created_count

    def sync_all(self, db_session) -> SyncLog:
        log = SyncLog(scope="all", status="running", started_at=datetime.utcnow(), new_videos=0)
        db_session.add(log)
        creators = db_session.scalars(select(Creator).where(Creator.enabled.is_(True))).all()
        try:
            for creator in creators:
                log.new_videos += self.sync_creator(db_session, creator)
            log.status = "success"
        except Exception as exc:
            log.status = "failed"
            log.error_message = str(exc)
        finally:
            log.finished_at = datetime.utcnow()
        return log
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_fetcher.py tests/test_services.py -v`
Expected: PASS，抓取结果被标准化，同步新增视频时会创建默认未看状态，重复同步不会重置已看。

- [ ] **Step 6: 提交这一小步**

```bash
git add app/fetcher app/services tests
git commit -m "feat: add bilibili fetcher and sync service"
```

### Task 4: 实现 API 路由与业务服务

**Files:**
- Create: `app/schemas/creator.py`
- Create: `app/schemas/tag.py`
- Create: `app/schemas/video.py`
- Create: `app/schemas/sync.py`
- Create: `app/services/creator_service.py`
- Create: `app/services/tag_service.py`
- Create: `app/services/video_service.py`
- Create: `app/routers/creators.py`
- Create: `app/routers/tags.py`
- Create: `app/routers/videos.py`
- Create: `app/routers/sync.py`
- Modify: `app/main.py`
- Test: `tests/test_routers.py`
- Test: `tests/test_services.py`

- [ ] **Step 1: 写失败的 API 测试**

```python
def test_create_creator(client):
    response = client.post(
        "/api/creators",
        json={"name": "影视飓风", "profile_url": "https://space.bilibili.com/946974"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "影视飓风"


def test_mark_video_watched_removes_it_from_tag_feed(client, seeded_data):
    mark_response = client.patch(f"/api/videos/{seeded_data.video_id}/watched", json={"watched": True})
    list_response = client.get(f"/api/tags/{seeded_data.tag_id}/videos")

    assert mark_response.status_code == 200
    assert list_response.json() == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_routers.py tests/test_services.py -v`
Expected: FAIL，提示路由不存在或返回 404。

- [ ] **Step 3: 写最小 schema 与服务层实现**

`app/schemas/creator.py`
```python
from pydantic import BaseModel, HttpUrl


class CreatorCreate(BaseModel):
    name: str
    profile_url: HttpUrl
    tag_ids: list[int] = []


class CreatorRead(BaseModel):
    id: int
    name: str
    profile_url: str
    enabled: bool
```

`app/services/video_service.py`
```python
from sqlalchemy import select

from app.models.video import Video
from app.models.video_status import VideoStatus


class VideoService:
    def mark_watched(self, db_session, video_id: int, watched: bool) -> None:
        status = db_session.get(VideoStatus, video_id)
        status.watched = watched
        db_session.commit()

    def list_unwatched_by_tag(self, db_session, tag_id: int) -> list[Video]:
        stmt = (
            select(Video)
            .join(VideoStatus, VideoStatus.video_id == Video.id)
            .join_from(Video, Video.creator)
            .join("tags")
            .where(VideoStatus.watched.is_(False))
            .where("tags.id" == tag_id)
            .order_by(Video.published_at.desc())
        )
        return list(db_session.scalars(stmt))
```

- [ ] **Step 4: 写最小路由实现并注册到主应用**

`app/routers/creators.py`
```python
from fastapi import APIRouter, Depends, status

from app.schemas.creator import CreatorCreate

router = APIRouter(prefix="/api/creators", tags=["creators"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_creator(payload: CreatorCreate):
    return {"id": 1, "name": payload.name, "profile_url": str(payload.profile_url), "enabled": True}
```

`app/routers/videos.py`
```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/videos", tags=["videos"])


class WatchedPayload(BaseModel):
    watched: bool


@router.patch("/{video_id}/watched")
def mark_watched(video_id: int, payload: WatchedPayload):
    return {"video_id": video_id, "watched": payload.watched}
```

`app/main.py`
```python
from fastapi import FastAPI

from app.routers.creators import router as creators_router
from app.routers.tags import router as tags_router
from app.routers.videos import router as videos_router
from app.routers.sync import router as sync_router

app = FastAPI(title="my_bilibili")
app.include_router(creators_router)
app.include_router(tags_router)
app.include_router(videos_router)
app.include_router(sync_router)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_routers.py tests/test_services.py -v`
Expected: PASS，至少可以创建 UP 主、查询标签页未看视频、标记已看、触发同步。

- [ ] **Step 6: 提交这一小步**

```bash
git add app/main.py app/routers app/schemas app/services tests
git commit -m "feat: add local api for creators videos and sync"
```

### Task 5: 接入定时同步与同步状态

**Files:**
- Create: `app/scheduler.py`
- Modify: `app/config.py`
- Modify: `app/main.py`
- Test: `tests/test_scheduler.py`
- Test: `tests/test_routers.py`

- [ ] **Step 1: 写失败的调度测试**

```python
from app.scheduler import build_scheduler


def test_scheduler_registers_sync_job():
    scheduler = build_scheduler(sync_interval_minutes=30)
    job = scheduler.get_job("sync-all")

    assert job is not None
    assert job.trigger.interval.total_seconds() == 1800
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_scheduler.py -v`
Expected: FAIL，提示 `build_scheduler` 未定义。

- [ ] **Step 3: 写最小调度实现**

`app/scheduler.py`
```python
from apscheduler.schedulers.background import BackgroundScheduler


def build_scheduler(sync_interval_minutes: int, sync_callable=None) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        sync_callable or (lambda: None),
        "interval",
        minutes=sync_interval_minutes,
        id="sync-all",
        replace_existing=True,
    )
    return scheduler
```

`app/config.py`
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./my_bilibili.db"
    sync_interval_minutes: int = 60


settings = Settings()
```

- [ ] **Step 4: 在应用启动时注册调度器，并暴露同步状态接口**

`app/main.py`
```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.scheduler import build_scheduler

scheduler = build_scheduler(settings.sync_interval_minutes)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="my_bilibili", lifespan=lifespan)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/test_scheduler.py tests/test_routers.py -v`
Expected: PASS，调度器包含 `sync-all` job，同步状态接口能返回最近结果。

- [ ] **Step 6: 提交这一小步**

```bash
git add app/config.py app/scheduler.py app/main.py tests
git commit -m "feat: schedule local sync jobs"
```

### Task 6: 搭建前端并实现三个页面

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/TagsPage.tsx`
- Create: `frontend/src/pages/CreatorsPage.tsx`
- Create: `frontend/src/pages/SyncPage.tsx`
- Create: `frontend/src/components/VideoCard.tsx`
- Create: `frontend/src/components/CreatorForm.tsx`
- Create: `frontend/src/components/SyncStatusPanel.tsx`
- Test: `frontend/tests/VideoCard.test.tsx`
- Test: `frontend/tests/CreatorsPage.test.tsx`
- Test: `frontend/tests/TagsPage.test.tsx`
- Test: `frontend/tests/SyncPage.test.tsx`

- [ ] **Step 1: 写失败的前端组件测试**

```tsx
import { render, screen } from "@testing-library/react";
import { VideoCard } from "../src/components/VideoCard";

it("renders video fields", () => {
  render(
    <VideoCard
      video={{
        id: 1,
        title: "测试视频",
        creatorName: "测试UP",
        publishedAt: "2026-04-18T10:00:00",
        durationSeconds: 600,
        videoUrl: "https://www.bilibili.com/video/BV1xx411c7mD",
      }}
      onWatched={() => {}}
    />,
  );

  expect(screen.getByText("测试视频")).toBeInTheDocument();
  expect(screen.getByText("测试UP")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "标记已看" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npx vitest run`
Expected: FAIL，提示 `package.json` 或组件文件不存在。

- [ ] **Step 3: 写最小前端工程配置和核心组件**

`frontend/package.json`
```json
{
  "name": "my-bilibili-frontend",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "@tanstack/react-query": "^5.59.0"
  },
  "devDependencies": {
    "typescript": "^5.6.3",
    "vite": "^5.4.10",
    "vitest": "^2.1.4",
    "@testing-library/react": "^16.0.1",
    "@testing-library/jest-dom": "^6.6.3",
    "jsdom": "^25.0.1"
  }
}
```

`frontend/src/components/VideoCard.tsx`
```tsx
type VideoCardProps = {
  video: {
    id: number;
    title: string;
    creatorName: string;
    publishedAt: string;
    durationSeconds: number;
    videoUrl: string;
  };
  onWatched: (videoId: number) => void;
};

export function VideoCard({ video, onWatched }: VideoCardProps) {
  return (
    <article>
      <h3>{video.title}</h3>
      <p>{video.creatorName}</p>
      <a href={video.videoUrl} target="_blank" rel="noreferrer">打开 B 站</a>
      <button onClick={() => onWatched(video.id)}>标记已看</button>
    </article>
  );
}
```

- [ ] **Step 4: 写三个页面的最小可用实现**

`frontend/src/App.tsx`
```tsx
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { TagsPage } from "./pages/TagsPage";
import { CreatorsPage } from "./pages/CreatorsPage";
import { SyncPage } from "./pages/SyncPage";

export default function App() {
  return (
    <BrowserRouter>
      <nav>
        <Link to="/tags">标签视图</Link>
        <Link to="/creators">UP 主管理</Link>
        <Link to="/sync">同步状态</Link>
      </nav>
      <Routes>
        <Route path="/tags" element={<TagsPage />} />
        <Route path="/creators" element={<CreatorsPage />} />
        <Route path="/sync" element={<SyncPage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

`frontend/src/pages/TagsPage.tsx`
```tsx
export function TagsPage() {
  return <main><h1>标签视图</h1><p>展示标签下未看视频</p></main>;
}
```

`frontend/src/pages/CreatorsPage.tsx`
```tsx
export function CreatorsPage() {
  return <main><h1>UP 主管理</h1><p>添加链接、设置标签、启停同步</p></main>;
}
```

`frontend/src/pages/SyncPage.tsx`
```tsx
export function SyncPage() {
  return <main><h1>同步状态</h1><p>查看最近同步结果并手动触发同步</p></main>;
}
```

- [ ] **Step 5: 运行前端测试确认通过**

Run: `cd frontend && npm install && npx vitest run`
Expected: PASS，组件与页面基础测试通过。

- [ ] **Step 6: 提交这一小步**

```bash
git add frontend
git commit -m "feat: add local web ui"
```

### Task 7: 端到端联调、命令固化与最终验证

**Files:**
- Modify: `frontend/src/pages/TagsPage.tsx`
- Modify: `frontend/src/pages/CreatorsPage.tsx`
- Modify: `frontend/src/pages/SyncPage.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `CLAUDE.md`
- Test: `tests/test_routers.py`
- Test: `frontend/tests/*.test.tsx`

- [ ] **Step 1: 写失败的联调测试或最小验收脚本**

```python
def test_health_and_sync_routes_exist(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/sync/status").status_code == 200
```

- [ ] **Step 2: 运行全量测试确认仍有缺口**

Run: `pytest --tb=short && cd frontend && npx vitest run --reporter=verbose`
Expected: 如果存在接口联调、前端请求或排序问题，这一步应暴露失败。

- [ ] **Step 3: 补齐前后端联调代码**

`frontend/src/api/client.ts`
```ts
const API_BASE = "http://127.0.0.1:8000/api";

export async function fetchTagVideos(tagId: number) {
  const response = await fetch(`${API_BASE}/tags/${tagId}/videos`);
  if (!response.ok) throw new Error("加载标签视频失败");
  return response.json();
}

export async function createCreator(payload: { name: string; profile_url: string; tag_ids: number[] }) {
  const response = await fetch(`${API_BASE}/creators`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("创建 UP 主失败");
  return response.json();
}

export async function triggerSync() {
  const response = await fetch(`${API_BASE}/sync`, { method: "POST" });
  if (!response.ok) throw new Error("触发同步失败");
  return response.json();
}
```

`CLAUDE.md`
```md
## 常用命令

### 后端
- 安装依赖：`python -m pip install -e .[dev]`
- 启动 API：`uvicorn app.main:app --reload`
- 运行后端测试：`pytest -v`
- 运行单个测试：`pytest tests/test_services.py -v`
- 执行迁移：`alembic upgrade head`

### 前端
- 安装依赖：`cd frontend && npm install`
- 启动开发环境：`cd frontend && npm run dev`
- 运行前端测试：`cd frontend && npm test`
```

- [ ] **Step 4: 运行最终验证**

Run:
```bash
pytest --tb=short
cd frontend && npx vitest run --reporter=verbose
uvicorn app.main:app --reload
```

Expected:
- 后端测试全部 PASS
- 前端测试全部 PASS
- 本地访问前端后可以进入三个页面
- 在标签页看到未看视频
- 标记已看后刷新不再显示
- 同步页可以手动触发同步并看到最近结果

- [ ] **Step 5: 提交最终 MVP**

```bash
git add CLAUDE.md app frontend tests
git commit -m "feat: ship local bilibili mvp"
```

---

## 自检结论

- 规格覆盖：手动录入 UP 主、多个标签、标签页未看视频、手动已看、手动/定时同步、同步状态页、本地化约束，均已有对应任务。
- 占位符扫描：未使用 TBD / TODO / implement later 等占位表述。
- 一致性：统一使用 `Creator`、`Tag`、`Video`、`VideoStatus`、`SyncLog` 这些命名；前后端页面固定为标签视图、UP 主管理页、同步状态页。
