#!/bin/sh
cd "$(dirname "$0")/.."
exec uv run python scripts/manage.py restart
