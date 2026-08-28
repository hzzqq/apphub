#!/usr/bin/env bash
# ============================================================================
# AppHub 一键部署脚本 —— 面向 Oracle Cloud Always Free (Ubuntu 22.04 / ARM)
# 用法（在目标服务器上执行）:
#     sudo bash setup_server.sh
# 全程无需把任何账号/密码/私钥发给任何人，你本地 SSH 进服务器粘贴本脚本即可。
# ============================================================================
set -euo pipefail

REPO="https://github.com/hzzqq/apphub"
APP_DIR="/opt/apphub"
PORT=8787
CURRENT_USER="$(whoami)"

echo "[*] 1/7 安装系统依赖..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl ufw cron

echo "[*] 2/7 克隆代码（公开仓库，无需鉴权）..."
sudo rm -rf "$APP_DIR"
sudo git clone "$REPO" "$APP_DIR"
sudo chown -R "$CURRENT_USER:$CURRENT_USER" "$APP_DIR"

echo "[*] 3/7 建虚拟环境并安装 Python 依赖（含 akshare 实时抓取）..."
cd "$APP_DIR"
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "[*] 4/7 注册 systemd 服务（开机自启 + 崩溃重启 + 自动刷新数据）..."
sudo tee /etc/systemd/system/apphub.service >/dev/null <<EOF
[Unit]
Description=AppHub Flask Data Backend
After=network.target

[Service]
User=$CURRENT_USER
WorkingDirectory=$APP_DIR/backend
Environment=PORT=$PORT
Environment=OFFLINE_MODE=False
ExecStart=$APP_DIR/.venv/bin/python app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable apphub
sudo systemctl restart apphub

echo "[*] 5/7 放行防火墙端口 $PORT ..."
sudo ufw allow 22/tcp
sudo ufw allow ${PORT}/tcp
sudo ufw --force enable || true

# ★ 重要：Oracle 默认用"安全列表(Security List)"而非 ufw 真正放行，
#   必须到 Oracle 控制台 → 网络 → 安全列表 → 入站规则 添加 8787/TCP (0.0.0.0/0)。
#   ufw 放行后若仍连不上，99% 是控制台安全列表没开，去补一条即可。

echo "[*] 6/7 配置自 ping 保活（防 Oracle 回收长期闲置实例）..."
( crontab -l 2>/dev/null; echo "*/10 * * * * curl -s -o /dev/null http://127.0.0.1:${PORT}/api/health" ) | crontab -

echo "[*] 7/7 本地自检..."
sleep 4
curl -s "http://127.0.0.1:${PORT}/api/health" | head -c 400
echo
echo
echo "============================================================"
echo "[完成] 在浏览器打开:  http://<服务器公网IP>:${PORT}/"
echo "         期库镜纸浆真实数据已内置(8/27=382,974吨), 后端每6h自动刷新。"
echo "============================================================"
