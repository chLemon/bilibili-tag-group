"""一键启停前后端服务，并在停止时备份数据仓库。

用法：
    uv run python scripts/manage.py start     # 幂等启动：已在运行则只打开浏览器
    uv run python scripts/manage.py stop      # 停止服务 + 备份 ../private-data
    uv run python scripts/manage.py restart   # = stop + start
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

# uv run python scripts/manage.py 时 Python 只把 scripts/ 加入 sys.path，
# 项目根不在内，无法 import app.*；这里手动补上
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings  # noqa: E402

LOG_DIR = PROJECT_ROOT / "logs"
BACKEND_HOST = settings.backend_host
BACKEND_PORT = settings.backend_port
FRONTEND_PORT = settings.frontend_port
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
PRIVATE_DATA_DIR = PROJECT_ROOT.parent / "private-data"
PRIVATE_DATA_REPO_SUBDIR = "bilibili-tag-group"

IS_WINDOWS = os.name == "nt"

# backend.log / frontend.log 是子进程输出重定向，进程内无法滚动；
# 每次 start 前检查一次，超限则轮替为 .1（只留一份备份）
LOG_ROTATE_THRESHOLD = 10 * 1024 * 1024


@dataclass(frozen=True)
class LauncherPaths:
    """启停涉及的全部路径，测试可注入临时目录。"""

    project_root: Path
    log_dir: Path
    frontend_dir: Path
    private_data_dir: Path


DEFAULT_PATHS = LauncherPaths(
    project_root=PROJECT_ROOT,
    log_dir=LOG_DIR,
    frontend_dir=FRONTEND_DIR,
    private_data_dir=PRIVATE_DATA_DIR,
)


def port_in_use(port: int) -> bool:
    """单次探测端口是否被占用（连得上 = 有服务在跑）。用于 start 时判断"已在运行"。"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def find_pid_on_port(port: int) -> int | None:
    """查占指定端口的 PID。POSIX 用 lsof，Windows 解析 netstat 输出。
    工具缺失或端口未被占用返回 None。"""
    if IS_WINDOWS:
        result = subprocess.run(
            ["netstat", "-ano"], capture_output=True,
        )
        # 按字节匹配，避免 PYTHONUTF8=1 下编码问题；找 LISTENING 行的 :<port>
        # 行形如 "  TCP    0.0.0.0:3333           0.0.0.0:0              LISTENING       12345"
        target = f":{port}".encode()
        listening = b"LISTENING"
        for line in result.stdout.splitlines():
            if target not in line or listening not in line:
                continue
            parts = line.split()
            if len(parts) >= 1:
                try:
                    return int(parts[-1])
                except ValueError:
                    continue
        return None
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
            capture_output=True,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    out = result.stdout.decode(errors="replace").strip()
    if not out:
        return None
    # 多行取第一个（多进程监听同端口极少见）
    first = out.splitlines()[0].strip()
    try:
        return int(first)
    except ValueError:
        return None


def _pid_alive(pid: int) -> bool:
    """判断进程是否存活。POSIX 用 kill(pid, 0)，Windows 查 tasklist。仅 kill_process_tree 内部用。"""
    if pid <= 0:
        return False
    if IS_WINDOWS:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
        )
        # CSV 每行形如 "name.exe","1234",...，比对第二列
        for line in result.stdout.splitlines():
            parts = line.split(b",")
            if len(parts) > 1 and parts[1] == f'"{pid}"'.encode():
                return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_for_port(port: int, timeout_seconds: float) -> bool:
    """轮询 TCP 端口直到可连接或超时，用于等服务真正就绪。"""
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
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    # 等 SIGTERM 起效，最多 5 秒；超时则 SIGKILL 强杀
    for _ in range(50):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    if _pid_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass


def stop_services_by_port(ports: list[int]) -> bool:
    """按端口查 PID 并终止；有进程被终止则返回 True。kill 前打印 PID + 端口供用户确认。"""
    stopped = False
    for port in ports:
        pid = find_pid_on_port(port)
        if pid is None:
            continue
        print(f"停止端口 {port} 上的进程 (PID {pid})")
        kill_process_tree(pid)
        stopped = True
    return stopped


def git_ok(args: list[str], cwd: Path) -> bool:
    """执行 git 子命令，返回是否成功（静默，不打印输出）。git 不存在或失败都返回 False。"""
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def pull_data_repo(private_data: Path) -> bool:
    """启动前拉取 private-data 远端更新，保证本地数据是最新的。
    不是 git 仓库或 pull 失败则返回 False，调用方应阻断启动。"""
    if not (private_data / ".git").exists():
        print(f"[ERROR] {private_data} 不是 git 仓库，无法拉取")
        return False
    if not git_ok(["pull", "--ff-only"], private_data):
        print(f"[ERROR] {private_data} 拉取失败（无 remote 或冲突？），已阻断启动")
        return False
    print("数据仓库已拉取最新")
    return True


def backup_data_repo(private_data: Path) -> bool:
    """提交并推送 private-data 仓库中的 JSON 变更。失败打印警告并返回 False。"""
    if not (private_data / ".git").exists():
        print(f"[WARN] {private_data} 不是 git 仓库，跳过备份")
        return False
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


def rotate_log_if_oversized(log_file: Path, threshold: int = LOG_ROTATE_THRESHOLD) -> bool:
    """日志超过阈值则轮替为 <name>.1（只留一份）。返回是否发生了轮替。"""
    try:
        if not log_file.exists() or log_file.stat().st_size <= threshold:
            return False
        backup = log_file.with_name(log_file.name + ".1")
        backup.unlink(missing_ok=True)
        log_file.rename(backup)
    except OSError as exc:
        print(f"[WARN] 日志轮替失败 {log_file}: {exc}")
        return False
    print(f"日志已轮替：{log_file} -> {log_file.name}.1")
    return True


class _Tee:
    """把写入原 stream 的内容同时写一份到文件。"""

    def __init__(self, stream, file):
        self._stream = stream
        self._file = file

    def write(self, s):
        self._stream.write(s)
        self._file.write(s)
        return len(s)

    def flush(self):
        self._stream.flush()
        self._file.flush()


def tee_console_to(log_file: Path, command: str) -> None:
    """控制台输出同时落一份到 launcher.log，窗口关闭后仍可回查启动/停止过程。

    每次运行覆盖重写（只留最近一次），防止无限膨胀。只覆盖 manage.py
    自身的 print；子进程（uv sync、npm install 等）直接继承控制台 fd，
    不经 sys.stdout，不会入档。
    """
    f = open(log_file, "w", encoding="utf-8")
    sys.stdout = _Tee(sys.stdout, f)
    sys.stderr = _Tee(sys.stderr, f)
    print(f"===== {datetime.now():%Y-%m-%d %H:%M:%S} manage.py {command} =====")


def spawn_service(command: list[str], log_file: Path, cwd: Path) -> subprocess.Popen:
    """后台启动服务，输出重定向到日志文件。

    POSIX 用 start_new_session 让子进程成为进程组组长（PID 即 PGID），
    Windows 走 cmd 包装，stop 时 taskkill /T 连同子进程一起杀。
    stdin 必须接 DEVNULL：setsid 后进程失去控制终端，继承的 tty 被读会
    EIO（vite 的 readline 因此崩溃）。
    """
    if IS_WINDOWS:
        cmdline = subprocess.list2cmdline(command)
        return subprocess.Popen(
            f'{cmdline} >> "{log_file}" 2>&1',
            shell=True,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    log = open(log_file, "a", encoding="utf-8")
    return subprocess.Popen(
        command,
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        cwd=cwd,
        start_new_session=True,
    )


def cmd_start(paths: LauncherPaths = DEFAULT_PATHS) -> int:
    """幂等启动：前后端都在跑就只开浏览器；缺哪个补某个（含依赖安装与日志轮替）。"""
    paths.log_dir.mkdir(exist_ok=True)
    if not pull_data_repo(paths.private_data_dir):
        return 1
    backend_running = port_in_use(BACKEND_PORT)
    frontend_running = port_in_use(FRONTEND_PORT)
    if backend_running and frontend_running:
        print("服务已在运行，直接打开浏览器...")
        webbrowser.open(FRONTEND_URL)
        return 0

    backend_log = paths.log_dir / "backend.log"
    frontend_log = paths.log_dir / "frontend.log"

    if not backend_running:
        if not (paths.project_root / ".venv").exists():
            print("未找到 .venv，执行 uv sync --extra dev ...")
            if shutil.which("uv") is None:
                print("[ERROR] 未找到 uv，请先安装 uv")
                return 1
            rc = subprocess.run(["uv", "sync", "--extra", "dev"], cwd=paths.project_root).returncode
            if rc != 0:
                print("[ERROR] uv sync 失败")
                return 1

        print("安装 Playwright chromium（首次约 150MB，走 npmmirror 镜像，请耐心等待）...")
        # 默认 CDN 在国内经常下不完，导致每次启动都重下；换 npmmirror 镜像
        env = {**os.environ, "PLAYWRIGHT_DOWNLOAD_HOST": "https://cdn.npmmirror.com/binaries/playwright"}
        result = subprocess.run(
            ["uv", "run", "playwright", "install", "chromium"],
            cwd=paths.project_root,
            env=env,
        )
        if result.returncode != 0:
            print("[WARN] Playwright chromium 安装失败，resolve-name 可能不可用")

        rotate_log_if_oversized(backend_log)
        spawn_service(
            [
                "uv",
                "run",
                "uvicorn",
                "app.main:app",
                "--host",
                BACKEND_HOST,
                "--port",
                str(BACKEND_PORT),
            ],
            backend_log,
            cwd=paths.project_root,
        )
        print(f"等待后端端口 {BACKEND_PORT} ...")
        if wait_for_port(BACKEND_PORT, 15):
            print("后端就绪")
        else:
            print(f"[WARN] 后端 15 秒内未就绪，见 {backend_log}")
    else:
        print("后端已在运行")

    if not frontend_running:
        if shutil.which("node") is None:
            print("[ERROR] 未找到 node，请先安装 Node.js")
            return 1
        if not (paths.frontend_dir / "node_modules").exists():
            print("未找到 node_modules，执行 npm install ...")
            if IS_WINDOWS:
                rc = subprocess.run("npm install", cwd=paths.frontend_dir, shell=True).returncode
            else:
                rc = subprocess.run(["npm", "install"], cwd=paths.frontend_dir).returncode
            if rc != 0:
                print("[ERROR] npm install 失败")
                return 1

        rotate_log_if_oversized(frontend_log)
        spawn_service(["npm", "run", "dev"], frontend_log, cwd=paths.frontend_dir)
        print(f"等待前端端口 {FRONTEND_PORT} ...")
        frontend_ready = wait_for_port(FRONTEND_PORT, 30)
        if frontend_ready:
            print("前端就绪")
        else:
            print(f"[WARN] 前端 30 秒内未就绪，见 {frontend_log}")
    else:
        print("前端已在运行")
        frontend_ready = True

    if frontend_ready:
        print("打开浏览器...")
        webbrowser.open(FRONTEND_URL)

    print()
    print(f"  Backend:  http://localhost:{BACKEND_PORT}")
    print(f"  Frontend: {FRONTEND_URL}")
    print(f"  Logs:     {paths.log_dir}")
    return 0


def cmd_stop(paths: LauncherPaths = DEFAULT_PATHS) -> int:
    """停止前后端，然后尝试备份数据仓库；备份失败只警告、不影响停止结果。"""
    if stop_services_by_port([BACKEND_PORT, FRONTEND_PORT]):
        print("服务已停止")
    else:
        print("未发现运行中的服务")
    backup_data_repo(paths.private_data_dir)
    return 0


def cmd_restart(paths: LauncherPaths = DEFAULT_PATHS) -> int:
    """先 stop（含备份）再 start。"""
    cmd_stop(paths)
    return cmd_start(paths)


def main(argv: list[str] | None = None) -> int:
    """解析 start/stop/restart 子命令并分发。argv 可注入以便测试。"""
    parser = argparse.ArgumentParser(prog="manage.py", description="一键启停前后端服务")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start", help="幂等启动前后端（已运行则只打开浏览器）")
    sub.add_parser("stop", help="停止前后端并备份数据仓库")
    sub.add_parser("restart", help="先 stop 再 start")
    args = parser.parse_args(argv)
    DEFAULT_PATHS.log_dir.mkdir(exist_ok=True)
    tee_console_to(DEFAULT_PATHS.log_dir / "launcher.log", args.command)
    handlers = {"start": cmd_start, "stop": cmd_stop, "restart": cmd_restart}
    return handlers[args.command]()


if __name__ == "__main__":
    sys.exit(main())
