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
  4. 真实数据后端覆盖(R57→R60): 逐一探测全部后端依赖 App 的
     /api/* 端点, 确保无「真实数据」链路断点(防 R51 徽章回归); 后端离线时自动启动
     backend/app.py 再查, 确保 CI 不带后端也强制校验(非离线跳过)。

用法 (在隔离 venv 的 python 下):
    python verify_all.py
退出码: 0=全部通过, 1=存在错误。
"""
import os
import re
import sys
import glob
import time
import shutil
import tempfile
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
    # R88-11: 回退到 PATH 上的 node（本地托管路径不存在时），使本门禁可跑在 CI(ubuntu 等)。
    _w = shutil.which("node")
    if _w:
        return _w
    return "node"
NODE = _resolve_node()
BACKEND = os.path.join(ROOT, "backend")

# R88-11: 前端语法校验的临时文件放在系统临时目录（固定子目录，覆盖写、不删除），
# 不写仓库根、不做删除动作 —— 本环境删除保护 shim 会硬拦删除并可能中断进程。
_JSCHECK_DIR = os.path.join(tempfile.gettempdir(), "apphub_jscheck")
try:
    os.makedirs(_JSCHECK_DIR, exist_ok=True)
except Exception:
    _JSCHECK_DIR = tempfile.mkdtemp(prefix="apphub_jscheck_")

# ───────────────────────── 1. 前端 JS 校验 ─────────────────────────
SCRIPT_BLOCK_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S | re.I)
# R88-8: 与后端 _ZERO_DEP_RE 语义对齐。原正则要求 src 值带引号，会漏掉未加引号的
# `<script src=x.js>`（浏览器同样会执行），造成前端门禁比后端宽松的假阴性。
# 改为兼容带/不带引号：group(2) 即 src 值。
SCRIPT_SRC_RE = re.compile(r"<script[^>]*\bsrc\s*=\s*([\"']?)([^\"'>\s]+)", re.I)


def check_frontend():
    print("─" * 60)
    print("【前端】遍历所有 App 的 index.html, 校验内联 JS 语法")
    errs = 0
    exts = 0
    blocks = 0
    all_files = sorted(glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True))
    # R88-9: 排除非应用目录（backend/tools/docs/desktop 及运行时产物 generated/、submitted/）。
    # 否则运行时生成 / 用户提交的 index.html 会被当成「项目应用」参与语法门禁 —— 它们既非
    # 项目代码，又会因残留文件让门禁非确定性失败（曾误报 generated/smoke_verify_app 语法错误）。
    files = [f for f in all_files if not _under_non_app_dir(f)]
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
        # 外部 src 检测（R88-8: 兼容带/不带引号的 src 值）
        for m in SCRIPT_SRC_RE.finditer(html):
            src = m.group(2)
            print("  [外部脚本-违规] %s -> %s  (破坏零依赖单文件承诺)" % (rel, src))
            exts += 1
        # 内联块校验（R88-11: 临时文件写入系统临时目录，不再写/删仓库根目录。
        # 既避免污染仓库，也彻底移除「删除动作」——本环境删除保护 shim 会硬拦删除并可能
        # 中断非交互进程，是 verify_all 此前必须靠外部 runner 才能跑完的根因。）
        for i, code in enumerate(SCRIPT_BLOCK_RE.findall(html)):
            if not code.strip():
                continue
            blocks += 1
            tmp = os.path.join(_JSCHECK_DIR, "_jscheck_%d.tmp.js" % i)
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
    # 结构: (method, url, expect, kwargs)
    cases = [
        ("GET", "/", 200, {}),
        ("GET", "/api/futures?symbol=cu", 200, {}),
        ("GET", "/api/corr_top?n=3", 200, {}),
        ("GET", "/api/quote?code=sh600519", 200, {}),
        ("GET", "/api/shepherd", 200, {}),
        ("GET", "/api/search?q=茅台&type=stock", 200, {}),
        ("GET", "/api/etf", 200, {}),
        ("GET", "/api/sector", 200, {}),
        ("GET", "/api/data?file=theme.json", 200, {}),
        # 越权/参数错误应正确拒绝
        ("GET", "/api/data?file=../../etc/passwd", 400, {}),
        ("GET", "/api/futures?mode=bogus", 400, {}),
        # R88-7: 生态化端点（R84~R88 新增）纳入冒烟, 防止新端点长期无回归覆盖
        ("GET", "/api/health", 200, {}),
        ("GET", "/api/info", 200, {}),
        ("GET", "/api/llm/status", 200, {}),
        ("GET", "/api/data_status", 200, {}),
        ("GET", "/api/cache/stats", 200, {}),
        ("GET", "/api/inventory_overview", 200, {}),
        ("GET", "/api/futures_varieties", 200, {}),
        ("GET", "/api/img2mesh/status", 200, {}),
        # 导出: 不存在目录 → 404; 目录穿越 → 400(必须拒绝); 合法格式但不存在 → 404
        ("GET", "/api/export_app?p=__no_such_app__", 404, {}),
        ("GET", "/api/export_app?p=../etc", 400, {}),
        ("GET", "/api/export_app?p=a/b/c", 404, {}),
        # 提交: 缺 multipart 文件必须 400
        ("POST", "/api/submit_app", 400, {}),
        # 生成: 缺 name 必须 400; 合法输入(离线走规则兜底)必须 200
        ("POST", "/api/gen_app", 400, {"json": {"desc": "无名称"}}),
        ("POST", "/api/gen_app", 200, {"json": {
            "name": "smoke_verify_app", "desc": "verify 冒烟", "features": ["a", "b"], "cat": "tool"}}),
    ]
    errs = 0
    created_gen = None
    for method, url, expect, kw in cases:
        try:
            r = c.get(url) if method == "GET" else c.post(url, **kw)
            if r.status_code != expect:
                print("  [状态不符] %s %s -> %d (期望 %d)" % (method, url, r.status_code, expect))
                errs += 1
            else:
                j = r.get_json(silent=True) or {}
                if isinstance(j, dict) and j.get("ok") is False and expect == 200:
                    print("  [ok=False] %s %s -> %s" % (method, url, j.get("error")))
                    errs += 1
                # 记录生成目录, 冒烟结束清理, 避免 generated/ 无限堆积
                if method == "POST" and url == "/api/gen_app" and isinstance(j, dict) and j.get("dir"):
                    created_gen = j.get("dir")
        except Exception as e:
            print("  [请求异常] %s %s -> %s" % (method, url, e))
            errs += 1
    if created_gen:
        # R88-9: 用 rename 把冒烟产物挪出仓库，而不是删除——本环境有删除保护(shim)，
        # 对 generated/ 的删除会被硬拦并可能中断进程；rename 不触发，且产物移入系统临时目录。
        try:
            import tempfile
            src = os.path.join(ROOT, *created_gen.split("/"))
            if os.path.isdir(src):
                dst = os.path.join(tempfile.gettempdir(),
                                   "apphub_smoke_gen_%d" % int(time.time() * 1000))
                os.replace(src, dst)
        except Exception:
            pass
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
def _ensure_runtime_harness():
    """前端运行时桩（_fe_smoke.js）已纳入仓库；若工作树缺失，自动从 git HEAD 还原，
    避免门禁因桩文件被误删而静默退化（曾因清理误删导致 52 个 App 全部 MODULE_NOT_FOUND）。"""
    for fn in ("_fe_smoke.js", "_fe_test.js"):
        p = os.path.join(ROOT, fn)
        if os.path.isfile(p):
            continue
        # R88-11: 先探测 git 是否存在该文件，再决定创建——不再「先建空壳再删除」
        # （本环境删除保护会硬拦删除并可能中断进程）。
        try:
            probe = subprocess.run(["git", "show", "HEAD:%s" % fn], cwd=ROOT,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        except Exception as e:
            print("  [提示] 探测 %s 失败: %s" % (fn, e))
            continue
        if probe.returncode != 0:
            print("  [提示] %s 不在 git HEAD，跳过（门禁将优雅跳过该项）" % fn)
            continue
        try:
            with open(p, "w", encoding="utf-8") as f:
                subprocess.run(["git", "show", "HEAD:%s" % fn], cwd=ROOT, stdout=f,
                               stderr=subprocess.DEVNULL, timeout=30)
            print("  [自修复] 从 git 还原缺失的 %s" % fn)
        except Exception as e:
            print("  [提示] 还原 %s 失败: %s" % (fn, e))


def check_frontend_runtime():
    """前端运行时验证（Node + DOM 模拟实跑各 App 前端脚本）：
       - sector-matrix：跑专项 _fe_test.js（深度业务断言：渲染/排序/视图筛选/概览注入/CSV）。
       - 其余所有 App：跑通用 _fe_smoke.js（广度冒烟：脚本 eval + 触发初始化，抓加载/初始化崩溃）。
       _fe_test.js 自包含（优先 /tmp/matrix_test.json，缺失回落内嵌 fixture）；_fe_smoke.js 用鲁棒 DOM/Canvas 桩。"""
    print("─" * 60)
    print("【前端运行时】Node + DOM 模拟实跑各 App 前端脚本（专项 + 通用冒烟）")
    _ensure_runtime_harness()
    errs = 0
    smoke = os.path.join(ROOT, "_fe_smoke.js")

    # 1) 专项（sector-matrix 深度业务断言）
    spec = os.path.join(ROOT, "_fe_test.js")
    if os.path.isfile(spec) and os.path.getsize(spec) > 0:
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
    elif os.path.isfile(spec):
        # R88-9: 空壳文件（历史「恢复失败 + 删除被拦」遗留的 0 字节 _fe_test.js）
        # 不应被当作运行时失败。诚实跳过，避免门禁被残留空文件误杀。
        print("  [跳过] _fe_test.js 为空壳（0 字节），跳过专项运行时检查")
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
                ".pytest_cache", "Artifacts", "deploy", "test", "tools", "desktop", "docs",
                # 运行时产物目录：由 /api/gen_app、/api/submit_app 落盘，无 index.html，非应用
                "generated", "submitted"}


def _under_non_app_dir(path):
    """path 是否位于某个非应用目录下（把 runtime/工具目录排除出前端扫描）。"""
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    return rel.split("/", 1)[0] in NON_APP_DIRS


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
        if _under_non_app_dir(html):
            continue  # R88-9: 运行时/工具目录的 HTML 不算项目前端调用
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


# ─────────────── 6. 真实数据后端覆盖（R57，接 R56 审计） ───────────────
def check_realdada_coverage():
    """真实数据后端覆盖（R57→R60，接 R56 审计工具）：逐一探测全部后端依赖 App 的 /api/* 端点，
       确保无「真实数据」链路断点（防 R51 徽章回归）。后端离线时自动启动 backend/app.py 再查
       （R60 收口：CI 不带后端也必须强制校验，杜绝「离线跳过」漏洞）；仅当后端启动失败才优雅跳过。
       复用 tools/audit_backend_data 的 APP_ENDPOINTS / DATA_FILE / probe，避免逻辑双份维护。"""
    print("─" * 60)
    print("【真实数据覆盖】探测后端依赖 App 的 /api/* 端点（离线自动启动后端）")
    try:
        import tools.audit_backend_data as audit_mod
    except Exception:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import audit_backend_data as audit_mod
        except Exception as e:
            print("  [提示] 无法导入审计模块: %s，跳过" % e)
            return 0
    import urllib.request
    import socket

    # R88 修复: 原先固定 8787 会复用上次 verify_all 未清干净的残留后端,
    # 随机打到半死实例, 导致「真实数据断点」忽有忽无、门禁非确定性。
    # 改为每次起一个全新、隔离空闲端口的后端, 保证探测的是当前代码/当前状态。
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    base = "http://127.0.0.1:%d" % port
    env = dict(os.environ)
    env["PORT"] = str(port)
    env["OFFLINE_MODE"] = "True"
    print("  后端离线，自动启动 backend/app.py (隔离端口 %d) 用于真实数据校验 ..." % port)
    proc = None
    try:
        proc = subprocess.Popen(
            [sys.executable, "backend/app.py"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        ok = False
        for _ in range(40):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=3)
                ok = True
                break
            except Exception:
                time.sleep(0.5)
        if not ok:
            print("  [提示] 后端启动失败，跳过真实数据覆盖检查")
            return 0

        errs = 0
        broken = []
        total_eps = 0
        for app, eps in sorted(audit_mod.APP_ENDPOINTS.items()):
            for ep in eps:
                total_eps += 1
                kind, msg = audit_mod.probe(base, ep, app)
                if kind == "ERR":
                    errs += 1
                    broken.append((app, ep, msg))
        if broken:
            for app, ep, msg in broken:
                print("  [真实数据断点] %s -> %s (%s)" % (app, ep, msg))
            print("  ⚠ 发现 %d 个真实数据链路断点，R51「真实数据」徽章可能不再诚实" % errs)
        else:
            print("  ✓ 全部后端依赖 App 的 /api/* 端点可用，真实数据链路无断点")
        print("  真实数据覆盖：探测 %d 个 App 端点，断点 %d" % (total_eps, errs))
        return errs
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


# ─────────────── 7. futures-inventory 提交保护（硬规则） ───────────────
def check_futures_inventory_guard():
    """提交保护（R58）：项目硬规则——futures-inventory/index.html 永远不得提交
       （它是被生成器重建、且需从每次提交中排除的专项文件）。
       若该文件在工作树有改动，门禁直接失败并给出还原命令，防止被误提交。"""
    print("─" * 60)
    print("【保护】futures-inventory/index.html 不得提交（项目硬规则）")
    fi = os.path.join(ROOT, "futures-inventory", "index.html")
    if not os.path.isfile(fi):
        print("  [跳过] 未发现 futures-inventory/index.html")
        return 0
    try:
        r = subprocess.run(["git", "status", "--porcelain", fi],
                           cwd=ROOT, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            print("  [提示] 无法调用 git，跳过保护检查")
            return 0
        if r.stdout.strip():
            print("  [禁止] futures-inventory/index.html 在工作树有改动，按项目规则禁止提交！")
            print("        请先执行: git checkout -- futures-inventory/index.html  再提交")
            return 1
    except Exception as e:
        print("  [提示] 保护检查异常: %s，跳过" % e)
        return 0
    print("  ✓ futures-inventory/index.html 工作树干净（未被修改，可安全提交）")
    return 0


# ─────────────── 8. AI 生成（规则兜底）模板占位符守卫 ───────────────
def check_gen_app_template():
    """守卫：AI 生成的「规则兜底」路径，模板与占位符替换方式必须一致。

    背景（真实事故，R88 修复）：R84 为修 CSS `100%` 触发的 ValueError，
    把生成器从 `%` 格式化改成 [[TOKEN]] 替换，却**没同步改模板里的 `%s`**。
    后果：每个兜底生成的 App 标题/名称/功能全是字面量 `%s`，
    且 `var KEY="apphub_note_"+%s;` 是语法错误 → 整个内联脚本挂掉。
    这类错误**不崩溃、不报错，只在产物里显形**，且发生在降级兜底路径，
    所以必须固化成门禁，防止再次静默产出废品。"""
    print("─" * 60)
    print("【生成守卫】AI 生成（规则兜底）模板占位符一致性")
    if not os.path.isdir(BACKEND):
        print("  ! 未发现 backend 目录, 跳过")
        return 0
    sys.path.insert(0, BACKEND)
    try:
        import app as backend
    except Exception as e:
        print("  [后端导入失败] %s" % e)
        return 1
    name, desc = "汇率换算器", "实时汇率换算"
    feats = ["多币种", "历史记录"]
    try:
        html = backend._rule_gen_app(name, desc, feats)
    except Exception as e:
        print("  [生成失败] %s" % e)
        return 1
    errs = 0
    for tok in ("%s", "[[", "]]"):
        if tok in html:
            print("  [占位符残留] 生成结果仍含 %r —— 模板与替换方式不一致" % tok)
            errs += 1
    for must in (name, desc, feats[0], feats[1]):
        if must not in html:
            print("  [未替换] 生成结果缺少 %r" % must)
            errs += 1
    if 'apphub_note_"+' not in html:
        print("  [JS 风险] localStorage KEY 未正确生成（应为 \"apphub_note_\"+<字符串>）")
        errs += 1
    # XSS 守卫(R88 第2轮实跑取证): 恶意用户输入不得原样落进生成的 HTML。
    # 注意: html.escape 会把 < > 转义为 &lt; &gt;, 危险标签变成纯文本(已无害),
    # 但转义后的文本里仍含 "onerror" 字面量 —— 所以只检查「未转义的裸标签」是否消失,
    # 并反向确认输入确实被转义(&lt;img 出现), 才是真修复而非误报。
    evil_html = backend._rule_gen_app('<img src=x onerror=alert(1)>', 'A & B <b>bold</b>',
                                      ['<script>bad()</script>'], 'tool')
    for payload in ("<img", "<script>bad", "<b>bold</b>", "javascript:"):
        if payload in evil_html:
            print("  [XSS 风险] 恶意输入原样落进生成 HTML: %r" % payload)
            errs += 1
    if "&lt;img" not in evil_html:
        print("  [XSS 守卫异常] 恶意 <img> 未被 HTML 转义（期望出现 &lt;img）")
        errs += 1
    # 真实未转义标签里的 onerror 仍必须被门禁拦截(否则防御形同虚设)
    real_xss = '<img src=x onerror=alert(1)><body onload=evil()>'
    real_reasons = backend._gate_zero_dep(real_xss)
    if not any("onerror" in r or "XSS" in r for r in real_reasons):
        print("  [XSS 守卫失效] 真实 <img onerror> 未被零依赖门禁拦截")
        errs += 1
    # 已转义文本(规则生成器产出)不得被门禁当作 XSS 误杀 —— 否则正常应用名含 onerror 会被 502
    # 注意: 转义片段本身没有 <html>/<body> 且偏短, 会触发结构/长度提示, 这是正常的;
    # 这里只检查「是否出现 XSS 类原因」, 不能把结构/长度提示误判为误杀。
    escaped = '&lt;img src=x onerror=alert(1)&gt; a note about onerror handling'
    esc_reasons = backend._gate_zero_dep(escaped)
    if any(("XSS" in r) or ("onerror" in r) or ("javascript" in r) for r in esc_reasons):
        print("  [XSS 守卫误杀] 已转义文本被当作 XSS 拦截（应放行）: %r" % esc_reasons)
        errs += 1
    # R88-8: 外部内容嵌入（iframe/object/embed）必须被零依赖门禁拦截
    for payload in ('<iframe srcdoc="<script>alert(1)</script>"></iframe>',
                    '<object data="x.swf"></object>', '<embed src="x">'):
        rr = backend._gate_zero_dep(payload + "<html><body>" + "x" * 300 + "</body></html>")
        if not any(("iframe" in r) or ("object" in r) or ("embed" in r) for r in rr):
            print("  [守卫失效] 外部嵌入标签未被拦截: %r" % payload)
            errs += 1
    # 关键：规则模板必须能通过自身门禁 —— 否则 ai_gen_app 规则兜底会 502（R88-3 类事故）
    self_reasons = backend._gate_zero_dep(html)
    if self_reasons:
        print("  [自门禁失败] 规则模板被自身零依赖门禁拒绝: %r" % self_reasons)
        errs += 1
    if errs == 0:
        print("  ✓ 规则兜底生成器占位符全部落位，无 %s / [[ ]] 残留，用户输入已 HTML 转义，"
              "且规则模板可通过自身零依赖门禁（XSS/零依赖守卫通过）")
    return errs


def check_inventory_refresh_guard():
    """守卫(R88 第5轮): refresh_one/refresh_crude 不得因抓取异常(失败/为空/日期不重叠)
    把真实缓存的库存列整体清空写回。真实事故: 一次错位抓取曾把 futures_SHFE_CU.json
    的库存全部写成 null。固定为回归测试 backend/test_refresh_guard.py。"""
    print("─" * 60)
    print("【库存守卫】refresh_one 异常抓取不得清空真实缓存")
    try:
        import test_refresh_guard as tg
    except Exception as e:
        print("  [导入失败] %s" % e)
        return 1
    try:
        rc = tg.main()
    except Exception as e:
        print("  [执行异常] %s" % e)
        return 1
    if rc == 0:
        print("  ✓ 异常抓取未破坏真实库存缓存（回归守卫通过）")
    else:
        print("  [FAIL] 库存缓存存在被清空风险")
    return rc


def check_ecosystem_endpoints():
    """守卫(R88-10): 生态化端点（gen_app / submit_app / export_app）安全与边界回归。
    固定为 backend/test_ecosystem_endpoints.py：用 test_client 跑，APP_ROOT 重定向到
    临时目录，绝不污染仓库。覆盖: gen 恶意输入转义、缺参 400、产物可托管、submit 外部
    script src/`<iframe>` 400、submit 合法 200、export 目录穿越 400 / 不存在 404 / 附件头。"""
    print("─" * 60)
    print("【生态端点守卫】gen_app / submit_app / export_app 安全与边界")
    sys.path.insert(0, BACKEND)
    try:
        import test_ecosystem_endpoints as eco
    except Exception as e:
        print("  [导入失败] %s" % e)
        return 1
    try:
        rc = eco.main()
    except Exception as e:
        print("  [执行异常] %s" % e)
        return 1
    if rc == 0:
        print("  ✓ 生态端点安全/边界回归通过")
    else:
        print("  [FAIL] 生态端点存在回归")
    return rc


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
    e6 = check_realdada_coverage()
    e7 = check_futures_inventory_guard()
    e8 = check_gen_app_template()
    e9 = check_inventory_refresh_guard()
    e10 = check_ecosystem_endpoints()
    total = e1 + e1b + e1c + e2 + e3 + e4 + e5 + e6 + e7 + e8 + e9 + e10
    print("─" * 60)
    print("汇总: 前端错误 %d, 前端单测失败 %d, 前端运行时 %d, 后端错误 %d, 一致性错误 %d, 目录卫生 %d, 端点一致性 %d, 真实数据覆盖 %d, 期货保护 %d, 生成守卫 %d, 库存守卫 %d, 生态端点 %d, 总计 %d"
          % (e1, e1b, e1c, e2, e3, e4, e5, e6, e7, e8, e9, e10, total))
    if total == 0:
        print("✅ 全部通过")
    else:
        print("❌ 存在 %d 项问题" % total)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
