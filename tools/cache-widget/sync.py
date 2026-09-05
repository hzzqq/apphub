#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存控制条「单一真源」同步脚本。

为何存在:
  8 个微应用里各内联了一份相同的缓存控制浮窗 + withCache 助手(约 27 行)。
  手工复制会导致漂移(某处改了别处没改)。本脚本把真源放在同目录 widget.html,
  运行后即把 8 个 App 的缓存控制条统一替换为真源内容, 做到「改一处, 全量生效」。

用法:
  python tools/cache-widget/sync.py            # 同步全部目标 App
  python tools/cache-widget/sync.py --check     # 只报告哪些 App 与真源不一致(不写盘)
  python tools/cache-widget/sync.py --apps market-cube etf-picker   # 只同步指定 App

幂等性:
  - 若 App 已含 CACHE-WIDGET-START/END 哨兵标记 -> 整段替换为最新真源
  - 否则若含带 window.withCache 的 <script> 块 -> 整块替换为最新真源(加哨兵)
  - 否则在 <body> 之后插入最新真源
  - 每次运行结果一致, 可重复执行。

行尾安全:
  以「字节级」替换, 严格保留每个文件原有的行尾(CRLF/LF)与无关字节,
  只替换缓存控制条那一段, 不产生整文件行尾漂移。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WIDGET_SRC = os.path.join(HERE, "widget.html")
APP_ROOT = os.path.dirname(os.path.dirname(HERE))  # 仓库根 = tools/ 的上一级

TARGET_APPS = [
    "market-cube", "etf-picker", "sector-rotation", "sector-matrix",
    "futures-chain", "shepherd-index", "price-alert", "smart-order",
]

START_B = b"<!-- CACHE-WIDGET-START -->"
END_B = b"<!-- CACHE-WIDGET-END -->"
_SENTINEL_RE = re.compile(re.escape(START_B) + b"[\\s\\S]*?" + re.escape(END_B), re.M)
# 旧式(无哨兵)内联块: 含 window.withCache 的 <script ...>...</script>
_OLD_BLOCK_RE = re.compile(
    rb"<script[^>]*>[\s\S]*?window\.withCache[\s\S]*?</script>", re.M)


def _detect_eol(data: bytes) -> bytes:
    return b"\r\n" if b"\r\n" in data else b"\n"


def load_canonical_bytes():
    with open(WIDGET_SRC, "rb") as f:
        text = f.read().decode("utf-8")
    m = _SENTINEL_RE.search(text.encode("utf-8"))
    if not m:
        raise SystemExit("widget.html 缺少哨兵标记 %s/%s" % (START_B, END_B))
    return m.group(0)  # bytes, 带原生行尾


def sync_app(app_dir, canonical, dry_run):
    path = os.path.join(APP_ROOT, app_dir, "index.html")
    if not os.path.isfile(path):
        print("  ! 跳过 %s (无 index.html)" % app_dir)
        return "skip"
    with open(path, "rb") as f:
        data = f.read()

    eol = _detect_eol(data)
    # 真源按目标文件行尾归一, 保证插入段与文件其余部分行尾一致
    canon = canonical.replace(b"\r\n", b"\n").replace(b"\n", eol)

    if _SENTINEL_RE.search(data):
        new_data = _SENTINEL_RE.sub(canon, data)
        mode = "sentinel-replace"
    elif _OLD_BLOCK_RE.search(data):
        new_data = _OLD_BLOCK_RE.sub(canon, data)
        mode = "old-block-replace"
    else:
        # 在 <body ...> 之后插入
        m = re.search(rb"<body[^>]*>", data)
        if not m:
            print("  ! 跳过 %s (找不到 <body>)" % app_dir)
            return "skip"
        insert_at = m.end()
        new_data = data[:insert_at] + eol + canon + eol + data[insert_at:]
        mode = "body-insert"

    if new_data == data:
        return "unchanged"

    if dry_run:
        print("  * [check] %s 需要更新 (%s)" % (app_dir, mode))
        return "needs-update"
    with open(path, "wb") as f:
        f.write(new_data)
    print("  + 已同步 %s (%s)" % (app_dir, mode))
    return "updated"


def main():
    args = sys.argv[1:]
    dry_run = "--check" in args
    explicit = [a for a in args if not a.startswith("--")]
    apps = explicit if explicit else TARGET_APPS

    canonical = load_canonical_bytes()
    print("%s 缓存控制条同步 -> %d 个 App%s"
          % ("[CHECK]" if dry_run else "[SYNC]", len(apps),
             " (干跑, 不写盘)" if dry_run else ""))
    counts = {}
    for app in apps:
        r = sync_app(app, canonical, dry_run)
        counts[r] = counts.get(r, 0) + 1
    print("完成: updated=%d unchanged=%d skip=%d needs_update=%d"
          % (counts.get("updated", 0), counts.get("unchanged", 0),
             counts.get("skip", 0), counts.get("needs-update", 0)))


if __name__ == "__main__":
    main()
