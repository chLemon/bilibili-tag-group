"""一键启停前后端服务，并在停止时备份数据仓库。

用法：
    uv run python manage.py start     # 幂等启动：已在运行则只打开浏览器
    uv run python manage.py stop      # 停止服务 + 备份 ../private-data
    uv run python manage.py restart   # = stop + start
"""
import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
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


def git_ok(args: list[str], cwd: Path) -> bool:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True).returncode == 0


def backup_data_repo(private_data: Path) -> bool:
    """提交并推送 private-data 仓库中的 JSON 变更。失败打印警告并返回 False。"""
    if not (private_data / ".git").exists():
        print(f"[WARN] {private_data} 不是 git 仓库，跳过备份")
        return False
    git_ok(["pull", "--ff-only"], private_data)  # 失败（如无 remote）不阻断
    subprocess.run(
        ["git", "add", "--", f"{PRIVATE_DATA_REPO_SUBDIR}/*.json"],
        cwd=private_data,
        capture_output=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=private_data,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        print("数据仓库无变更，跳过备份")
        return True
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not git_ok(
        ["commit", "-m", f"backup: bilibili-tag-group data snapshot ({timestamp})"],
        private_data,
    ):
        print("[WARN] 数据仓库 commit 失败")
        return False
    if not git_ok(["push"], private_data):
        print("[WARN] 数据仓库 push 失败（已本地提交）")
        return False
    print("数据仓库已提交并推送")
    return True


def spawn_service(command: list[str], log_file: Path, cwd: Path) -> subprocess.Popen:
    """后台启动服务，输出重定向到日志文件。

    POSIX 用 start_new_session 让子进程成为进程组组长（PID 即 PGID），
    Windows 走 cmd 包装，stop 时 taskkill /T 连同子进程一起杀。
    """
    if IS_WINDOWS:
        cmdline = subprocess.list2cmdline(command)
        return subprocess.Popen(
            f'{cmdline} >> "{log_file}" 2>&1',
            shell=True,
            cwd=cwd,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    log = open(log_file, "a", encoding="utf-8")
    return subprocess.Popen(
        command,
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        start_new_session=True,
    )


def cmd_start(paths: LauncherPaths = DEFAULT_PATHS) -> int:
    paths.log_dir.mkdir(exist_ok=True)
    pid_files = [paths.backend_pid_file, paths.frontend_pid_file]
    if services_running(pid_files):
        print("服务已在运行，直接打开浏览器...")
        webbrowser.open(FRONTEND_URL)
        return 0

    if shutil.which("node") is None:
        print("[ERROR] 未找到 node，请先安装 Node.js")
        return 1

    if not (paths.project_root / ".venv").exists():
        print("未找到 .venv，执行 uv sync --extra dev ...")
        if shutil.which("uv") is None:
            print("[ERROR] 未找到 uv，请先安装 uv")
            return 1
        rc = subprocess.run(
            ["uv", "sync", "--extra", "dev"], cwd=paths.project_root
        ).returncode
        if rc != 0:
            print("[ERROR] uv sync 失败")
            return 1

    result = subprocess.run(
        ["uv", "run", "playwright", "install", "chromium"],
        cwd=paths.project_root,
        capture_output=True,
    )
    if result.returncode != 0:
        print("[WARN] Playwright chromium 安装失败，resolve-name 可能不可用")

    if not (paths.frontend_dir / "node_modules").exists():
        print("未找到 node_modules，执行 npm install ...")
        if IS_WINDOWS:
            rc = subprocess.run(
                "npm install", cwd=paths.frontend_dir, shell=True
            ).returncode
        else:
            rc = subprocess.run(["npm", "install"], cwd=paths.frontend_dir).returncode
        if rc != 0:
            print("[ERROR] npm install 失败")
            return 1

    backend_log = paths.log_dir / "backend.log"
    frontend_log = paths.log_dir / "frontend.log"
    backend = spawn_service(
        [
            "uv", "run", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(BACKEND_PORT),
        ],
        backend_log,
        cwd=paths.project_root,
    )
    frontend = spawn_service(["npm", "run", "dev"], frontend_log, cwd=paths.frontend_dir)

    print(f"等待后端端口 {BACKEND_PORT} ...")
    if wait_for_port(BACKEND_PORT, 15):
        paths.backend_pid_file.write_text(str(backend.pid))
        print(f"后端就绪 (PID {backend.pid})")
    else:
        print(f"[WARN] 后端 15 秒内未就绪，见 {backend_log}")

    print(f"等待前端端口 {FRONTEND_PORT} ...")
    if wait_for_port(FRONTEND_PORT, 30):
        paths.frontend_pid_file.write_text(str(frontend.pid))
        print(f"前端就绪 (PID {frontend.pid})")
        print("打开浏览器...")
        webbrowser.open(FRONTEND_URL)
    else:
        print(f"[WARN] 前端 30 秒内未就绪，见 {frontend_log}")

    print()
    print(f"  Backend:  http://localhost:{BACKEND_PORT}")
    print(f"  Frontend: {FRONTEND_URL}")
    print(f"  Logs:     {paths.log_dir}")
    return 0


def cmd_stop(paths: LauncherPaths = DEFAULT_PATHS) -> int:
    if stop_services([paths.backend_pid_file, paths.frontend_pid_file]):
        print("服务已停止")
    else:
        print("未发现运行中的服务")
    backup_data_repo(paths.private_data_dir)
    return 0


def cmd_restart(paths: LauncherPaths = DEFAULT_PATHS) -> int:
    cmd_stop(paths)
    return cmd_start(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="manage.py", description="一键启停前后端服务")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start", help="幂等启动前后端（已运行则只打开浏览器）")
    sub.add_parser("stop", help="停止前后端并备份数据仓库")
    sub.add_parser("restart", help="先 stop 再 start")
    args = parser.parse_args(argv)
    handlers = {"start": cmd_start, "stop": cmd_stop, "restart": cmd_restart}
    return handlers[args.command]()


if __name__ == "__main__":
    sys.exit(main())
