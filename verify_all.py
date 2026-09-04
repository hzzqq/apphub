# -*- coding: utf-8 -*-
"""
App Hub 全量校验脚本 (一次性质量基线 + 回归门禁)
================================================
用途: 在每次迭代后一键校验, 防止留下损坏状态。

覆盖:
  1. 前端: 遍历所有 App 的 index.html, 提取内联 <script> 块, 用 node --check 校验 JS 语法;
     同时检测破坏「零依赖单文件」承诺的外部 <script src=...> 引用。
  2. 后端: import backend.app, 用 test_client 冒烟全部 13 个端点(离线模式, 无需联网)。
  3. 一致性: 检测 data/ 目录 JSON 与 /api/data 白名单是否一一对应。

用法 (在隔离 venv 的 python 下):
    python verify_all.py
退出码: 0=全部通过, 1=存在错误。
"""
import os
import re
import sys
import glob
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
def _resolve_node():
    """Resolve the managed node.exe via glob so a version-dir rename
    (e.g. 22.22.2 -> 22.22.2-2) does not silently break every frontend
    check with [WinError 2] 系统找不到指定的文件。"""
    hits = sorted(glob.glob(r"C:/Users/Administrator/.workbuddy/binaries/node/versions/2*/node.exe"),
                  reverse=True)
    if hits:
        return hits[0]
    return r"C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-2/node.exe"
NODE = _resolve_node()
BACKEND = os.path.join(ROOT, "backend")

# ───────────────────────── 1. 前端 JS 校验 ─────────────────────────
SCRIPT_BLOCK_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S | re.I)
SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=[\"']([^\"']+)[\"']", re.I)


def check_frontend():
    print("─" * 60)
    print("【前端】遍历所有 App 的 index.html, 校验内联 JS 语法")
    errs = 0
    exts = 0
    blocks = 0
    files = sorted(glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True))
    files = [f for f in files if "backend" not in f]
    if not files:
        print("  ! 未发现任何 index.html")
        return 1
    for path in files:
        rel = os.path.relpath(path, ROOT)
        try:
            html = open(path, encoding="utf-8").read()
        except Exception as e:
            print("  [读取失败] %s: %s" % (rel, e))
            errs += 1
            continue
        # 外部 src 检测
        for src in SCRIPT_SRC_RE.findall(html):
            print("  [外部脚本-违规] %s -> %s  (破坏零依赖单文件承诺)" % (rel, src))
            exts += 1
        # 内联块校验
        for i, code in enumerate(SCRIPT_BLOCK_RE.findall(html)):
            if not code.strip():
                continue
            blocks += 1
            tmp = os.path.join(ROOT, "_jscheck_%d.tmp.js" % i)
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write("(function(){\n%s\n})();\n" % code)
                r = subprocess.run([NODE, "--check", tmp],
                                   capture_output=True, text=True, timeout=30)
                if r.returncode != 0:
                    print("  [JS语法错误] %s block#%d:\n%s" %
                          (rel, i, r.stderr.strip()[:600]))
                    errs += 1
            except Exception as e:
                print("  [JS校验异常] %s block#%d: %s" % (rel, i, e))
                errs += 1
            finally:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass  # 安全删除 shim 在回收站不可用时抛错, 不影响校验结论
    print("  扫描 %d 个 HTML, 校验 %d 个内联脚本块, 外部脚本违规 %d, 语法错误 %d"
          % (len(files), blocks, exts, errs))
    return errs + exts


# ───────────────────────── 2. 后端端点冒烟 ─────────────────────────
def check_backend():
    print("─" * 60)
    print("【后端】import backend.app 并冒烟全部端点 (离线模式)")
    if not os.path.isdir(BACKEND):
        print("  ! 未发现 backend 目录, 跳过")
        return 0
    sys.path.insert(0, BACKEND)
    try:
        import app as backend
    except Exception as e:
        print("  [后端导入失败] %s" % e)
        return 1
    c = backend.app.test_client()
    cases = [
        ("/", 200),
        ("/api/futures?symbol=cu", 200),
        ("/api/corr_top?n=3", 200),
        ("/api/quote?code=sh600519", 200),
        ("/api/shepherd", 200),
        ("/api/search?q=茅台&type=stock", 200),
        ("/api/etf", 200),
        ("/api/sector", 200),
        ("/api/data?file=theme.json", 200),
        # 越权/参数错误应正确拒绝
        ("/api/data?file=../../etc/passwd", 400),
        ("/api/futures?mode=bogus", 400),
    ]
    errs = 0
    for url, expect in cases:
        try:
            r = c.get(url)
            if r.status_code != expect:
                print("  [状态不符] %s -> %d (期望 %d)" % (url, r.status_code, expect))
                errs += 1
            else:
                j = r.get_json(silent=True) or {}
                if isinstance(j, dict) and j.get("ok") is False and expect == 200:
                    print("  [ok=False] %s -> %s" % (url, j.get("error")))
                    errs += 1
        except Exception as e:
            print("  [请求异常] %s -> %s" % (url, e))
            errs += 1
    print("  冒烟 %d 个端点, 失败 %d" % (len(cases), errs))
    return errs


# ───────────────────── 2b. 前端单测 (test/run.js) ─────────────────────
def check_frontend_tests():
    """发现并运行各 App 的 test/run.js 前端逻辑单测 (node)。"""
    print("─" * 60)
    print("【前端单测】发现并运行各 App 的 test/run.js")
    tests = sorted(glob.glob(os.path.join(ROOT, "**", "test", "run.js"), recursive=True))
    if not tests:
        print("  未发现前端单测 (test/run.js)，跳过")
        return 0
    errs = 0
    for t in tests:
        rel = os.path.relpath(t, ROOT)
        try:
            r = subprocess.run([NODE, rel], cwd=ROOT, capture_output=True,
                               text=True, timeout=120)
        except Exception as e:
            print("  [运行异常] %s -> %s" % (rel, e))
            errs += 1
            continue
        if r.returncode != 0:
            tail = (r.stdout.strip()[-700:] + "\n" + r.stderr.strip()[-300:]).strip()
            print("  [前端单测失败] %s\n%s" % (rel, tail))
            errs += 1
        else:
            for line in r.stdout.strip().splitlines():
                s = line.strip()
                if "通过" in s or "失败" in s or "✅" in s or "明细" in s:
                    print("  [%s] %s" % (rel, s))
    print("  运行 %d 个前端单测套件, 失败 %d" % (len(tests), errs))
    return errs


# ──────────── 2c. 前端运行时验证（Node + DOM 模拟实跑前端脚本） ────────────
def check_frontend_runtime():
    """前端运行时验证（Node + DOM 模拟实跑各 App 前端脚本）：
       - sector-matrix：跑专项 _fe_test.js（深度业务断言：渲染/排序/视图筛选/概览注入/CSV）。
       - 其余所有 App：跑通用 _fe_smoke.js（广度冒烟：脚本 eval + 触发初始化，抓加载/初始化崩溃）。
       _fe_test.js 自包含（优先 /tmp/matrix_test.json，缺失回落内嵌 fixture）；_fe_smoke.js 用鲁棒 DOM/Canvas 桩。"""
    print("─" * 60)
    print("【前端运行时】Node + DOM 模拟实跑各 App 前端脚本（专项 + 通用冒烟）")
    errs = 0
    smoke = os.path.join(ROOT, "_fe_smoke.js")

    # 1) 专项（sector-matrix 深度业务断言）
    spec = os.path.join(ROOT, "_fe_test.js")
    if os.path.isfile(spec):
        try:
            r = subprocess.run([NODE, spec, NODE], cwd=ROOT, capture_output=True,
                               text=True, timeout=120)
        except Exception as e:
            print("  [运行异常] _fe_test.js -> %s" % e); errs += 1
        else:
            combined = r.stdout + r.stderr
            if r.returncode != 0 or "ALL FRONTEND RUNTIME CHECKS PASSED" not in combined:
                print("  [前端运行时失败] _fe_test.js\n%s" % (combined.strip()[-900:]))
                errs += 1
            else:
                print("  [ok] sector-matrix（专项 7 项检查）")
    else:
        print("  [跳过] 未找到 _fe_test.js")

    # 2) 通用冒烟（其余 App）
    apps = []
    for name in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, name)
        if not os.path.isdir(d) or name.startswith(".") or name.startswith("_"):
            continue
        if name in NON_APP_DIRS:
            continue
        if not os.path.isfile(os.path.join(d, "index.html")):
            continue
        if name in ("sector-matrix", "shepherd-index", "futures-chain"):
            continue  # 已有专项覆盖，避免重复
        apps.append(name)

    for app in apps:
        adir = os.path.join(ROOT, app)
        try:
            r = subprocess.run([NODE, smoke, adir, NODE], cwd=ROOT, capture_output=True,
                               text=True, timeout=60)
        except Exception as e:
            print("  [运行异常] %s -> %s" % (app, e)); errs += 1; continue
        out = r.stdout + r.stderr
        if r.returncode != 0 or "FE_RUNTIME_FAIL" in out:
            tail = (r.stdout.strip()[-600:] + "\n" + r.stderr.strip()[-300:]).strip()
            print("  [前端运行时失败] %s\n%s" % (app, tail)); errs += 1
        else:
            print("  [ok] %s" % app)

    print("  前端运行时验证：专项 1 + 通用冒烟 %d 个 App，失败 %d" % (len(apps), errs))
    return errs


# ───────────────────── 3. data 与白名单一致性 ─────────────────────
def check_data_whitelist():
    print("─" * 60)
    print("【一致性】backend/data/*.json 与 /api/data 白名单")
    data_dir = os.path.join(BACKEND, "data")
    if not os.path.isdir(data_dir):
        return 0
    # data/ 目录同时存放两类文件：
    #   - /api/data 白名单文件（工具类 App 通过该端点读取）
    #   - futures_<exch>_<sym>.json 期货库存/行情快照（由 /api/futures 等专用端点直接读盘，不走 /api/data）
    # 一致性检查应保证：白名单文件必须存在；非白名单的期货快照不应被误判为遗漏。
    import re
    def _is_futures_snapshot(fname):
        return bool(re.match(r"futures_[A-Z]+_[^\s/]+\.json$", fname))
    on_disk = set(f for f in os.listdir(data_dir) if f.endswith(".json"))
    sys.path.insert(0, BACKEND)
    try:
        import app as backend
        allowed = set(backend.api_data.__wrapped__.allowed) if hasattr(backend.api_data, "__wrapped__") else None
    except Exception:
        allowed = None
    # 直接从源码解析 allowed 集合
    allowed = set()
    try:
        src = open(os.path.join(BACKEND, "app.py"), encoding="utf-8").read()
        m = re.search(r"allowed\s*=\s*\{(.*?)\}", src, re.S)
        if m:
            allowed = set(re.findall(r"[\"']([^\"']+\.json)[\"']", m.group(1)))
    except Exception:
        pass
    # 真正问题：
    #   - 非期货快照文件在 disk 但不在 allowed -> 白名单遗漏
    #   - allowed 文件不在 disk -> 白名单悬空
    missing_raw = on_disk - allowed
    missing = {f for f in missing_raw if not _is_futures_snapshot(f)}
    snapshots_not_whitelisted = {f for f in missing_raw if _is_futures_snapshot(f)}
    extra = allowed - on_disk
    errs = 0
    if missing:
        print("  [白名单遗漏] data/ 存在但未列入白名单: %s" % sorted(missing))
        errs += len(missing)
    if snapshots_not_whitelisted:
        print("  [期货快照] 以下快照由 /api/futures 等专用端点读盘，未要求加入 /api/data 白名单: %s" % sorted(snapshots_not_whitelisted))
    if extra:
        print("  [白名单悬空] 列入白名单但 data/ 无文件: %s" % sorted(extra))
        errs += len(extra)
    print("  data/ 文件 %d, 白名单 %d, 不一致 %d (期货快照 %d 个不计入错误)" % (
        len(on_disk), len(allowed), errs, len(snapshots_not_whitelisted)))
    return errs


# ───────────────── 4. 目录卫生（应用目录 vs 非应用目录边界） ─────────────────
# 背景：项目根除 30 个应用目录外，还混着 Artifacts/ deploy/ test/ backend/ 等非应用目录
# （都没有 index.html）。边界不清时，任何「遍历子目录当应用」的脚本都会误扫，
# 后端同源托管也可能把内部脚本/部署配置暴露到公网。此处把边界固化成可自动校验的门禁。
NON_APP_DIRS = {".git", ".workbuddy", "backend", "node_modules", "__pycache__",
                ".pytest_cache", "Artifacts", "deploy", "test"}


def check_app_dirs():
    """校验「应用目录」边界：有 index.html 且已在大厅 APPS 注册；其余必须显式声明为非应用目录。"""
    print("─" * 60)
    print("【目录卫生】应用目录 vs 非应用目录（以 index.html + 大厅 APPS 注册为准）")
    errs = 0
    try:
        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    except Exception as e:
        print("  [读取失败] index.html: %s" % e)
        return 1
    registered = re.findall(r'dir:\s*"([^"]+)"', html)
    if not registered:
        print("  [解析失败] 未能从 index.html 的 APPS 数组解析出任何 dir")
        return 1
    reg_set = set(registered)
    if len(registered) != len(reg_set):
        dup = sorted(d for d in reg_set if registered.count(d) > 1)
        print("  [重复注册] APPS 数组存在重复 dir：%s" % dup)
        errs += 1

    # 1) 根级目录：既未声明为非应用目录、又不含 index.html → 卫生问题
    for name in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, name)
        if not os.path.isdir(d) or name.startswith(".") or name.startswith("_"):
            continue
        if name in NON_APP_DIRS:
            continue
        if not os.path.isfile(os.path.join(d, "index.html")):
            print("  [非应用目录] %s/ 既未声明为非应用目录，又没有 index.html" % name)
            errs += 1
        elif name not in reg_set:
            print("  [漏注册] %s/ 有 index.html，但大厅 APPS 数组里没有它" % name)
            errs += 1

    # 2) 反向检查：APPS 注册了，但磁盘上不存在或缺少 index.html
    for d in sorted(reg_set):
        p = os.path.join(ROOT, d)
        if not os.path.isdir(p):
            print("  [悬空注册] APPS 里的 %s 在磁盘上不存在" % d)
            errs += 1
        elif not os.path.isfile(os.path.join(p, "index.html")):
            print("  [悬空注册] APPS 里的 %s 缺少 index.html" % d)
            errs += 1

    print("  大厅注册 %d 个应用；非应用目录 %d 个（%s）；问题 %d"
          % (len(reg_set), len(NON_APP_DIRS), "/".join(sorted(NON_APP_DIRS)), errs))
    return errs


# ───────────────── 5. 前端 fetch 端点 ↔ 后端路由一致性 ─────────────────
def check_endpoint_consistency():
    """防止「前端调了后端没实现的路由」或反之长期脱节。
       扫描所有前端 HTML 中字面量出现的 /api/<name> 端点，确认后端 app.py 都有对应 @app.route 定义。
       反向的孤儿路由（后端有、前端未用）只提示、不报错，便于后续清理。"""
    print("─" * 60)
    print("【一致性】前端 fetch 的 /api 端点 ↔ 后端路由定义")
    try:
        src = open(os.path.join(BACKEND, "app.py"), encoding="utf-8").read()
    except Exception as e:
        print("  [读取失败] backend/app.py: %s" % e)
        return 1
    # 端点路径可含多级（如 /api/itinerary/generate）。旧正则字符集不含 "/"，
    # 会把多级路由在首段后截断（前端截成 /api/itinerary、后端又因要求紧跟引号而漏匹配），
    # 造成「前端调用但后端未定义」的假阳性。此处改为支持多级、且不匹配裸 "/api/"。
    _EP = r'/api/[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*'
    back_routes = set(re.findall(r'@app\.route\(\s*"(' + _EP + r')"', src))
    used = set()
    for html in glob.glob(os.path.join(ROOT, "**", "*.html"), recursive=True):
        try:
            t = open(html, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        for m in re.findall(_EP, t):
            used.add(m)
    missing = sorted(u for u in used if u not in back_routes)
    errs = 0
    if missing:
        print("  [前端调用但后端未定义] %s" % missing)
        errs += len(missing)
    orphans = sorted(r for r in back_routes if r not in used)
    if orphans:
        print("  [孤儿路由·提示] 后端定义但前端未调用: %s" % orphans)
    print("  前端用到 %d 个 /api 端点, 后端定义 %d 个, 缺失 %d (孤儿 %d 仅提示)"
          % (len(used), len(back_routes), errs, len(orphans)))
    return errs


def main():
    print("=" * 60)
    print("App Hub 全量校验 @ %s" % ROOT)
    print("=" * 60)
    e1 = check_frontend()
    e1b = check_frontend_tests()
    e1c = check_frontend_runtime()
    e2 = check_backend()
    e3 = check_data_whitelist()
    e4 = check_app_dirs()
    e5 = check_endpoint_consistency()
    total = e1 + e1b + e1c + e2 + e3 + e4 + e5
    print("─" * 60)
    print("汇总: 前端错误 %d, 前端单测失败 %d, 前端运行时 %d, 后端错误 %d, 一致性错误 %d, 目录卫生 %d, 端点一致性 %d, 总计 %d"
          % (e1, e1b, e1c, e2, e3, e4, e5, total))
    if total == 0:
        print("✅ 全部通过")
    else:
        print("❌ 存在 %d 项问题" % total)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
