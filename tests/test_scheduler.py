"""调度器单元测试：验证 build_scheduler 的 job 注册行为与调度器状态查询。"""
from unittest.mock import MagicMock

import pytest

from app.scheduler import build_scheduler, get_sync_job_info


class TestBuildScheduler:
    """测试 build_scheduler 函数：只验证 job 注册，不启动调度器。"""

    def test_registers_sync_all_job(self):
        """build_scheduler 应注册 id='sync-all' 的 job。"""
        stub_callable = MagicMock()
        scheduler = build_scheduler(
            sync_interval_minutes=30, sync_callable=stub_callable
        )
        job = scheduler.get_job("sync-all")
        assert job is not None, "应存在 id='sync-all' 的 job"

    def test_interval_minutes_correct(self):
        """job 的 interval 应与传入的 sync_interval_minutes 一致。"""
        stub_callable = MagicMock()
        for minutes in [15, 30, 60, 120]:
            scheduler = build_scheduler(
                sync_interval_minutes=minutes, sync_callable=stub_callable
            )
            job = scheduler.get_job("sync-all")
            assert job is not None
            # APScheduler 3.x 的 IntervalTrigger 将 interval 存储在 trigger.interval 字段中
            interval_td = job.trigger.interval
            assert interval_td.total_seconds() == minutes * 60, (
                f"期望 {minutes} 分钟，实际 {interval_td.total_seconds()} 秒"
            )

    def test_sync_callable_is_used_as_job_func(self):
        """build_scheduler 应将 sync_callable 注册为 job 的执行函数。"""
        stub_callable = MagicMock()
        scheduler = build_scheduler(
            sync_interval_minutes=60, sync_callable=stub_callable
        )
        job = scheduler.get_job("sync-all")
        assert job is not None
        assert job.func is stub_callable

    def test_default_callable_is_noop_when_none(self):
        """sync_callable=None 时，build_scheduler 不应抛出异常，job 应注册成功。"""
        scheduler = build_scheduler(sync_interval_minutes=60, sync_callable=None)
        job = scheduler.get_job("sync-all")
        assert job is not None


class TestGetSyncJobInfo:
    """测试 get_sync_job_info：验证返回调度器状态字段。"""

    def test_returns_enabled_true_when_job_exists(self):
        """有 sync-all job 时，enabled 应为 True。"""
        stub_callable = MagicMock()
        scheduler = build_scheduler(
            sync_interval_minutes=60, sync_callable=stub_callable
        )
        info = get_sync_job_info(scheduler, sync_interval_minutes=60)
        assert info["enabled"] is True

    def test_returns_correct_interval_minutes(self):
        """interval_minutes 应与创建时传入的值一致。"""
        stub_callable = MagicMock()
        scheduler = build_scheduler(
            sync_interval_minutes=45, sync_callable=stub_callable
        )
        info = get_sync_job_info(scheduler, sync_interval_minutes=45)
        assert info["interval_minutes"] == 45

    def test_returns_job_id(self):
        """应返回 job_id 字段，值为 'sync-all'。"""
        stub_callable = MagicMock()
        scheduler = build_scheduler(
            sync_interval_minutes=60, sync_callable=stub_callable
        )
        info = get_sync_job_info(scheduler, sync_interval_minutes=60)
        assert info["job_id"] == "sync-all"

    def test_returns_enabled_false_when_no_job(self):
        """无 sync-all job 时（例如 callable=None 且实现选择不注册），enabled 可为 False。

        此测试验证 get_sync_job_info 在 scheduler 无 job 情况下的防御行为。
        这里通过 mock 一个没有 job 的 scheduler 来验证。
        """
        mock_scheduler = MagicMock()
        mock_scheduler.get_job.return_value = None
        info = get_sync_job_info(mock_scheduler, sync_interval_minutes=60)
        assert info["enabled"] is False
        assert info["job_id"] == "sync-all"
        assert info["interval_minutes"] == 60
