#!/usr/bin/env bash
# App Hub 零编译桌面启动器（mac / Linux）
set -e
cd "$(dirname "$0")"
echo "[App Hub] 启动中（零编译桌面壳层）..."
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
"$PY" launch.py
