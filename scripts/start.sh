#!/bin/sh
# 一键启动前后端（POSIX 入口）。实际逻辑在 scripts/manage.py，
# 这里只负责切到项目根目录再转发，保证在任何目录下执行都生效。
cd "$(dirname "$0")/.."
exec uv run python scripts/manage.py start
