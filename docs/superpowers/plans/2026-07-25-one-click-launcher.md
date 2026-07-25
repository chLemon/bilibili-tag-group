# 一键启动器（manage.py）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用单个跨平台 Python 脚本 `manage.py`（start/stop/restart）替换现有 Windows 专用且已过时的 bat/ps1 启停脚本。

**Architecture:** `manage.py` 仅用标准库实现全部逻辑（进程存活性检查、PID 文件、端口等待、进程树终止、git 备份）；`start.bat` / `stop.bat` / `restart.bat` / `start.sh` / `stop.sh` 只做一行转发。测试通过 `LauncherPaths` 数据类注入临时目录，不触碰真实服务与数据仓库。

**Tech Stack:** Python 3.12 标准库（argparse、subprocess、socket、signal、webbrowser、dataclasses）、pytest、uv。

## Global Constraints

- Python `>=3.12`，运行命令统一用 `uv run` 前缀
- 不新增第三方依赖，`manage.py` 只用标准库
- ruff：line-length 100，`select = ["E", "F", "I", "UP"]`
- 测试默认跳过 integration marker；新测试不标记 integration（不真的启动 uvicorn/vite）
- 文档、注释用中文；命令、配置键等技术标识保持原文
- 数据备份只操作 `../private-data` 仓库，不碰项目仓库本身
- 时间戳格式 `YYYY-MM-DD HH:mm`（本地时间，用于备份 commit message）

---

### Task 1: manage.py 骨架与进程存活性检查

**Files:**
- Create: `manage.py`
- Test: `tests/test_manage.py`

**Interfaces:**
- Produces（后续任务依赖这些签名）:
  - `manage.IS_WINDOWS: bool`
  - `manage.pid_is_running(pid: int) -> bool`
  - `manage.read_live_pid(pid_file: Path) -> int | None` — 无效/死进程会清理文件并返回 None
  - `manage.services_running(pid_files: list[Path]) -> bool`

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_manage.py`：

```python
"""manage.py 一键启停脚本测试。"""
import os
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_manage.py -v`
Expected: 收集阶段即失败，`ModuleNotFoundError: No module named 'manage'`

- [ ] **Step 3: 创建 manage.py 骨架**

创建 `manage.py`：

```python
"""一键启停前后端服务，并在停止时备份数据仓库。

用法：
    uv run python manage.py start     # 幂等启动：已在运行则只打开浏览器
    uv run python manage.py stop      # 停止服务 + 备份 ../private-data
    uv run python manage.py restart   # = stop + start
"""
import os
import subprocess
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
    return any(read_live_pid(f) is not None for f in pid_files)
```

注意 Windows 分支的匹配：`tasklist /FO CSV /NH` 输出形如 `"python.exe","1234","Console",...`，去空格后查 `"1234",`。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_manage.py -v`
Expected: 8 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add manage.py tests/test_manage.py
git commit -m "feat: manage.py 骨架与进程存活性检查"
```

---

### Task 2: 端口等待 wait_for_port

**Files:**
- Modify: `manage.py`
- Test: `tests/test_manage.py`

**Interfaces:**
- Produces: `manage.wait_for_port(port: int, timeout_seconds: float) -> bool`

- [ ] **Step 1: 追加失败的测试**

向 `tests/test_manage.py` 追加（文件顶部需新增 `import socket`）：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_manage.py -k wait_for_port -v`
Expected: FAIL，`AttributeError: module 'manage' has no attribute 'wait_for_port'`

- [ ] **Step 3: 实现 wait_for_port**

`manage.py` 顶部 import 增加 `import socket`、`import time`，文件末尾追加：

```python
def wait_for_port(port: int, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_manage.py -v`
Expected: 10 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add manage.py tests/test_manage.py
git commit -m "feat: manage.py 增加端口就绪等待"
```

---

### Task 3: 进程树终止与 stop_services

**Files:**
- Modify: `manage.py`
- Test: `tests/test_manage.py`

**Interfaces:**
- Produces:
  - `manage.kill_process_tree(pid: int) -> None`（POSIX `killpg`，失败回退 `kill`；Windows `taskkill /T /F`）
  - `manage.stop_services(pid_files: list[Path]) -> bool`（有进程被终止则 True）

- [ ] **Step 1: 追加失败的测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_manage.py -k stop_services -v`
Expected: FAIL，`AttributeError: module 'manage' has no attribute 'stop_services'`

- [ ] **Step 3: 实现**

`manage.py` 顶部 import 增加 `import signal`，文件末尾追加：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_manage.py -v`
Expected: 12 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add manage.py tests/test_manage.py
git commit -m "feat: manage.py 增加进程树终止与服务停止"
```

---

### Task 4: 数据仓库备份 backup_data_repo

**Files:**
- Modify: `manage.py`
- Test: `tests/test_manage.py`

**Interfaces:**
- Consumes: `manage.PRIVATE_DATA_REPO_SUBDIR`（值为 `"bilibili-tag-group"`）
- Produces: `manage.backup_data_repo(private_data: Path) -> bool` — 无变更返回 True；失败打印警告返回 False

- [ ] **Step 1: 追加失败的测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_manage.py -k backup -v`
Expected: FAIL，`AttributeError: module 'manage' has no attribute 'backup_data_repo'`

- [ ] **Step 3: 实现**

`manage.py` 顶部 import 增加 `from datetime import datetime`，文件末尾追加：

```python
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
```

说明：`git add -- "bilibili-tag-group/*.json"` 的通配由 git pathspec 处理（不依赖 shell），git 的 `*` 可跨目录分隔符匹配。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_manage.py -v`
Expected: 15 个测试全部 PASS

- [ ] **Step 5: Commit**

```bash
git add manage.py tests/test_manage.py
git commit -m "feat: manage.py 增加数据仓库 JSON 备份"
```

---

### Task 5: spawn_service 与 start/stop/restart 命令

**Files:**
- Modify: `manage.py`
- Test: `tests/test_manage.py`

**Interfaces:**
- Consumes: 前四个任务的全部产物
- Produces:
  - `manage.spawn_service(command: list[str], log_file: Path, cwd: Path) -> subprocess.Popen`
  - `manage.cmd_start(paths: LauncherPaths = DEFAULT_PATHS) -> int`
  - `manage.cmd_stop(paths: LauncherPaths = DEFAULT_PATHS) -> int`
  - `manage.cmd_restart(paths: LauncherPaths = DEFAULT_PATHS) -> int`
  - `manage.main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: 追加失败的测试**

```python
def test_cmd_start_idempotent_opens_browser_only(paths, monkeypatch):
    """已有服务在运行时，start 只打开浏览器，不起新进程。"""
    paths.backend_pid_file.write_text(str(os.getpid()))
    opened = []
    monkeypatch.setattr(manage.webbrowser, "open", opened.append)

    def forbidden(*args, **kwargs):
        raise AssertionError("不应启动新进程")

    monkeypatch.setattr(manage, "spawn_service", forbidden)
    assert manage.cmd_start(paths) == 0
    assert opened == [manage.FRONTEND_URL]


def test_cmd_stop_backup_failure_still_returns_zero(paths, capsys):
    """备份失败（private-data 不是 git 仓库）不影响 stop 的退出码。"""
    assert manage.cmd_stop(paths) == 0
    out = capsys.readouterr().out
    assert "未发现运行中的服务" in out
    assert "跳过备份" in out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_manage.py -k cmd_ -v`
Expected: FAIL，`AttributeError: module 'manage' has no attribute 'cmd_start'`

- [ ] **Step 3: 实现**

`manage.py` 顶部 import 增加：

```python
import argparse
import shutil
import sys
import webbrowser
```

文件末尾追加：

```python
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
```

同时更新 `manage.py` 顶部的 import 区块，最终完整 import 为（ruff 会检查排序）：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_manage.py -v`
Expected: 17 个测试全部 PASS

- [ ] **Step 5: 跑 lint 与全量后端测试**

Run: `uv run ruff check manage.py tests/test_manage.py && uv run pytest --tb=short`
Expected: ruff 无输出；全部测试 PASS

- [ ] **Step 6: Commit**

```bash
git add manage.py tests/test_manage.py
git commit -m "feat: manage.py 增加 start/stop/restart 命令"
```

---

### Task 6: 薄壳脚本、删除 ps1、文档更新

**Files:**
- Create: `start.sh`、`stop.sh`、`restart.bat`
- Modify: `start.bat`、`stop.bat`、`README.md`、`CLAUDE.md`
- Delete: `start.ps1`、`stop.ps1`

**Interfaces:**
- Consumes: `manage.main`（通过 `uv run python manage.py <cmd>` 调用）
- Produces: 无代码接口

- [ ] **Step 1: 重写 `start.bat`**

```bat
@echo off
cd /d "%~dp0"
uv run python manage.py start
```

- [ ] **Step 2: 重写 `stop.bat`**

```bat
@echo off
cd /d "%~dp0"
uv run python manage.py stop
pause
```

- [ ] **Step 3: 创建 `restart.bat`**

```bat
@echo off
cd /d "%~dp0"
uv run python manage.py restart
pause
```

- [ ] **Step 4: 创建 `start.sh` 与 `stop.sh`**

`start.sh`：

```bash
#!/bin/sh
cd "$(dirname "$0")"
exec uv run python manage.py start
```

`stop.sh`：

```bash
#!/bin/sh
cd "$(dirname "$0")"
exec uv run python manage.py stop
```

Run: `chmod +x start.sh stop.sh`

- [ ] **Step 5: 删除 ps1**

```bash
git rm start.ps1 stop.ps1
```

- [ ] **Step 6: 更新 README.md**

将第 43-45 行的「### Windows 一键启停」整节替换为：

```markdown
### 一键启停

```bash
uv run python manage.py start    # 幂等启动前后端并打开主页（已运行则只开浏览器）
uv run python manage.py stop     # 停止服务并提交、推送 ../private-data 数据仓库
uv run python manage.py restart  # 先 stop 再 start
```

Windows 可双击 `start.bat` / `stop.bat` / `restart.bat`，macOS 可用 `./start.sh` / `./stop.sh`（均为一行转发）。PID 写入 `logs/*.pid`。
```

目录结构一节（原第 151-152 行）替换为：

```
├── manage.py                  # 一键启停脚本（跨平台，纯标准库）
├── start.bat / stop.bat / restart.bat   # Windows 双击入口（转发到 manage.py）
├── start.sh / stop.sh         # macOS 入口（转发到 manage.py）
```

- [ ] **Step 7: 更新 CLAUDE.md**

在「## 常用命令」标题下、「## 后端」之前插入：

```markdown
## 一键启停

- 启动前后端并打开主页：`uv run python manage.py start`（幂等，已运行则只开浏览器）
- 停止并备份数据仓库：`uv run python manage.py stop`
- 重启：`uv run python manage.py restart`
```

- [ ] **Step 8: 手工冒烟（macOS）**

Run: `./start.sh`
Expected: 后端 8000、前端 5173 就绪，浏览器自动打开主页；`logs/backend.pid`、`logs/frontend.pid` 存在

再次 Run: `./start.sh`
Expected: 输出「服务已在运行，直接打开浏览器...」，不重复起进程

Run: `./stop.sh`
Expected: 服务停止，PID 文件删除；`../private-data` 无变更时输出「数据仓库无变更，跳过备份」

确认进程确实退出：`lsof -i :8000 -i :5173` 无输出

- [ ] **Step 9: Commit**

```bash
git add start.bat stop.bat restart.bat start.sh stop.sh README.md CLAUDE.md
git commit -m "feat: 跨平台一键启停薄壳脚本，移除过时 ps1"
```

---

## Self-Review

- **Spec 覆盖**：幂等 start（Task 5）、僵尸 PID 清理（Task 1）、依赖检查与 uv sync（Task 5 cmd_start）、playwright install（Task 5）、npm install（Task 5）、端口等待 15s/30s（Task 2 + Task 5 调用）、PID 写入（Task 5）、打开浏览器（Task 5）、进程树终止（Task 3）、备份 pull/add/commit/push（Task 4）、备份失败退出码 0（Task 5 cmd_stop + 测试）、薄壳与 ps1 删除（Task 6）、README/CLAUDE.md（Task 6）——全部覆盖。
- **占位符扫描**：无 TBD/TODO，所有代码步骤含完整代码。
- **类型一致性**：`LauncherPaths` 字段名在 Task 1 定义、Task 5 与全部测试一致；`read_live_pid` / `services_running` / `stop_services` / `backup_data_repo` / `spawn_service` 签名跨任务一致；测试引用 `manage.FRONTEND_URL`、`manage.PRIVATE_DATA_REPO_SUBDIR` 均在 Task 1 定义。
