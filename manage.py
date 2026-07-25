"""一键启停前后端服务，并在停止时备份数据仓库。

用法：
    uv run python manage.py start     # 幂等启动：已在运行则只打开浏览器
    uv run python manage.py stop      # 停止服务 + 备份 ../private-data
    uv run python manage.py restart   # = stop + start
"""
import os
import signal
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
BACKEND_PID_FILE = LOG_DIR / "backend.pid"
FRONTEND_PID_FILE = LOG_DIR / "frontend.pid"
BACKEND_PORT = 8000
FRONTEND_PORT = 5173
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
PRIVATE_DATA_DIR = PROJECT_ROOT.parent / "private-data"
PRIVATE_DATA_REPO_SUBDIR = "bilibili-tag-group"

IS_WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class LauncherPaths:
    """启停涉及的全部路径，测试可注入临时目录。"""

    project_root: Path
    log_dir: Path
    backend_pid_file: Path
    frontend_pid_file: Path
    frontend_dir: Path
    private_data_dir: Path


DEFAULT_PATHS = LauncherPaths(
    project_root=PROJECT_ROOT,
    log_dir=LOG_DIR,
    backend_pid_file=BACKEND_PID_FILE,
    frontend_pid_file=FRONTEND_PID_FILE,
    frontend_dir=FRONTEND_DIR,
    private_data_dir=PRIVATE_DATA_DIR,
)


def pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WINDOWS:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
        )
        return f'"{pid},"' in result.stdout.replace(" ", "")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def read_live_pid(pid_file: Path) -> int | None:
    """读取 PID 文件；内容非法或进程已死则清理文件并返回 None。"""
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
    except ValueError:
        pid_file.unlink(missing_ok=True)
        return None
    if pid_is_running(pid):
        return pid
    pid_file.unlink(missing_ok=True)
    return None


def services_running(pid_files: list[Path]) -> bool:
    """任一 PID 文件指向存活进程即视为服务在运行；顺手清理失效文件。"""
    alive = False
    for f in pid_files:
        if read_live_pid(f) is not None:
            alive = True
    return alive


def wait_for_port(port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def kill_process_tree(pid: int) -> None:
    """终止整棵进程树。POSIX 杀进程组（失败回退单进程），Windows 用 taskkill。"""
    if IS_WINDOWS:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True
        )
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass


def stop_services(pid_files: list[Path]) -> bool:
    """按 PID 文件终止服务并清理文件；有进程被终止则返回 True。"""
    stopped = False
    for pid_file in pid_files:
        pid = read_live_pid(pid_file)
        if pid is None:
            continue
        kill_process_tree(pid)
        pid_file.unlink(missing_ok=True)
        stopped = True
    return stopped
