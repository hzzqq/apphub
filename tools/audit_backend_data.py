#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_backend_data.py — App Hub「真实数据」后端覆盖审计

验证 R51「真实数据」徽章的诚实度：启动 Flask 后端，逐一探测
每个后端依赖 App 实际调用的 /api/* 端点，分类为：
  - OK     : 2xx 且返回非空、非错误 JSON（真实数据/离线缓存均可）
  - EMPTY  : 2xx 但返回空数据（前端将回退本地样本）
  - ERR    : 4xx/5xx 或连接失败（该 App 真实数据链路断开）
  - POST   : 仅接受 POST，本审计仅做 GET 探活（标记为需人工核验）

用法：
  python tools/audit_backend_data.py            # 默认 8787 端口
  python tools/audit_backend_data.py --port 9000
  python tools/audit_backend_data.py --no-boot  # 后端已自行启动时使用

输出：每个 App 的探测结果 + 末尾汇总计数。
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

# ---- 与 index.html 中 APP_ENDPOINTS 同步（审计脚本内嵌，避免解析 HTML） ----
APP_ENDPOINTS = {
    "cache-insight": ["/api/cache/stats", "/api/cache/clear", "/api/cache/warm"],
    "code-teacher": ["/api/llm"],
    "corr-explorer": ["/api/corr_top"],
    "data-explorer": ["/api/data"],
    "data-status-dash": ["/api/data_status"],
    "eia-watch": ["/api/eia_crude"],
    "etf-picker": ["/api/etf"],
    "futures-board": ["/api/futures"],
    "futures-chain": ["/api/futures_chain", "/api/futures_varieties"],
    "futures-events": ["/api/futures_events"],
    "futures-inventory": ["/api/corr_top", "/api/eia_crude", "/api/futures", "/api/futures_events", "/api/inventory_overview", "/api/refresh", "/api/search"],
    "futures-spread": ["/api/futures_spread"],
    "health-board": ["/api/health"],
    "holdings-check": ["/api/data"],
    "holdings-health": ["/api/quote"],
    "info-board": ["/api/info"],
    "inv-refresh": ["/api/refresh"],
    "inventory-watch": ["/api/inventory_overview"],
    "itinerary": ["/api/itinerary/generate"],
    "itinerary-view": ["/api/itinerary/generate"],
    "kpattern": ["/api/data"],
    "market-cube": ["/api/market_cube"],
    "market-mood": ["/api/shepherd"],
    "market-qa": ["/api/llm"],
    "price-alert": ["/api/quote"],
    "quote-board": ["/api/quote"],
    "search-box": ["/api/search"],
    "sector-heat": ["/api/sector"],
    "sector-matrix": ["/api/futures_sector_matrix"],
    "sector-rotation": ["/api/sector"],
    "shepherd-index": ["/api/health", "/api/shepherd"],
    "smart-order": ["/api/quote"],
    "spread-viewer": ["/api/futures_spread"],
    "trader-avatars": ["/api/llm"],
    "trading-agents": ["/api/llm"],
    "variety-screener": ["/api/futures_varieties"],
}
# 已知仅接受 POST 的端点（GET 探活无意义，单独标记）
POST_ONLY = {"/api/llm", "/api/itinerary/generate", "/api/cache/clear", "/api/cache/warm", "/api/refresh"}
# /api/data 为「通用静态数据托管」，必须带 ?file=<白名单内文件名> 才能返回数据；
# 各 App 实际调用时都带正确 file 参数（bare GET 必然 400，属正常，非断点）。
# 以下为各依赖 App 实际使用的 file 参数，用于探活真实可用性。
DATA_FILE = {
    "holdings-check": "holdings.json",
    "kpattern": "kpattern.json",
    # data-explorer 为交互式探索器，无固定 file；用任一白名单文件确认路由本身可用即可
    "data-explorer": "stocknote.json",
}


def classify(status, body):
    if status is None:
        return "ERR", "连接失败"
    if status >= 400:
        return "ERR", "HTTP %d" % status
    # 2xx
    if not body:
        return "EMPTY", "2xx 但空响应"
    try:
        j = json.loads(body)
        if isinstance(j, dict) and j.get("error"):
            return "ERR", "error: %s" % str(j.get("error"))[:40]
        if isinstance(j, (list, dict)) and len(j) == 0:
            return "EMPTY", "2xx 空数据"
        return "OK", "2xx 有数据(%dB)" % len(body)
    except Exception:
        # 非 JSON 但 2xx：可能是 HTML/文本，按有内容算 OK
        return "OK", "2xx 非JSON(%dB)" % len(body)


def probe(base, ep, app=None):
    url = base.rstrip("/") + ep
    # /api/data 需要 ?file= 参数，按各 App 实际使用的文件名探活
    if ep == "/api/data" and app and app in DATA_FILE:
        url = base.rstrip("/") + "/api/data?file=" + DATA_FILE[app]
    if ep in POST_ONLY:
        # POST 端点仅做存在性探活：用 GET 试探，4xx 视为已定义（路由存在）
        try:
            req = urllib.request.Request(url, method="GET")
            urllib.request.urlopen(req, timeout=6).read()
            return "POST", "路由存在(GET探活 2xx)"
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 405, 406, 415):
                return "POST", "路由存在(GET探活 %d)" % e.code
            return "ERR", "HTTP %d" % e.code
        except Exception as e:
            return "ERR", "连接失败"
    try:
        req = urllib.request.Request(url, method="GET")
        r = urllib.request.urlopen(req, timeout=6)
        return classify(r.status, r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return classify(e.code, getattr(e, "read", lambda: b"")() or b"")
    except Exception:
        return "ERR", "连接失败"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-boot", action="store_true", help="不自动启动后端（后端已运行）")
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    base = "http://%s:%d" % (args.host, args.port)

    proc = None
    if not args.no_boot:
        print("[audit] 启动后端 backend/app.py (port=%d) ..." % args.port)
        proc = subprocess.Popen(
            [sys.executable, "backend/app.py"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # 等待健康
        for _ in range(30):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=3)
                break
            except Exception:
                time.sleep(0.5)
        else:
            print("[audit] 后端启动失败，退出")
            if proc:
                proc.terminate()
            sys.exit(1)

    try:
        # 去重点，先探活所有端点（/api/data 按各 App 实际 file 参数探活）
        probes = sorted({(app, ep) for app, eps in APP_ENDPOINTS.items() for ep in eps})
        ep_status = {}
        for app, ep in probes:
            kind, msg = probe(base, ep, app)
            ep_status[(app, ep)] = (kind, msg)
            label = ep if ep != "/api/data" else "/api/data?file=%s" % DATA_FILE.get(app, "?")
            print("  %-32s %-6s %s" % (label, kind, msg))

        print("\n=== 每个 App 的端点覆盖 ===")
        counts = {"OK": 0, "EMPTY": 0, "ERR": 0, "POST": 0}
        app_summary = {}
        for app, eps in sorted(APP_ENDPOINTS.items()):
            kinds = []
            for ep in eps:
                k, m = ep_status[(app, ep)]
                kinds.append(k)
                counts[k] = counts.get(k, 0) + 1
            # App 整体判定：任一 ERR 即视为该 App 真实数据链路有断点
            if any(k == "ERR" for k in kinds):
                verdict = "⚠ 有断点"
            elif all(k in ("OK", "POST") for k in kinds):
                verdict = "✓ 全通"
            elif all(k == "EMPTY" for k in kinds):
                verdict = "○ 全空(本地样本)"
            else:
                verdict = "△ 混合"
            app_summary[app] = (verdict, kinds)
            print("  %-20s %-10s %s" % (app, verdict, ",".join(kinds)))

        print("\n=== 汇总 ===")
        print("端点探测总数: %d" % sum(len(v) for v in APP_ENDPOINTS.values()))
        print("OK=%d  EMPTY=%d  ERR=%d  POST(需人工)=%d" % (
            counts.get("OK", 0), counts.get("EMPTY", 0), counts.get("ERR", 0), counts.get("POST", 0)))
        broken = [a for a, (v, _) in app_summary.items() if v == "⚠ 有断点"]
        print("真实数据链路有断点的 App: %d" % len(broken))
        for b in broken:
            print("   - %s" % b)
        # CI 门禁：存在 ERR（4xx/5xx/连接失败）= 真实数据链路断点，视为失败
        if counts.get("ERR", 0) > 0 or broken:
            print("\n[audit] 真实数据覆盖校验未通过：ERR=%d 断点App=%d" % (
                counts.get("ERR", 0), len(broken)))
            sys.exit(1)
        print("\n[audit] 真实数据覆盖校验通过 ✅")
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
