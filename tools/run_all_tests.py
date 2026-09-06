#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
App Hub 全量前端单测 + 可选后端 pytest 一键运行器。

- 发现仓库根下所有 */test/run.js（零依赖 Node vm 沙箱单测），逐个用 managed node 跑，
  收集每个套件的退出码与最后几行输出，打印 ✓/✗ 汇总。
- 可选 --backend：额外用隔离 venv 的 pytest 跑 backend/test_app.py + backend/test_cache.py。
- 任一测试失败则进程退出码非 0（可直接挂 CI / pre-push）。

用法:
    python tools/run_all_tests.py            # 仅前端单测
    python tools/run_all_tests.py --backend  # 前端单测 + 后端 pytest
    python tools/run_all_tests.py --quiet    # 仅打印失败项
"""
import os
import sys
import glob
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_node():
    # 优先用隔离的 managed node 二进制，回退到 PATH 上的 node
    pats = glob.glob(os.path.join(
        os.environ.get("USERPROFILE", "C:/Users/Administrator"),
        ".workbuddy", "binaries", "node", "versions", "2*", "node.exe"))
    if pats:
        return sorted(pats)[-1]
    on_path = shutil.which("node")
    if on_path:
        return on_path
    raise RuntimeError("找不到 node 二进制：请将 node 加入 PATH 或检查 managed node 路径")


def find_venv_python():
    # managed python venv（隔离，已装 flask/flask-cors/pytest）
    cand = os.path.join(
        os.environ.get("USERPROFILE", "C:/Users/Administrator"),
        ".workbuddy", "binaries", "python", "envs", "default", "Scripts", "python.exe")
    if os.path.exists(cand):
        return cand
    return None


def run_frontend(node):
    # 顶层 app 目录下的 */test/run.js，外加仓库根 test/run.js（大厅自测）
    suites = sorted(glob.glob(os.path.join(ROOT, "*", "test", "run.js")))
    root_test = os.path.join(ROOT, "test", "run.js")
    if os.path.exists(root_test):
        suites.append(root_test)
    total, passed, failed = 0, 0, 0
    failures = []
    for suite in suites:
        app = os.path.basename(os.path.dirname(os.path.dirname(suite)))
        total += 1
        try:
            r = subprocess.run([node, suite], cwd=ROOT, capture_output=True,
                               text=True, timeout=120)
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
            r = subprocess.CompletedProcess([node, suite], 124, "", "timeout")
        if ok:
            passed += 1
            print("  ✓ %-22s" % app)
        else:
            failed += 1
            failures.append((app, r.stdout.strip().splitlines()[-3:], r.stderr.strip().splitlines()[-3:]))
            print("  ✗ %-22s (exit %s)" % (app, r.returncode))
    return total, passed, failed, failures


def run_backend():
    py = find_venv_python()
    if not py:
        print("  (跳过后端 pytest：未找到隔离 venv python，")
        print("   可跑 `python -m venv` 并 pip install flask flask-cors pytest)")
        return None
    r = subprocess.run([py, "-m", "pytest", "-q", "test_app.py", "test_cache.py"],
                       cwd=os.path.join(ROOT, "backend"), capture_output=True, text=True, timeout=300)
    ok = r.returncode == 0
    print(r.stdout.strip().splitlines()[-3:] and "\n".join(r.stdout.strip().splitlines()[-3:]) or r.stderr.strip()[-3:])
    return ok


def main():
    args = set(sys.argv[1:])
    quiet = "--quiet" in args
    with_backend = "--backend" in args

    node = find_node()
    print("node: %s" % node)
    print("— 前端单测 —")
    total, passed, failed, failures = run_frontend(node)

    if not quiet:
        pass
    else:
        for app, out, err in failures:
            print("\n[%s] stdout tail:" % app)
            print("\n".join(out))
            if err:
                print("[%s] stderr tail:" % app)
                print("\n".join(err))

    print("\n前端单测汇总：%d 套件，%d 通过 / %d 失败" % (total, passed, failed))

    backend_ok = True
    if with_backend:
        print("\n— 后端 pytest —")
        res = run_backend()
        if res is False:
            backend_ok = False

    print()
    if failed == 0 and backend_ok:
        print("✅ 全部通过")
        sys.exit(0)
    else:
        print("❌ 存在失败项")
        sys.exit(1)


if __name__ == "__main__":
    main()
