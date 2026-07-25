"""manage.py 一键启停脚本测试。"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

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


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_wait_for_port_open():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        assert manage.wait_for_port(port, 2) is True


def test_wait_for_port_timeout():
    start = time.monotonic()
    assert manage.wait_for_port(free_port(), 0.3) is False
    assert time.monotonic() - start < 2


def test_stop_services_kills_process_and_removes_pid_file(paths):
    kwargs = {} if manage.IS_WINDOWS else {"start_new_session": True}
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"], **kwargs
    )
    paths.backend_pid_file.write_text(str(proc.pid))
    try:
        assert manage.stop_services(
            [paths.backend_pid_file, paths.frontend_pid_file]
        ) is True
        for _ in range(50):
            if not manage.pid_is_running(proc.pid):
                break
            time.sleep(0.1)
        assert not manage.pid_is_running(proc.pid)
        assert not paths.backend_pid_file.exists()
    finally:
        proc.kill()  # 兜底，防止测试失败遗留进程


def test_stop_services_no_running_services(paths):
    assert manage.stop_services(
        [paths.backend_pid_file, paths.frontend_pid_file]
    ) is False


GIT_ENV = {
    "GIT_AUTHOR_NAME": "test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def data_repo(tmp_path, monkeypatch):
    """带 bare remote 的 private-data 仓库，已有一次初始提交并配置好 upstream。"""
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)
    remote = tmp_path / "remote.git"
    run_git(["init", "--bare", str(remote)], tmp_path)
    repo = tmp_path / "private-data"
    subdir = repo / manage.PRIVATE_DATA_REPO_SUBDIR
    subdir.mkdir(parents=True)
    run_git(["init"], repo)
    run_git(["remote", "add", "origin", str(remote)], repo)
    (subdir / "creators.json").write_text("[]")
    run_git(["add", "."], repo)
    run_git(["commit", "-m", "init"], repo)
    run_git(["push", "-u", "origin", "HEAD"], repo)
    return repo


def test_backup_commits_and_pushes_json_changes(data_repo):
    json_file = data_repo / manage.PRIVATE_DATA_REPO_SUBDIR / "creators.json"
    json_file.write_text('[{"id": 1}]')
    assert manage.backup_data_repo(data_repo) is True
    log = run_git(["log", "--oneline"], data_repo).stdout.decode()
    assert "backup: bilibili-tag-group data snapshot" in log


def test_backup_no_changes_returns_true(data_repo):
    assert manage.backup_data_repo(data_repo) is True
    log = run_git(["log", "--oneline"], data_repo).stdout.decode()
    assert "backup:" not in log


def test_backup_not_a_repo_returns_false(tmp_path, capsys):
    assert manage.backup_data_repo(tmp_path) is False
    assert "跳过备份" in capsys.readouterr().out
