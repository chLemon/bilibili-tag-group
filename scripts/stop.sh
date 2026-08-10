#!/bin/sh
# 停止前后端并备份 ../private-data 数据仓库（POSIX 入口）。逻辑见 scripts/manage.py。
cd "$(dirname "$0")/.."
exec uv run python scripts/manage.py stop
