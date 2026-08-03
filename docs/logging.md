# 日志文件说明

`logs/` 下各日志文件的内容、产生方式与滚动策略。按项目约定，`logs/*.log` 纳入 git（跨机器排查问题），`*.pid` 与轮替备份 `*.log.1` 不入库。

## 应用日志

### `app.log`

- **内容**：后端应用日志（`app.*` logger 的全部输出），格式 `时间 [级别] logger名: 消息`。
- **产生方式**：`app/logging_config.py` 的 `RotatingFileHandler`，由 FastAPI lifespan 调用 `setup_logging()` 挂上。
- **滚动策略**：单文件 10MB，保留 5 份（`app.log.1` ~ `app.log.5`），上限约 60MB。**不会膨胀。**

## 进程输出重定向

由 `scripts/manage.py` 的 `spawn_service` 把子进程 stdout/stderr 以 append 模式重定向到文件（manage.py start 启动时才有；手动 `uvicorn` / `npm run dev` 不产生）。

### `backend.log`

- **内容**：uvicorn 进程的全部输出——uvicorn 自身的启动/访问日志，外加应用日志（`setup_logging` 同时往 stderr 和 `app.log` 写，stderr 被重定向到这里）。**内容基本是 app.log 的超集**，排障时优先看它。
- **滚动策略**：进程内无法滚动，改为 **start 时一次性轮替**：`cmd_start` spawn 前检查，超过 10MB 则 rename 为 `backend.log.1`（只留一份）。注意只在重启服务时生效，单次长跑期间仍会持续增长。

### `frontend.log`

- **内容**：vite dev server 的全部输出（启动信息、编译错误等）。
- **滚动策略**：同 `backend.log`，start 时轮替，只留 `frontend.log.1`。vite 输出很少，实践中几乎不会触发。

## 其他文件

- `backend-stdout.log` / `backend-stderr.log` / `frontend-stdout.log` / `frontend-stderr.log` / `launcher.log` / `migration.log`：历史遗留的空文件，当前代码不再写入。
- `backend.pid` / `frontend.pid`：运行中服务的 PID，`stop` 据此清理进程。不入库。

## 为什么 backend.log 与 app.log 内容重复

`setup_logging` 挂了 stderr + 文件两个 handler，是为了兼顾两种启动方式：手动 `uvicorn --reload` 时看控制台，manage.py 启动时落 `app.log`。stderr 经重定向进入 `backend.log` 属副作用，代价是有界重复（已被滚动/轮替限制），收益是手动调试时控制台不会静默，故保留。
