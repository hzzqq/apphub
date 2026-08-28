# 部署与分享指南 · App Hub

目标：**不打包压缩，只分享一个网址**。对方打开网址即进入微应用大厅，各 App 自动走同源后端获取实时数据，效果与你双击打开本地文件一致，甚至更好（不用手填后端地址、没有 CORS 报错）。

---

## 0. 原理（先看懂这个，后面都不绕）

本项目 = **纯前端单文件 HTML（26 个 App） + Flask 后端（真实数据）**。

- 前端本身只是静态文件，双击 `index.html` 就能开。
- 但「实时行情 / 期货库存 / 财报 / 搜索」这些数据**必须在服务器端用 Python（akshare）抓取**——浏览器受 CORS 限制，直连东方财富/上期所会失败。
- 所以「分享一个能拿实时数据的网站」= 把**前端 + 后端整体部署成一个同源站点**，让后端顺便托管前端。

本次改造已完成这一关键一步：
- 后端 `backend/app.py` 现在**顺带托管前端**，`/` 就是大厅，`/futures-inventory/index.html` 等都能直接访问。
- 后端绑定 `0.0.0.0` 并读取环境变量 `PORT`（云平台注入）。
- 大厅在 `http(s)` 下自动把接口地址设为 `location.origin`（同源），各 App 无需手填地址、无 CORS。
- 本地双击 `file://` 打开仍保留「填 `http://127.0.0.1:8787`」的旧行为，两条路都通。
- **后端内置自动刷新调度器**：启动即开一个后台线程，每 `REFRESH_HOURS`（默认 6 小时）自动用 akshare 重抓全部期货品种的库存并改写本地缓存。也就是说——**部署后网站里的数据会自己保持最新，访客什么都不用做**。

---

## 1. 同局域网直连（零成本，立刻能用）

适合：宿舍/办公室/演示，给别人看效果。

```bash
cd E:/project/app/backend
pip install -r requirements.txt
python app.py        # 已绑定 0.0.0.0:8787
```

让同一 WiFi 下的其他人打开 `http://<你的内网IP>:8787`（内网 IP 用 `ipconfig` 查，形如 `192.168.x.x`）。
> 注意：你的电脑要一直开着；对方才能访问。

---

## 2. 内网穿透（把本机暴露成公网网址，无需云服务器）

适合：临时分享、不想买服务器、想立刻给外地朋友一个链接。

```bash
# 以 ngrok 为例（需注册拿 token）
ngrok config add-authtoken <你的token>
ngrok http 8787
# 终端会给出一个 https://xxxx.ngrok-free.app 公网地址, 直接发给别人
```

同类工具：frp（自建）、花生壳、cpolar、Cloudflare Tunnel。

---

## 3. 部署到云服务器（真·公网站点，24h 在线）★ 推荐

> ⚠️ **数据延迟关键**：akshare 抓的是东方财富/上期所等**国内数据源**。请选**国内节点**的云（腾讯云轻量应用服务器 / CloudBase，地域选广州、上海、北京）。海外主机（Railway/Fly.io 美区）可能被数据源限流，届时后端会用本地缓存快照兜底，实时刷新会降级。

### 方式 A：Docker（最省心，任何支持容器的云都行）

```bash
# 在你本地或服务器构建并运行
docker build -t app-hub .
docker run -d --name app-hub -p 8787:8787 -e OFFLINE_MODE=False app-hub
# 浏览器打开 http://<服务器IP>:8787
```

### 方式 B：直接装 Python 运行（腾讯云轻量/CloudBase 云函数 Web 服务）

```bash
git clone <你的仓库> && cd app/backend
pip install -r requirements.txt
# 生产建议用 gunicorn 常驻:
pip install gunicorn
gunicorn -w 2 -b 0.0.0.0:8787 app:app
```

- 腾讯云轻量应用服务器：在安全组放行 `8787`（或改用 80/443）。
- CloudBase 云托管：构建命令 `pip install -r backend/requirements.txt`，启动命令 `python backend/app.py`，监听端口填 `8787`，并绑定自定义域名。

### 方式 C：Railway / Fly.io（海外，适合给国外朋友 demo）

- `Procfile` 已就位：`web: OFFLINE_MODE=False REFRESH_HOURS=6 python backend/app.py`。
- `railway.json` 已就位（含 `OFFLINE_MODE=False`、健康检查 `/api/health`、自动重启），连 GitHub 仓库点一下即部署。
- ⚠️ 海外节点抓国内数据源（东方财富/上期所）可能不稳定：自动刷新失败时回退到本地真实缓存（仍是真实历史数据，只是不是当天最新）。**要稳定实时，请用方式 A/B 的国内节点**。

### 方式 D：腾讯云 systemd 常驻（轻量/Lighthouse，最稳）

- `deploy/apphub.service` 已就位：开机自启 + 崩溃自动重启 + `OFFLINE_MODE=False` + 自动刷新。
- 用法见文件头注释；把项目放到 `/opt/apphub` 后 `systemctl enable --now apphub` 即可。

---

## 4. 数据如何「永远最新」（核心问题：凭一个网站能看到更新吗？）

**能。** 机制如下（抓取发生在服务器，不在访客浏览器）：

1. 部署后的网站 = 一个 7×24 运行的 Flask 后端 + 同源前端。
2. 后端用 akshare 去抓东方财富/上期所。**抓数据的是服务器，访客只管看**。
3. 缓存更新有两条路径，保证「永远最新」：
   - **自动（已内置）**：后端后台线程每 `REFRESH_HOURS`（默认 6h）自动重抓全部品种，缓存永远是新的。访客**零操作**。
   - **手动**：访客点 App 里的「刷新数据」按钮 → 触发 `/api/refresh` → 后端立刻重抓该品种。
4. 即使自动刷新失败（数据源限流 / 服务器 IP 被挡 / 海外节点），也**保留上一次的真实缓存**，绝不回退合成样本、绝不白屏。

| 场景 | 设置 | 效果 |
|---|---|---|
| 部署（推荐） | `OFFLINE_MODE=False` + 自动刷新开启 | 每 6h 自动更新真实库存/行情，访客打开即最新 |
| 无网 / 未装 akshare | `OFFLINE_MODE=True` | 用 `backend/data/` 本地快照与离线样本兜底，永不 500 |
| 已有缓存快照 | 任意 | `futures_SHFE_SP.json` 等本地真实数据优先返回 |

> 注意：`app.py` 里 `OFFLINE_MODE` 默认是 `True`（沙箱安全），但 `start.bat`/`start.sh`/`Procfile`/`Dockerfile` 都已显式设成 `False`，所以**正常部署后自动就是实时 + 自动刷新**。
> 纸浆 SP 库存快照已更新至 **2026-08-27（382,974 吨）**；部署后第 1 个刷新周期（≤6h）内会自动补到最新。

---

## 5. 部署后自检

- 打开 `http://<域名或IP>:8787/` → 应见微应用大厅。
- 打开「期库镜」→ 选「上期所 / 纸浆」，应显示含 8/27 的真实 K 线×库存。
- `http://<域名或IP>:8787/api/health` → 返回含 `"auto_refresh"` 字段：
  - `"offline":false` 表示后端在线且为实时模式；
  - `"auto_refresh":{"running":true,"last_run":"...","last_ok":N}` 表示自动刷新调度器已在跑、最近一次成功刷新了 N 个品种。

---

## 6. 安全提示

- 前端静态托管已屏蔽 `backend/`、` .git/`、`.workbuddy/`、构建脚本等敏感路径，但**后端代码与 `data/` 仍随镜像一起部署**，请勿在 `data/` 放密钥。
- 本站无鉴权，仅适合**非敏感的个人工具分享**；若要公网长期开放，建议加一层反向代理（Nginx + 密码/HTTPS）。
