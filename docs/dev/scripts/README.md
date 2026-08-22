# scripts 目录说明

`scripts/` 负责前后端一键启停与数据备份，跨平台逻辑集中在 `manage.py`，`.sh` / `.bat` 只是转发入口。

## 文件清单

| 文件 | 平台 | 作用 |
| --- | --- | --- |
| `manage.py` | 全平台 | 启停核心：端口探测判断在跑、按端口查 PID 终止、轮替日志、停止时备份数据仓库 |
| `start.sh` / `start.bat` | POSIX / Windows | `manage.py start` 入口，双击可运行 |
| `stop.sh` / `stop.bat` | POSIX / Windows | `manage.py stop` 入口 |
| `restart.sh` / `restart.bat` | POSIX / Windows | `manage.py restart` 入口（= stop + start） |
| `ensure-uv.bat` | Windows only | 启停前确保 `uv` 可用，缺失则 `pip --user` 装并补进会话 PATH |

## manage.py

```
uv run python scripts/manage.py start     # 幂等启动：已在运行则只开浏览器
uv run python scripts/manage.py stop      # 停止服务 + 备份 ../private-data
uv run python scripts/manage.py restart   # stop + start
```

### 关键常量

- `PROJECT_ROOT`：脚本上一级，即项目根。
- `LOG_DIR = PROJECT_ROOT / "logs"`：`backend.log` / `frontend.log` / `launcher.log`。
- `BACKEND_HOST` / `BACKEND_PORT` / `FRONTEND_PORT`：取自 `app/config.settings`，值来自项目根 `config.json`（默认 `127.0.0.1` / `3333` / `2222`）。`frontend/vite.config.ts` 也读同一份，改端口只动一处。
- `PRIVATE_DATA_DIR = PROJECT_ROOT.parent / "private-data"`：数据仓库根，备份目标。
- `PRIVATE_DATA_REPO_SUBDIR = "bilibili-tag-group"`：备份时只 `git add` 该子目录下的 `*.json`。
- `IS_WINDOWS = os.name == "nt"`：分支用，决定进程探测/终止方式。
- `LOG_ROTATE_THRESHOLD = 10MB`：单份日志超阈值则在下次启动前轮替为 `<name>.1`，只留一份。

### 进程探测与终止（纯端口方案）

- `port_in_use(port)`：`socket.create_connection(("127.0.0.1", port), timeout=0.5)`，连得上 = 在跑。`cmd_start` 判断用。
- `find_pid_on_port(port)`：POSIX `lsof -ti :<port> -sTCP:LISTEN`；Windows 解析 `netstat -ano` 按 `:<port>` + `LISTENING` 取行末 PID（按字节匹配避开 `PYTHONUTF8=1` 编码问题）。工具缺失或端口未占返回 `None`。
- `_pid_alive(pid)`：`kill_process_tree` 内部轮询用。POSIX `os.kill(pid, 0)`；Windows `tasklist` CSV 按字节比对。
- `kill_process_tree(pid)`：POSIX `os.killpg(pid, SIGTERM)`（子进程 `start_new_session=True` 启动，PID 即 PGID），失败回退单进程；最多等 5 秒，超时 `SIGKILL` 强杀，最后 `waitpid` 收尸。Windows `taskkill /T /F /PID <pid>`。
- `stop_services_by_port(ports)`：循环 `find_pid_on_port` + `kill_process_tree`，kill 前打印"停止端口 X 上的进程 (PID Y)"。
- `wait_for_port(port, timeout)`：轮询端口就绪，后端 15s、前端 30s，就绪才开浏览器。

### 启动流程 `cmd_start`

1. `port_in_use` 探测前后端端口；都在跑就直接开浏览器。
2. 后端未跑：`.venv` 缺则 `uv sync --extra dev`；`uv run playwright install chromium`（走 npmmirror 镜像）；轮替 `backend.log`；`spawn_service` 后台拉起 `uv run uvicorn app.main:app --host <BACKEND_HOST> --port <BACKEND_PORT>`，stdout/stderr → `backend.log`，stdin = `DEVNULL`（setsid 后读 tty 会 EIO，vite 的 readline 会崩）；`wait_for_port` 等就绪。
3. 前端未跑：`node_modules` 缺则 `npm install`；轮替 `frontend.log`；`spawn_service` 拉起 `npm run dev`；`wait_for_port` 等就绪（vite 自身也读 `config.json` 的 `frontend_port`，两边一致）。
4. 前端就绪后开浏览器，打印 Backend / Frontend / Logs 地址。

### 停止流程 `cmd_stop`

1. `stop_services_by_port([BACKEND_PORT, FRONTEND_PORT])`：按端口查 PID 并终止。
2. `backup_data_repo(private_data_dir)`：
   - `../private-data/.git` 不存在则警告跳过。
   - `git pull --ff-only`（失败不阻断）。
   - `git add -- bilibili-tag-group/*.json`。
   - 无变更跳过；有变更 `commit` + `push`。
   - 任何一步失败只打 `[WARN]`，不影响停止结果。

### 日志轮替 `rotate_log_if_oversized`

单份日志超 10MB 改名为 `<name>.1`，旧的 `.1` 先删。只在启动前检查，进程内不滚动（子进程重定向，运行时无法轮替）。

### 控制台双写 `tee_console_to`

`sys.stdout` / `sys.stderr` 包成 `_Tee`，同时写一份到 `logs/launcher.log`，窗口关闭后仍可回查。每次运行覆盖重写，只留最近一次。只覆盖 `manage.py` 自身的 `print`；子进程直接继承控制台 fd，不经 `sys.stdout`，不会入档。

## 平台入口脚本

`.sh`：

```sh
cd "$(dirname "$0")/.."
exec uv run python scripts/manage.py <command>
```

切到项目根后转发，`exec` 替换进程避免多余 shell 层。

`.bat`：

- `cd /d "%~dp0.."` 切到项目根（`/d` 跨盘符）。
- `set PYTHONUTF8=1` 让 `manage.py` 输出 UTF-8。
- `call scripts\ensure-uv.bat`。
- `uv run python scripts\manage.py <command>`。
- 末尾 `pause` 保持窗口。

所有 `.bat` 保持纯 ASCII：cmd 用系统 ANSI 代码页（zh-CN 下是 GBK）解析批处理，`chcp 65001` 不能可靠修复非 ASCII 行，所以中文输出都在 `manage.py` 里。

## ensure-uv.bat

Windows 专用，启停前确保 `uv` 可用：

1. `where uv` 找到则退出。
2. 否则 `where python` → 回退 `where py`，都没有报错退出。
3. `<python> -m pip install --user uv`。
4. 把 pip 用户 Scripts 目录与 Python 自带 Scripts 目录追加到当前会话 PATH；用户目录那份通过 PowerShell 写注册表持久化（不用 `setx`，它在 1024 字符处截断会损坏 PATH）。
5. 再次 `where uv` 确认。

## 关键设计点

- **端口是唯一真相**：启动判断用 `port_in_use`，停止取 PID 用 `find_pid_on_port`。不写 PID 文件，避免 PID 复用误杀与残留文件。代价是 stop 时若端口被别的程序占会杀掉它——但端口是我们配的 3333/2222，被占概率极低，且 kill 前会打印 PID + 端口供用户确认。
- **进程组终止**：POSIX `start_new_session` 启动 + `killpg` 终止，保证 uvicorn / vite 派生的子进程（Playwright、esbuild 等）一并清理。
- **幂等启动**：服务已运行时只开浏览器，不重启、不重装依赖。
- **备份解耦**：停止完成就算备份失败也不回滚，本地提交即使 push 失败也保留。
- **跨平台分支集中在 manage.py**：`.sh` / `.bat` 只做最少的事，所有"如果 Windows 则…"的分支都在 Python 里。
