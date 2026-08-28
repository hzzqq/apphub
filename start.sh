#!/usr/bin/env bash
# App 大厅 一键启动器 (Git Bash / Linux / macOS)
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  App 大厅 一键启动器"
echo "============================================================"

# 1) 选择 python 解释器
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python  >/dev/null 2>&1; then PY=python
else echo "[错误] 没找到 python，请先安装"; exit 1; fi
echo "[ok] 使用 $PY: $($PY --version 2>&1)"

# 2) 确保后端依赖
$PY -c "import flask" >/dev/null 2>&1 || $PY -m pip install Flask flask-cors

# 3) 启动 Flask 后端（后台常驻）
echo "[*] 启动后端 http://127.0.0.1:8787 ..."
nohup $PY backend/app.py >backend.log 2>&1 &
BACK_PID=$!
sleep 4

# 4) 抓取真实期货数据（有网才成功，失败不影响大厅）
if $PY -c "import akshare" >/dev/null 2>&1; then
  echo "[*] 抓取真实期货数据 (纸浆SP等) ..."
  $PY backend/fetch_real_futures.py || echo "[跳过] 抓取失败，期库镜将使用内置样本"
else
  echo "[提示] 未安装 akshare，跳过真实数据抓取 (可选: pip install akshare)"
fi

# 5) 打开 App 大厅
HALL="$(cd "$(dirname "$0")" && pwd)/index.html"
if command -v xdg-open >/dev/null 2>&1; then xdg-open "$HALL"
elif command -v open >/dev/null 2>&1; then open "$HALL"
else echo "[提示] 请手动打开: $HALL"; fi

echo
echo "============================================================"
echo "  启动完成！后端 PID=$BACK_PID (关闭该进程即停止所有 API)"
echo "============================================================"
echo "按回车退出启动器（后端继续在后台运行）..."
read
