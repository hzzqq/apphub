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
NODE = r"C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2/node.exe"
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
        ("/api/blackswan", 200),
        ("/api/earnings?code=600519", 200),
        ("/api/search?q=茅台&type=stock", 200),
        ("/api/etf", 200),
        ("/api/sector", 200),
        ("/api/data?file=theme.json", 200),
        ("/api/trading_agents", 200),
        ("/api/code_teacher", 200),
        ("/api/theme", 200),
        # 越权/参数错误应正确拒绝
        ("/api/data?file=../../etc/passwd", 400),
        ("/api/futures?mode=bogus", 400),
        ("/api/earnings", 400),
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


def main():
    print("=" * 60)
    print("App Hub 全量校验 @ %s" % ROOT)
    print("=" * 60)
    e1 = check_frontend()
    e1b = check_frontend_tests()
    e2 = check_backend()
    e3 = check_data_whitelist()
    total = e1 + e1b + e2 + e3
    print("─" * 60)
    print("汇总: 前端错误 %d, 前端单测失败 %d, 后端错误 %d, 一致性错误 %d, 总计 %d"
          % (e1, e1b, e2, e3, total))
    if total == 0:
        print("✅ 全部通过")
    else:
        print("❌ 存在 %d 项问题" % total)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
