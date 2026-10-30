#!/usr/bin/env bash
# 酒店前台录入系统 · macOS / Linux / Git Bash 一键启动
# 与 start.bat 共用同一份逻辑（start.py），这里只负责"找一个能用的 Python"。
set -euo pipefail

cd "$(dirname "$0")"

PY=""
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo "[错误] 没找到 python3。请先安装 Python 3.11+。" >&2
  exit 1
fi

echo "[启动] 使用解释器：$PY"
exec "$PY" start.py "$@"
