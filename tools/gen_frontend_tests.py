# -*- coding: utf-8 -*-
"""
tools/gen_frontend_tests.py — App Hub 前端单测「共享生成器」（单一真源）。

把 26 个由本项目注入脚手架的 test/run.js（18 个 P2 + 8 个 P1 缓存型 App）
改写为依赖 tools/test-scaffold.js 的薄封装，消除 26 份重复的内联脚手架。
用法：
    python tools/gen_frontend_tests.py            # 重写所有目标为薄封装
    python tools/gen_frontend_tests.py --check    # 仅校验是否已是薄封装（非薄封装则非零退出）

注意：另 10 个历史遗留 test/run.js（blackswan / bookmark-manager / code-teacher /
earnings-calendar / futures-inventory / password-vault / stocknote / theme-studio /
trading-agents 等）使用更早的脚手架约定，不在此脚本处理范围，保持原样。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app 根目录(E:/project/app)
# 26 个由本项目（P1/P2）注入统一脚手架的 App
TARGETS = [
    # P2（18）
    "cache-insight", "countdown", "cube-trainer", "desktop-pet", "expense-ledger",
    "focus-timer", "futures-spread", "habit-tracker", "health-check", "holdings-check",
    "itinerary", "kpattern", "market-brief", "mood-meter", "recipe-box",
    "todo-list", "unit-converter", "workout-log",
    # P1 缓存型（7；etf-picker 为最早自研规范测试，脚手架签名不同且唯一，保持原样）
    "market-cube", "sector-rotation", "sector-matrix", "futures-chain",
    "shepherd-index", "price-alert", "smart-order",
]
REQUIRE_LINE = 'const { runAppTest } = require("../../tools/test-scaffold.js");\n'


def is_thin(path):
    with open(path, encoding="utf-8") as f:
        return REQUIRE_LINE.strip() in f.read()


def to_thin(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    # 脚手架结束行：P2 在 function arrEq；P1 缓存型在 const eq =
    end = None
    for i, l in enumerate(lines):
        if "function arrEq" in l or "const eq =" in l:
            end = i
            break
    if end is None:
        raise RuntimeError("找不到脚手架结束标记(function arrEq / const eq =): " + path)
    # 页脚起始行：汇总：
    foot = None
    for i, l in enumerate(lines):
        if "汇总：" in l:
            foot = i
            break
    if foot is None:
        raise RuntimeError("找不到页脚标记(汇总：): " + path)
    middle = "\n".join(lines[end + 1:foot]).strip("\n")
    out = (
        REQUIRE_LINE
        + "runAppTest(__dirname, (api) => {\n"
        + "  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;\n"
        + middle
        + "\n});\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)


def main():
    check_only = "--check" in sys.argv
    problems = []
    for d in TARGETS:
        p = os.path.join(ROOT, d, "test", "run.js")
        if not os.path.exists(p):
            problems.append("缺失: " + d)
            continue
        if check_only:
            if not is_thin(p):
                problems.append("非薄封装: " + d)
        else:
            if is_thin(p):
                print("skip (已薄封装):", d)
            else:
                to_thin(p)
                print("converted:", d)
    if problems:
        print("\n问题：")
        for x in problems:
            print("  - " + x)
        sys.exit(1)
    print("\nOK: 全部目标已为薄封装 ✅" if check_only else "\n完成 ✅")


if __name__ == "__main__":
    main()
