# 一键启动器设计（manage.py）

日期：2026-07-25
状态：已确认

## 背景

现有 `start.bat` / `stop.bat` / `start.ps1` / `stop.ps1` 只支持 Windows，且内容与当前架构脱节：仍在检查 `my_bilibili.db`、跑 `alembic upgrade head`、用 `pip install -e ".[dev]"` 装依赖，而项目已迁移到 JSON 文件存储 + uv。此外逻辑只有 Windows 一份，macOS 无法使用。

## 目标

- 一键启动前端 + 后端并打开主页，macOS 与 Windows 行为一致
- 提供停止、重启、数据仓库备份操作
- 单一事实来源：逻辑只写一份，消除双脚本漂移

## 方案

根目录新增 `manage.py`，纯标准库实现（`subprocess`、`socket`、`signal`、`pathlib`、`webbrowser`、`os`），不新增依赖。平台差异（杀进程树）在脚本内部分支。

薄壳只保留一行转发：

- `start.bat` / `stop.bat` / `restart.bat`（Windows 双击）
- `start.sh` / `stop.sh`（macOS 终端）

原 `start.ps1` / `stop.ps1` 删除。

## 命令

```
uv run python manage.py start     # 幂等启动：已在运行则只打开浏览器
uv run python manage.py stop      # 停止服务 + 备份数据仓库
uv run python manage.py restart   # = stop + start
```

`start` 取幂等语义（用户已确认，不沿用原 `start.bat` 的先停后启）。

## start 流程

1. 检查 `logs/backend.pid` / `logs/frontend.pid`：进程还活着 → 打开浏览器退出；PID 文件失效（进程不存在或内容非法）→ 清理后继续
2. 检查 `node` 在 PATH；`.venv` 不存在则执行 `uv sync --extra dev`，存在则跳过（对齐原脚本语义）
3. `uv run playwright install chromium`（幂等，失败仅警告）
4. 后台启动 `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`，输出重定向到 `logs/backend.log`
5. 后台启动 `npm run dev`（cwd=`frontend/`），输出到 `logs/frontend.log`；`frontend/node_modules` 缺失则先 `npm install`
6. 等端口就绪：8000 等 15 秒，5173 等 30 秒；超时打印警告并指向对应日志文件
7. POSIX 下子进程用 `start_new_session=True` 起独立进程组，写入 PID 文件的就是真实 PID（不需要原脚本"查子进程"的 workaround）；Windows 下仍需从 `cmd.exe` 包装进程中找真实子进程 PID
8. `webbrowser.open("http://localhost:5173")`

## stop 流程与数据备份

1. 读 PID 文件 → 终止整棵进程树：POSIX `os.killpg(pid, SIGTERM)`，Windows `taskkill /T /F /PID <pid>`；进程不存在则只清理 PID 文件
2. 备份 `../private-data`：
   - `git -C ../private-data pull --ff-only`
   - `git add bilibili-tag-group/*.json`
   - 有变更则 `git commit -m "backup: bilibili-tag-group data snapshot (<YYYY-MM-DD HH:mm>)"` 并 `git push`
3. 备份失败时打印警告，但退出码仍为 0——备份失败不应阻止服务停止（与原脚本 `2>$null` 全吞不同，新脚本至少让人看到失败）

## 错误处理

- 依赖缺失（node / uv）：打印明确错误并以非零码退出
- 端口等待超时：警告 + 日志路径，不退出（服务可能仍在启动中）
- 备份失败：警告，退出码 0

## 测试

`tests/test_manage.py`，用临时目录模拟 PID 文件与 git 仓库：

- 幂等 start：已运行时只打开浏览器，不重复起进程
- 僵尸 PID 文件被清理
- stop 终止进程树并删除 PID 文件
- stop 后有 JSON 变更时产生备份 commit
- 备份失败（如非 git 仓库）不阻断 stop，退出码仍为 0

不真的启动 uvicorn / vite（属于手工联调范围）。

## 明确不做

- 不做 `install.ps1` / `start.ps1` 的 setup/start 拆分（保持对齐原一键体验）
- 不做日志查看、状态查询等额外子命令（YAGNI）
- 不自动执行项目仓库本身的 git 操作，只动 `../private-data`
