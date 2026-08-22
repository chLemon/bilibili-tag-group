# scripts 目录说明

项目根目录下的 `scripts/` 负责前后端服务的一键启停与数据备份，所有跨平台逻辑集中在 `manage.py`，`.sh` / `.bat` 只是转发入口。

## 文件清单

| 文件 | 平台 | 作用 |
| --- | --- | --- |
| `manage.py` | 全平台 | 启停核心逻辑：拉起前后端、写 PID、轮替日志、停止时备份数据仓库 |
| `start.sh` / `start.bat` | POSIX / Windows | `manage.py start` 的入口，双击即可运行 |
| `stop.sh` / `stop.bat` | POSIX / Windows | `manage.py stop` 的入口 |
| `restart.sh` / `restart.bat` | POSIX / Windows | `manage.py restart` 的入口（= stop + start） |
| `ensure-uv.bat` | Windows only | 启停前检测 `uv` 是否可用，缺失则通过 `pip --user` 装一份并补进当前会话 PATH |

## manage.py

启停的唯一真实实现，命令行用法：

```
uv run python scripts/manage.py start     # 幂等启动：已在运行则只开浏览器
uv run python scripts/manage.py stop      # 停止服务 + 备份 ../private-data
uv run python scripts/manage.py restart   # stop + start
```

### 关键常量与路径

- `PROJECT_ROOT`：脚本所在目录的上一级，即项目根。
- `LOG_DIR = PROJECT_ROOT / "logs"`：存放 `backend.pid` / `frontend.pid` / `backend.log` / `frontend.log` / `launcher.log`。
- `BACKEND_HOST` / `BACKEND_PORT` / `FRONTEND_PORT`：从 `app/config.settings` 读取（默认 `127.0.0.1` / `3333` / `2222`），值来自项目根 `config.json`。前端 vite 开发服务器与后端 uvicorn 各占一个端口，`frontend/vite.config.ts` 也读同一份 `config.json`，改端口只动一处。
- `PRIVATE_DATA_DIR = PROJECT_ROOT.parent / "private-data"`：数据仓库根，备份目标。
- `PRIVATE_DATA_REPO_SUBDIR = "bilibili-tag-group"`：本项目在数据仓库下的子目录，备份时只 `git add` 这个子目录下的 `*.json`。
- `IS_WINDOWS = os.name == "nt"`：分支用，决定进程探测/终止方式。
- `LOG_ROTATE_THRESHOLD = 10MB`：单份日志超过该阈值则在下次启动前轮替为 `<name>.1`，只留一份备份。

### 端口配置源

端口统一在项目根 `config.json` 里定义（`backend_host` / `backend_port` / `frontend_port` / `sync_interval_minutes`），入 git，前后端共享。三处读取：

- `app/config.py`：`_load_settings()` 读 `config.json` 覆盖默认值，文件缺失或非法用默认值兜底（3333/2222/60）；`settings` 暴露给 `scripts/manage.py` 与 `app/main.py`。
- `scripts/manage.py`：`from app.config import settings` 后赋给模块级常量 `BACKEND_HOST` / `BACKEND_PORT` / `FRONTEND_PORT`，启动 uvicorn 传 `--host` / `--port`，`wait_for_port` 等就绪，`webbrowser.open` 用 `FRONTEND_URL`。
- `frontend/vite.config.ts`：`JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "config.json")))` 直接读 JSON，`server.port` 用 `frontend_port`，`proxy."/api".target` 用 `backend_port`。

`LauncherPaths` 是一个 frozen dataclass，把启停涉及的所有路径打包，便于测试时注入临时目录；`DEFAULT_PATHS` 是生产用的默认实例。

### 进程探测与终止

- `pid_is_running(pid)`：
  - POSIX 用 `os.kill(pid, 0)` 探测，`ProcessLookupError` 视为已死，`PermissionError` 视为存活（进程不属于当前用户但仍在跑）。
  - Windows 调 `tasklist /FI "PID eq <pid>" /FO CSV /NH`，按字节比对 CSV 第二列（PID 字段），避开 `PYTHONUTF8=1` 下的编码问题。
- `read_live_pid(pid_file)`：读 PID 文件，内容非法或进程已死则清理文件并返回 `None`，避免残留 PID 文件误判。
- `kill_process_tree(pid)`：
  - POSIX 用 `os.killpg(pid, SIGTERM)`（子进程用 `start_new_session=True` 启动，PID 即 PGID），失败回退到单进程 `SIGTERM`；最多等 5 秒，超时 `SIGKILL` 强杀，最后 `waitpid` 收尸。
  - Windows 用 `taskkill /T /F /PID <pid>`，`/T` 连同子进程一起终止。
- `stop_services(pid_files)`：循环 `read_live_pid` + `kill_process_tree` + 清理 PID 文件，只要有进程被终止就返回 `True`。

### 端口就绪探测

`wait_for_port(port, timeout)` 轮询 `socket.create_connection(("127.0.0.1", port), timeout=1)`，每 0.5 秒一次直到超时。后端给 15 秒、前端给 30 秒（前端要等 vite 起来 + 首次 npm install 可能较慢）。探测成功才打开浏览器，避免打开太早看到 `ECONNREFUSED`。

### 启动流程 `cmd_start`

1. 确保 `logs/` 存在；读取前后端 PID 文件。
2. 如果两个 PID 都存活：直接 `webbrowser.open(FRONTEND_URL)`，不重启。
3. 后端缺失时：
   - `.venv` 不存在则先 `uv sync --extra dev`；`uv` 不在 PATH 直接报错退出。
   - 跑 `uv run playwright install chromium`，走 `PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright` 镜像（国内默认 CDN 经常下不完，会导致每次启动都重下）。
   - 超阈值则轮替 `backend.log`。
   - `spawn_service` 用 `start_new_session=True`（POSIX）或 `CREATE_NO_WINDOW` + `cmd` 包装（Windows）后台拉起 `uv run uvicorn app.main:app --host <BACKEND_HOST> --port <BACKEND_PORT>`，stdout/stderr 重定向到 `backend.log`，stdin 接 `DEVNULL`（setsid 后失去控制终端，继承的 tty 被读会 EIO，vite 的 readline 会因此崩溃）。
   - 写 PID 文件，`wait_for_port(BACKEND_PORT, 15)` 等就绪。
4. 前端缺失时：
   - `node` 不在 PATH 报错退出。
   - `node_modules` 缺失则 `npm install`（Windows 用 `shell=True` 走 cmd）。
   - 轮替 `frontend.log`，`spawn_service` 拉起 `npm run dev`，写 PID，`wait_for_port(FRONTEND_PORT, 30)` 等就绪（vite 自身也读 `config.json` 的 `frontend_port` 决定监听端口，两边一致）。
5. 前端就绪后打开浏览器，打印 Backend / Frontend / Logs 三个地址。

### 停止流程 `cmd_stop`

1. `stop_services([backend_pid_file, frontend_pid_file])` 终止前后端。
2. `backup_data_repo(private_data_dir)`：
   - `../private-data/.git` 不存在则警告并跳过（用户没把数据目录初始化成 git 仓库）。
   - `git pull --ff-only` 尝试拉远端（失败不阻断，比如没配 remote）。
   - `git add -- bilibili-tag-group/*.json` 只添加本项目的数据文件，不误伤同仓库下的其他项目。
   - `git status --porcelain` 判断有无变更；无变更直接返回，不造空提交。
   - 有变更则 `git commit -m "backup: bilibili-tag-group data snapshot (YYYY-MM-DD HH:MM)"`，再 `git push`。
   - 任何一步失败都只打 `[WARN]`，不影响停止结果——停止本身已经完成，备份是附加动作。

### 日志轮替 `rotate_log_if_oversized`

单份日志超 10MB 则改名为 `<name>.1`，旧的 `.1` 先删。只在启动前检查一次，进程内不滚动（`backend.log` / `frontend.log` 是子进程重定向，无法在运行时轮替）。

### 控制台双写 `tee_console_to`

把 `sys.stdout` / `sys.stderr` 包成 `_Tee`，同时写一份到 `logs/launcher.log`，窗口关闭后仍可回查启停过程。每次运行覆盖重写（只留最近一次），防止膨胀。只覆盖 `manage.py` 自身的 `print`；子进程（`uv sync`、`npm install` 等）直接继承控制台 fd，不经 `sys.stdout`，不会入档。

## 平台入口脚本

`start.sh` / `stop.sh` / `restart.sh`：

```sh
cd "$(dirname "$0")/.."
exec uv run python scripts/manage.py <command>
```

切到项目根目录后转发，保证在任何目录下执行都生效，`exec` 替换进程避免多余的 shell 层。

`start.bat` / `stop.bat` / `restart.bat`：

- `cd /d "%~dp0.."` 切到项目根（`/d` 跨盘符切换）。
- `set PYTHONUTF8=1` 让 `manage.py` 输出 UTF-8，与 macOS/Linux 一致。
- `call scripts\ensure-uv.bat` 确保 uv 可用。
- `uv run python scripts\manage.py <command>` 转发。
- 末尾 `pause` 保持窗口，方便双击用户读取输出。

所有 `.bat` 强制保持纯 ASCII：cmd 用系统 ANSI 代码页（zh-CN 下是 GBK）解析批处理，`chcp 65001` 不能可靠修复非 ASCII 行的解析，所以所有中文输出都放在 `manage.py` 里。

## ensure-uv.bat

Windows 专用，启停前确保 `uv` 可用：

1. `where uv` 找到则直接退出。
2. 找不到时优先 `where python`，回退到 `where py`（py launcher），都没有就报错退出。
3. `<python> -m pip install --user uv` 装到用户目录。
4. 把 pip 用户 Scripts 目录与 Python 自带 Scripts 目录都追加到当前会话 PATH；用户目录那一份通过 PowerShell 写注册表持久化到用户 PATH（不用 `setx`，因为它在 1024 字符处截断，会损坏已有 PATH）。
5. 再次 `where uv` 确认。

## 关键设计点

- **PID 文件是唯一真相**：启停判断服务是否在跑完全依赖 `logs/backend.pid` / `logs/frontend.pid`，不扫端口、不查进程名，避免误杀同名进程。
- **进程组终止**：POSIX 用 `start_new_session` 启动 + `killpg` 终止，保证 uvicorn / vite 派生的子进程（Playwright、esbuild 等）一并清理。
- **幂等启动**：服务已运行时只开浏览器，不重启、不重装依赖。
- **备份解耦**：停止已经完成就算备份失败也不回滚，数据本地提交即使 push 失败也保留。
- **跨平台分支集中在 manage.py**：`.sh` / `.bat` 只做最少的事，所有"如果 Windows 则…"的分支都在 Python 里，便于维护和测试。
