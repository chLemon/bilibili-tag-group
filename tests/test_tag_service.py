"""TagService 单元测试：未看视频聚合与按标签查询。"""

from datetime import datetime

from app.domains.creators.models import Creator, CreatorTag
from app.domains.tags.models import Tag
from app.domains.tags.service import TagService
from app.domains.videos.models import Video, VideoStatus


async def _seed(store):
    """两个标签、三个 UP 主（c1/c2 有标签，c3 无标签）、四条视频。

    视频状态：v1 未看、v2 已看、v3 未看、v4 未看。
    """
    t1 = await store.tags.add(Tag(name="科技"))
    t2 = await store.tags.add(Tag(name="生活"))
    c1 = await store.creators.add(
        Creator(
            name="c1",
            profile_url="https://space.bilibili.com/1",
            avatar_url="https://example.com/c1.png",
            video_count=0,
        )
    )
    c2 = await store.creators.add(
        Creator(
            name="c2",
            profile_url="https://space.bilibili.com/2",
            avatar_url="https://example.com/c2.png",
            video_count=0,
        )
    )
    c3 = await store.creators.add(
        Creator(
            name="c3",
            profile_url="https://space.bilibili.com/3",
            avatar_url="https://example.com/c3.png",
            video_count=0,
        )
    )
    await store.creator_tags.add(CreatorTag(creator_id=c1.id, tag_id=t1.id))
    await store.creator_tags.add(CreatorTag(creator_id=c2.id, tag_id=t1.id))
    await store.creator_tags.add(CreatorTag(creator_id=c2.id, tag_id=t2.id))

    async def add_video(creator_id: int, bvid: str, status: int) -> Video:
        v = await store.videos.add(
            Video(
                bvid=bvid,
                creator_id=creator_id,
                title=f"title-{bvid}",
                video_url=f"https://www.bilibili.com/video/{bvid}",
                published_at=datetime(2024, 1, 1),
                duration_seconds=60,
            )
        )
        await store.video_statuses.add(VideoStatus(video_id=v.id, status=status))
        return v

    v1 = await add_video(c1.id, "BV1", 0)
    await add_video(c1.id, "BV2", 1)
    v3 = await add_video(c2.id, "BV3", 0)
    v4 = await add_video(c3.id, "BV4", 0)
    return t1, t2, c1, c2, c3, v1, v3, v4


async def test_unwatched_count_by_tag(store):
    t1, t2, *_ = await _seed(store)
    counts = TagService().unwatched_count_by_tag(store)
    # t1 下有 c1(v1) + c2(v3) = 2 个未看；t2 下有 c2(v3) = 1 个未看
    assert counts == {t1.id: 2, t2.id: 1}


async def test_list_unwatched_videos_by_tag(store):
    t1, _, c1, c2, _, v1, v3, _ = await _seed(store)
    videos = TagService().list_unwatched_videos_by_tag(store, t1.id)
    assert {v.id for v in videos} == {v1.id, v3.id}
    by_id = {v.id: v for v in videos}
    assert by_id[v1.id].creator_name == c1.name
    assert by_id[v3.id].creator_name == c2.name


async def test_list_unwatched_videos_untagged(store):
    *_, v4 = await _seed(store)
    videos = TagService().list_unwatched_videos_untagged(store)
    assert [v.id for v in videos] == [v4.id]


async def test_list_unwatched_empty(store):
    assert TagService().list_unwatched_videos_untagged(store) == []
    assert TagService().unwatched_count_by_tag(store) == {}
