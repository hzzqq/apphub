# 分享打包脚本：把项目整理成「开箱即用」的分发包（不含开发/内部文件）。
# 产物：E:/project/app_dist/AppHub/ （解压后目录） + E:/project/app_dist/AppHub.zip
import os, shutil, zipfile

SRC = "E:/project/app"
DST = "E:/project/app_dist/AppHub"
OUT = "E:/project/app_dist/AppHub.zip"

# 排除的目录（任意层级）
EXCLUDE_DIRS = {".workbuddy", "__pycache__", ".pytest_cache", ".git", "node_modules", "Artifacts"}
# 排除的文件名（任意层）
EXCLUDE_FILES = {
    "backend.log", "verify_all.py", "xss_patch.py", "_bake6.py", "_enrich_inv.py",
    "少年开发者prompt卡片.md", ".DS_Store", "Thumbs.db", "package_for_share.py",
}
# 额外按相对路径精确排除
EXCLUDE_PATHS = {"backend/test_app.py", "backend/backend.log", "backend/.gitignore"}
EXCLUDE_SUFFIX = {".pyc", ".log"}

def rel(p):
    return os.path.relpath(p, SRC).replace("\\", "/")

def allowed(path):
    r = rel(path)
    parts = r.split("/")
    if any(seg in EXCLUDE_DIRS for seg in parts):
        return False
    base = os.path.basename(path)
    if base in EXCLUDE_FILES:
        return False
    if r in EXCLUDE_PATHS:
        return False
    if any(base.endswith(s) for s in EXCLUDE_SUFFIX):
        return False
    return True

# ---- 1) 构建分发目录 ----
if os.path.exists(DST):
    shutil.rmtree(DST)
os.makedirs(DST, exist_ok=True)

copied = 0
for root, dirs, files in os.walk(SRC):
    dirs[:] = [d for d in dirs if allowed(os.path.join(root, d))]
    for f in files:
        sp = os.path.join(root, f)
        if not allowed(sp):
            continue
        dp = os.path.join(DST, rel(sp))
        os.makedirs(os.path.dirname(dp), exist_ok=True)
        shutil.copy2(sp, dp)
        copied += 1

# ---- 2) 写一份傻瓜式运行说明 ----
guide = """App Hub 微应用大厅 · 运行说明
================================

这是一个「26 个零依赖单文件网页应用 + 真实数据后端」的打包。
解压后无需联网、无需复杂安装，双击即可在浏览器里使用全部功能。

────────────────────────────────
一、怎么跑（三步）
────────────────────────────────
【Windows】
  直接双击根目录里的  start.bat
  （首次会自动装 Flask，可能要等 10 秒左右）

【macOS / Linux】
  在终端里进入本目录，执行：  bash start.sh
  （或 Git Bash 里双击 start.sh）

启动后会：
  1. 自动开一个本地后端，地址 http://127.0.0.1:8787
  2. 自动打开浏览器进入「微应用大厅」
  关掉那个后端窗口 / 终端，即停止所有服务。

────────────────────────────────
二、关于数据（重要）
────────────────────────────────
✅ 不装 akshare（推荐大多数用户）：
   后端用「内置真实缓存数据 + 离线样本」运行。
   已附带 70 个品种的**真实历史数据**（含纸浆 SP 截至 2026-08-27
   的 382,974 吨真实库存、各品种 K 线等），离线也能看到真实图表。

✅ 装了 akshare（想看实时最新数据）：
   pip install akshare
   再运行 start.bat / start.sh，会自动进入「实时模式」：
   - 后端每 6 小时自动用 akshare 重抓全部品种并刷新缓存
   - 你也可以在 App 里点「刷新数据」按钮立刻更新
   - 即便某次抓取失败，也会保留上一次的真实缓存，不会白屏/造假

最小依赖其实只要：Python 3.10+ 和 Flask。
（start 脚本会在首次运行时自动帮你装 Flask + flask-cors）

────────────────────────────────
三、能玩什么
────────────────────────────────
大厅里 26 个应用，覆盖：
  · 金融：期库镜(期货库存×K线)、价格预警、牧羊人指数、黑天鹅、
         板块轮动、ETF 挑选、持仓体检、智能下单、K线形态、情绪温度、
         财报日历、个股笔记
  · 效率：桌面宠物、行程规划、健康自检、交易Agent、主题工坊、
         代码老师、习惯打卡、专注计时、菜谱盒、健身日志、
         书签管理、密码库、记账本
数据类应用点开即用；效率类应用数据存在你本地浏览器 localStorage。

────────────────────────────────
四、常见问题
────────────────────────────────
Q：打开后是空白/合成演示数据？
A：说明后端没起来。检查是否装了 Python 并加入 PATH；
   重新双击 start.bat，看后端窗口有无报错。

Q：想长期分享给朋友（给别人一个网址）？
A：本地双击是「自己用」。要变成「一个网址对方打开即用」，
   需要把「前端 + 后端」一起部署到一台服务器（见 DEPLOY.md）。
   本项目已支持同源部署，按 DEPLOY.md 走即可。

Q：端口 8787 被占用？
A：关掉占用该端口的程序，或改 backend/app.py 里的端口再跑。

祝你用得顺手 🛠️
"""
with open(os.path.join(DST, "运行说明.txt"), "w", encoding="utf-8") as f:
    f.write(guide)

# ---- 3) 压缩 ----
if os.path.exists(OUT):
    os.remove(OUT)
n = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
    for root, dirs, files in os.walk(DST):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.isfile(fp):
                continue
            arc = os.path.relpath(fp, os.path.dirname(DST)).replace("\\", "/")
            z.write(fp, arc)
            n += 1

print("COPIED_FILES", copied, "+ 运行说明.txt")
print("ZIPPED_FILES", n)
print("OUT", OUT, "SIZE_MB", round(os.path.getsize(OUT)/1024/1024, 2))
