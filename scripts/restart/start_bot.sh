#!/bin/bash

# 兼容入口：统一交给项目进程管理器，不再直接创建 legacy 的 atri 会话。
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
MANAGER="$PROJECT_DIR/scripts/manage_processes.py"

if [ ! -x "$PYTHON" ]; then
    echo "错误：找不到项目虚拟环境解释器: $PYTHON" >&2
    exit 1
fi
if [ ! -f "$MANAGER" ]; then
    echo "错误：找不到进程管理器: $MANAGER" >&2
    exit 1
fi

exec "$PYTHON" "$MANAGER" start
