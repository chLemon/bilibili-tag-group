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
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
    paths.backend_pid_file.write_text(str(proc.pid))
    try:
        assert manage.stop_services([paths.backend_pid_file, paths.frontend_pid_file]) is True
        for _ in range(50):
            if not manage.pid_is_running(proc.pid):
                break
            time.sleep(0.1)
        assert not manage.pid_is_running(proc.pid)
        assert not paths.backend_pid_file.exists()
    finally:
        proc.kill()  # 兜底，防止测试失败遗留进程


def test_stop_services_no_running_services(paths):
    assert manage.stop_services([paths.backend_pid_file, paths.frontend_pid_file]) is False


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


def test_cmd_start_idempotent_opens_browser_only(paths, monkeypatch):
    """前后端都在运行时，start 只打开浏览器，不起新进程。"""
    paths.backend_pid_file.write_text(str(os.getpid()))
    paths.frontend_pid_file.write_text(str(os.getpid()))
    opened = []
    monkeypatch.setattr(manage.webbrowser, "open", opened.append)

    def forbidden(*args, **kwargs):
        raise AssertionError("不应启动新进程")

    monkeypatch.setattr(manage, "spawn_service", forbidden)
    assert manage.cmd_start(paths) == 0
    assert opened == [manage.FRONTEND_URL]


def test_cmd_start_starts_only_dead_service(paths, monkeypatch):
    """后端存活、前端已死时，只重启前端并打开浏览器，不重起后端。"""
    import types as types_mod

    paths.backend_pid_file.write_text(str(os.getpid()))
    paths.frontend_pid_file.write_text(str(spawn_dead_pid()))
    (paths.frontend_dir / "node_modules").mkdir(parents=True)
    monkeypatch.setattr(
        manage, "shutil", types_mod.SimpleNamespace(which=lambda name: "/usr/bin/node")
    )
    monkeypatch.setattr(manage, "wait_for_port", lambda port, timeout: True)
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


def test_cmd_stop_backup_failure_still_returns_zero(paths, capsys):
    """备份失败（private-data 不是 git 仓库）不影响 stop 的退出码。"""
    assert manage.cmd_stop(paths) == 0
    out = capsys.readouterr().out
    assert "未发现运行中的服务" in out
    assert "跳过备份" in out


def test_cmd_start_writes_pid_files_even_when_port_timeout(paths, monkeypatch):
    """端口超时也要写 PID 文件，否则 stop 无法清理孤儿进程。"""
    backend_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    frontend_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        import types as types_mod

        def fake_spawn(command, log_file, cwd):
            if "uvicorn" in command:
                return types_mod.SimpleNamespace(pid=backend_proc.pid)
            return types_mod.SimpleNamespace(pid=frontend_proc.pid)

        monkeypatch.setattr(manage, "spawn_service", fake_spawn)
        monkeypatch.setattr(manage, "wait_for_port", lambda port, timeout: False)
        (paths.project_root / ".venv").mkdir()
        (paths.frontend_dir / "node_modules").mkdir(parents=True)
        fake_shutil = types_mod.SimpleNamespace(which=lambda name: "/usr/bin/node")
        monkeypatch.setattr(manage, "shutil", fake_shutil)
        # 拦截 playwright install 的 subprocess.run（该路径下仅此一处 subprocess.run）
        real_run = manage.subprocess.run

        def fake_run(args, *rest, **kwargs):
            if args and "playwright" in " ".join(str(a) for a in args):
                return types_mod.SimpleNamespace(returncode=0)
            return real_run(args, *rest, **kwargs)

        monkeypatch.setattr(manage.subprocess, "run", fake_run)

        rc = manage.cmd_start(paths)
        assert rc == 0
        assert paths.backend_pid_file.read_text().strip() == str(backend_proc.pid)
        assert paths.frontend_pid_file.read_text().strip() == str(frontend_proc.pid)
    finally:
        for p in (backend_proc, frontend_proc):
            try:
                p.kill()
                p.wait()
            except Exception:
                pass


def test_kill_process_tree_sigkill_when_sigterm_ignored():
    """进程忽略 SIGTERM 时，kill_process_tree 应在 5 秒内 SIGKILL 强杀，不挂死。"""
    if manage.IS_WINDOWS:
        import pytest

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
            if not manage.pid_is_running(proc.pid):
                break
            time.sleep(0.1)
        assert not manage.pid_is_running(proc.pid)
    finally:
        try:
            proc.kill()
            proc.wait()
        except Exception:
            pass


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
