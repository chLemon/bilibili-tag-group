# 日志文件说明

`logs/` 下各日志文件的内容、产生方式与滚动策略。按项目约定，`logs/*.log` 纳入 git（跨机器排查问题），`*.pid` 与轮替备份 `*.log.1` 不入库。

## 启动器日志

### `launcher.log`

- **内容**：`manage.py` 自身的控制台输出（依赖安装进度、端口等待、备份结果等）。bat/sh 入口都只是转发到 manage.py，所以两端输出统一落在这里。
- **滚动策略**：每次运行 manage.py 时**覆盖重写**，只保留最近一次，不会膨胀。子进程（uv sync、npm install 等）直接写控制台，不入档。

## 进程输出重定向

由 `scripts/manage.py` 的 `spawn_service` 把子进程 stdout/stderr 以 append 模式重定向到文件（manage.py start 启动时才有；手动 `uvicorn` / `npm run dev` 不产生）。

### `backend.log`

- **内容**：uvicorn 进程的全部输出——uvicorn 自身的启动/访问日志，外加应用日志（`app/logging_config.py` 的 `setup_logging` 把应用日志写到 stderr，随之被重定向到这里）。**唯一的后端日志文件**，排障看它即可。
- **滚动策略**：进程内无法滚动，改为 **start 时一次性轮替**：`cmd_start` spawn 前检查，超过 10MB 则 rename 为 `backend.log.1`（只留一份）。注意只在重启服务时生效，单次长跑期间仍会持续增长。

### `frontend.log`

- **内容**：vite dev server 的全部输出（启动信息、编译错误等）。
- **滚动策略**：同 `backend.log`，start 时轮替，只留 `frontend.log.1`。vite 输出很少，实践中几乎不会触发。

## 其他文件

不再生成 PID 文件——`stop` 按端口查 PID（`lsof` / `netstat`），`logs/` 只保留日志文件。

## 为什么只有 backend.log 一个后端日志

历史上曾有 `app.log`（`RotatingFileHandler` 滚动落盘）与 `backend.log` 并存，内容重复。由于服务固定由 manage.py 启动（不手动跑 uvicorn），stderr 一定会被重定向到 backend.log，`setup_logging` 便只保留 stderr 输出，文件落盘统一交给 backend.log，避免双份日志。
