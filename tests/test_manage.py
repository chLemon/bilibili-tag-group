"""manage.py 一键启停脚本测试。"""
import os
import subprocess
import sys

import pytest

import manage


def spawn_dead_pid() -> int:
    """启动一个立即退出的进程，返回其（已死的）PID。"""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


@pytest.fixture
def paths(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return manage.LauncherPaths(
        project_root=tmp_path,
        log_dir=log_dir,
        backend_pid_file=log_dir / "backend.pid",
        frontend_pid_file=log_dir / "frontend.pid",
        frontend_dir=tmp_path / "frontend",
        private_data_dir=tmp_path / "private-data",
    )


def test_pid_is_running_with_current_process():
    assert manage.pid_is_running(os.getpid()) is True


def test_pid_is_running_with_dead_process():
    assert manage.pid_is_running(spawn_dead_pid()) is False


def test_read_live_pid_returns_pid_when_alive(tmp_path):
    pid_file = tmp_path / "a.pid"
    pid_file.write_text(str(os.getpid()))
    assert manage.read_live_pid(pid_file) == os.getpid()
    assert pid_file.exists()


def test_read_live_pid_cleans_stale_file(tmp_path):
    pid_file = tmp_path / "a.pid"
    pid_file.write_text(str(spawn_dead_pid()))
    assert manage.read_live_pid(pid_file) is None
    assert not pid_file.exists()


def test_read_live_pid_cleans_invalid_content(tmp_path):
    pid_file = tmp_path / "a.pid"
    pid_file.write_text("not-a-number")
    assert manage.read_live_pid(pid_file) is None
    assert not pid_file.exists()


def test_read_live_pid_missing_file(tmp_path):
    assert manage.read_live_pid(tmp_path / "a.pid") is None


def test_services_running_true_when_any_alive(tmp_path):
    alive = tmp_path / "a.pid"
    alive.write_text(str(os.getpid()))
    dead = tmp_path / "b.pid"
    dead.write_text(str(spawn_dead_pid()))
    assert manage.services_running([alive, dead]) is True
    # 死进程的 PID 文件被顺手清理
    assert not dead.exists()


def test_services_running_false_when_all_dead(tmp_path):
    dead = tmp_path / "b.pid"
    dead.write_text(str(spawn_dead_pid()))
    assert manage.services_running([dead, tmp_path / "missing.pid"]) is False
