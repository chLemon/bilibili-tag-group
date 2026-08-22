"""manage.py 一键启停脚本测试。"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import manage
import pytest


def spawn_dead_pid() -> int:
    """启动一个立即退出的进程，返回其（已死的）PID。"""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def paths(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return manage.LauncherPaths(
        project_root=tmp_path,
        log_dir=log_dir,
        frontend_dir=tmp_path / "frontend",
        private_data_dir=tmp_path / "private-data",
    )


# ── port_in_use ────────────────────────────────────────────────────────────


def test_port_in_use_true_when_listening():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        port = s.getsockname()[1]
        assert manage.port_in_use(port) is True


def test_port_in_use_false_when_free():
    assert manage.port_in_use(free_port()) is False


# ── find_pid_on_port ───────────────────────────────────────────────────────


def _listen_port() -> tuple[int, subprocess.Popen]:
    """起一个监听端口的子进程，返回 (port, proc)。"""
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-c", f"import socket, time; s=socket.socket(); s.bind(('127.0.0.1', {port})); s.listen(1); time.sleep(60)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # 等子进程真的开始监听
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if manage.port_in_use(port):
            return port, proc
        time.sleep(0.05)
    proc.kill()
    proc.wait()
    raise RuntimeError("子进程未在 3 秒内开始监听")


def test_find_pid_on_port_returns_pid_when_listening():
    port, proc = _listen_port()
    try:
        pid = manage.find_pid_on_port(port)
        assert pid == proc.pid
    finally:
        proc.kill()
        proc.wait()


def test_find_pid_on_port_returns_none_when_free():
    assert manage.find_pid_on_port(free_port()) is None


# ── _pid_alive（kill_process_tree 内部用）──────────────────────────────────


def test_pid_alive_with_current_process():
    assert manage._pid_alive(os.getpid()) is True


def test_pid_alive_with_dead_process():
    assert manage._pid_alive(spawn_dead_pid()) is False


# ── wait_for_port ──────────────────────────────────────────────────────────


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


# ── stop_services_by_port ──────────────────────────────────────────────────


def test_stop_services_by_port_kills_listening_process():
    port, proc = _listen_port()
    try:
        assert manage.stop_services_by_port([port]) is True
        for _ in range(50):
            if not manage._pid_alive(proc.pid):
                break
            time.sleep(0.1)
        assert not manage._pid_alive(proc.pid)
        assert not manage.port_in_use(port)
    finally:
        try:
            proc.kill()
            proc.wait()
        except Exception:
            pass


def test_stop_services_by_port_no_running_services():
    assert manage.stop_services_by_port([free_port()]) is False


# ── backup_data_repo ───────────────────────────────────────────────────────


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


# ── pull_data_repo ─────────────────────────────────────────────────────────


def test_pull_data_repo_not_a_repo_returns_false(tmp_path, capsys):
    """不是 git 仓库时返回 False 并打印 ERROR，调用方据此阻断。"""
    assert manage.pull_data_repo(tmp_path) is False
    out = capsys.readouterr().out
    assert "不是 git 仓库" in out
    assert "[ERROR]" in out


def test_pull_data_repo_pull_failure_returns_false(data_repo, monkeypatch, capsys):
    """git pull 失败时返回 False 并打印 ERROR。"""
    # 把 git 改名让 git_ok 调用失败
    monkeypatch.setenv("PATH", "/nonexistent")
    assert manage.pull_data_repo(data_repo) is False
    out = capsys.readouterr().out
    assert "拉取失败" in out
    assert "[ERROR]" in out


def test_pull_data_repo_success_returns_true(data_repo, capsys):
    """正常拉取返回 True。"""
    assert manage.pull_data_repo(data_repo) is True
    assert "数据仓库已拉取最新" in capsys.readouterr().out


# ── spawn_service ──────────────────────────────────────────────────────────


def test_spawn_service_detaches_stdin(paths, monkeypatch):
    """后台服务不得继承终端 stdin，否则 setsid 后读 tty 会 EIO 崩溃（vite 实测）。"""
    captured = {}

    class FakePopen:
        def __init__(self, command, **kwargs):
            captured.update(kwargs)
            self.pid = os.getpid()

    monkeypatch.setattr(manage.subprocess, "Popen", FakePopen)
    manage.spawn_service(["echo", "hi"], paths.log_dir / "x.log", cwd=paths.project_root)
    assert captured.get("stdin") == subprocess.DEVNULL


# ── cmd_start ──────────────────────────────────────────────────────────────


def test_cmd_start_idempotent_when_both_ports_in_use(paths, monkeypatch):
    """前后端端口都被占时，start 只打开浏览器，不起新进程。"""
    opened = []
    monkeypatch.setattr(manage.webbrowser, "open", opened.append)
    monkeypatch.setattr(manage, "port_in_use", lambda port: True)
    monkeypatch.setattr(manage, "pull_data_repo", lambda private_data: True)

    def forbidden(*args, **kwargs):
        raise AssertionError("不应启动新进程")

    monkeypatch.setattr(manage, "spawn_service", forbidden)
    assert manage.cmd_start(paths) == 0
    assert opened == [manage.FRONTEND_URL]


def test_cmd_start_blocks_when_pull_fails(paths, monkeypatch, capsys):
    """pull_data_repo 失败时，start 阻断并返回 1。"""
    monkeypatch.setattr(manage, "pull_data_repo", lambda private_data: False)

    def forbidden(*args, **kwargs):
        raise AssertionError("pull 失败不应启动新进程")

    monkeypatch.setattr(manage, "spawn_service", forbidden)
    assert manage.cmd_start(paths) == 1


def test_cmd_start_starts_only_dead_service(paths, monkeypatch):
    """后端端口被占、前端端口空闲时，只启动前端并打开浏览器，不重起后端。"""
    import types as types_mod

    (paths.frontend_dir / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(manage, "shutil", types_mod.SimpleNamespace(which=lambda name: "/usr/bin/node"))
    monkeypatch.setattr(manage, "wait_for_port", lambda port, timeout: True)

    def port_in_use(port: int) -> bool:
        return port == manage.BACKEND_PORT

    monkeypatch.setattr(manage, "port_in_use", port_in_use)
    monkeypatch.setattr(manage, "pull_data_repo", lambda private_data: True)

    opened = []
    monkeypatch.setattr(manage.webbrowser, "open", opened.append)
    spawned = []

    def fake_spawn(command, log_file, cwd):
        spawned.append(command)
        return types_mod.SimpleNamespace(pid=os.getpid())

    monkeypatch.setattr(manage, "spawn_service", fake_spawn)
    assert manage.cmd_start(paths) == 0
    assert spawned == [["npm", "run", "dev"]]
    assert opened == [manage.FRONTEND_URL]


# ── cmd_stop ───────────────────────────────────────────────────────────────


def test_cmd_stop_no_running_services_returns_zero(paths, monkeypatch, capsys):
    """无服务运行时，stop 打印未发现并返回 0；备份失败不影响退出码。"""
    monkeypatch.setattr(manage, "find_pid_on_port", lambda port: None)
    assert manage.cmd_stop(paths) == 0
    out = capsys.readouterr().out
    assert "未发现运行中的服务" in out
    assert "跳过备份" in out


def test_cmd_stop_kills_services_by_port(paths, monkeypatch, capsys):
    """stop 按端口查 PID 并终止。"""
    port, proc = _listen_port()
    try:
        # 让 find_pid_on_port 只对该端口返回 PID
        original = manage.find_pid_on_port

        def fake_find(port_):
            if port_ == port:
                return original(port)
            return None

        monkeypatch.setattr(manage, "find_pid_on_port", fake_find)
        # 改 BACKEND_PORT 让 cmd_stop 命中我们的测试端口
        monkeypatch.setattr(manage, "BACKEND_PORT", port)
        monkeypatch.setattr(manage, "FRONTEND_PORT", free_port())
        assert manage.cmd_stop(paths) == 0
        out = capsys.readouterr().out
        assert f"停止端口 {port}" in out
        for _ in range(50):
            if not manage._pid_alive(proc.pid):
                break
            time.sleep(0.1)
        assert not manage._pid_alive(proc.pid)
    finally:
        try:
            proc.kill()
            proc.wait()
        except Exception:
            pass


# ── cmd_restart ────────────────────────────────────────────────────────────


def test_cmd_restart_passes_paths_to_stop_and_start(paths, monkeypatch):
    """cmd_restart 必须把 paths 透传给 cmd_stop 与 cmd_start。"""
    received = []

    def fake_stop(p):
        received.append(("stop", p))
        return 0

    def fake_start(p):
        received.append(("start", p))
        return 0

    monkeypatch.setattr(manage, "cmd_stop", fake_stop)
    monkeypatch.setattr(manage, "cmd_start", fake_start)

    rc = manage.cmd_restart(paths)
    assert rc == 0
    assert received == [("stop", paths), ("start", paths)]


# ── kill_process_tree ──────────────────────────────────────────────────────


def test_kill_process_tree_sigkill_when_sigterm_ignored():
    """进程忽略 SIGTERM 时，kill_process_tree 应在 5 秒内 SIGKILL 强杀，不挂死。"""
    if manage.IS_WINDOWS:
        pytest.skip(reason="POSIX 信号语义")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)",
        ],
        start_new_session=True,
    )
    start = time.monotonic()
    try:
        manage.kill_process_tree(proc.pid)
        elapsed = time.monotonic() - start
        assert elapsed < 15
        for _ in range(50):
            if not manage._pid_alive(proc.pid):
                break
            time.sleep(0.1)
        assert not manage._pid_alive(proc.pid)
    finally:
        try:
            proc.kill()
            proc.wait()
        except Exception:
            pass


# ── rotate_log_if_oversized ────────────────────────────────────────────────


def test_rotate_log_if_oversized(tmp_path):
    log = tmp_path / "backend.log"
    log.write_text("x" * 100)
    assert manage.rotate_log_if_oversized(log, threshold=50) is True
    assert not log.exists()
    assert (tmp_path / "backend.log.1").stat().st_size == 100


def test_rotate_log_under_threshold_keeps_file(tmp_path):
    log = tmp_path / "backend.log"
    log.write_text("x" * 100)
    assert manage.rotate_log_if_oversized(log, threshold=200) is False
    assert log.exists()
    assert not (tmp_path / "backend.log.1").exists()


def test_rotate_log_replaces_old_backup(tmp_path):
    log = tmp_path / "backend.log"
    old_backup = tmp_path / "backend.log.1"
    old_backup.write_text("old")
    log.write_text("y" * 100)
    assert manage.rotate_log_if_oversized(log, threshold=50) is True
    assert old_backup.read_text() == "y" * 100


def test_rotate_log_missing_file_is_noop(tmp_path):
    assert manage.rotate_log_if_oversized(tmp_path / "nope.log") is False
