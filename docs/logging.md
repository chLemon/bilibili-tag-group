# 日志文件说明

`logs/` 下各日志文件的内容与滚动策略。`logs/*.log` 纳入 git 用于跨机器排障，轮替备份 `*.log.1` 不入库。

## `launcher.log`

`manage.py` 自身的控制台输出（依赖安装、端口等待、备份结果等），`bat` / `sh` 入口都转发到 `manage.py`，输出统一落这里。

每次运行 `manage.py` 时覆盖重写，只保留最近一次。子进程（`uv sync`、`npm install` 等）直接写控制台，不经 `sys.stdout`，不入档。

## `backend.log`

uvicorn 进程的全部输出——uvicorn 启动/访问日志 + 应用日志（`app/logging_config.py` 把应用日志写到 stderr，被 `spawn_service` 重定向到这里）。排障看它即可。

`cmd_start` spawn 前一次性轮替：超过 10MB rename 为 `backend.log.1`（只留一份）。进程内不滚动，单次长跑期间持续增长。

## `frontend.log`

vite dev server 的全部输出（启动信息、编译错误等）。滚动策略同 `backend.log`，vite 输出少，实践中几乎不触发轮替。
