#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_hooks.py — 安装 App Hub 的 git pre-commit 钩子（项目硬规则）

futures-inventory/index.html 由生成器重建，禁止提交其任何改动。
本脚本把拦截逻辑写入 .git/hooks/pre-commit，使「误 git add -A」也会在提交时
被硬性拦截，忘也忘不掉。.git/hooks 不被 git 跟踪、不会随 push 传播，
故 clone / 重装后用 `python tools/install_hooks.py` 重跑一次即可恢复保护。

用法:
    python tools/install_hooks.py
"""
import os

HOOK = """#!/bin/sh
# App Hub 硬规则：futures-inventory/index.html 由生成器重建，禁止提交其改动。
protected="futures-inventory/index.html"
if git diff --cached --name-only | grep -qx "$protected"; then
  echo "【禁止提交】$protected 在工作树有改动，按项目硬规则禁止提交！" >&2
  echo "  若确需更新，请走生成器流程并明确授权；本次提交已被 pre-commit 钩子拦截。" >&2
  exit 1
fi
exit 0
"""

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(ROOT, ".git", "hooks", "pre-commit")


def main():
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(HOOK)
    try:
        os.chmod(path, 0o755)
    except Exception:
        pass
    print("已安装 pre-commit 钩子: %s" % path)


if __name__ == "__main__":
    main()
