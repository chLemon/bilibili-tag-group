#!/bin/sh
# 重启前后端 = stop + start（POSIX 入口）。逻辑见 scripts/manage.py。
cd "$(dirname "$0")/.."
exec uv run python scripts/manage.py restart
