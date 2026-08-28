# -*- coding: utf-8 -*-
"""
期库镜 · 真实数据抓取脚本（在有网机器上运行一次，长期使用）
========================================================
把 akshare 真实期货行情 + 多口径库存抓下来，存成:
    backend/data/futures_<交易所>_<品种>.json
后端 /api/futures 会优先读取这些文件 -> 期库镜默认即真实数据。

对齐 akshare 1.18.x 的真实接口名:
    - 行情: ak.futures_zh_daily_sina(symbol="<代码>0")  # 全交易所主力连续日线
    - 库存(仓单日报, 按交易日返回):
        SHFE -> ak.futures_shfe_warehouse_receipt(date="YYYYMMDD")
        CZCE -> ak.futures_warehouse_receipt_czce(date="YYYYMMDD")
        DCE  -> ak.futures_warehouse_receipt_dce(date="YYYYMMDD")
        INE  -> ak.futures_ine_warehouse_receipt(date="YYYYMMDD")
      取各品种"小计"行的"仓单数量"作为当日库存(吨)。
    库存接口仅在交易日返回有效数据；非交易日/失败 -> 该日库存留 null(不编造)。

用法:
    cd E:/project/app/backend
    pip install akshare pandas
    python fetch_real_futures.py                 # 抓取默认品种列表
    python fetch_real_futures.py --symbol sp --exchange SHFE --days 365
    python fetch_real_futures.py --all           # 抓取内置全品种列表(较慢)
"""
import argparse
import json
import os
import datetime
import sys

import akshare as ak
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEFAULT_SYMBOLS = [
    ("SHFE", "sp"), ("SHFE", "cu"), ("SHFE", "al"), ("SHFE", "rb"),
    ("DCE", "i"), ("DCE", "m"), ("DCE", "y"), ("CZCE", "TA"),
    ("CZCE", "MA"), ("CZCE", "SR"), ("INE", "sc"),
]


def _to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _extr_subtotal(df):
    """从仓单日报(含'小计'行)里取 仓单数量 小计值。"""
    if df is None:
        return None
    try:
        cols = [c for c in df.columns if "仓单" in str(c) or "数量" in str(c)]
        if not cols:
            return None
        col = cols[0]
        sub = df[df.iloc[:, 0].astype(str).str.contains("小计")]
        if sub.empty:
            return None
        v = _to_float(sub.iloc[0][col])
        return v if (v is not None and v > 0) else None
    except Exception:
        return None


def fetch_kline(sina_symbol, start, end):
    """真实主力连续日线 -> {date: close}"""
    try:
        df = ak.futures_zh_daily_sina(symbol=sina_symbol.lower() + "0")
        if df is None or df.empty:
            return {}
        df = df[["date", "close"]].copy()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        out = {}
        for _, r in df.iterrows():
            d = r["date"]
            if start <= d <= end:
                out[d] = _to_float(r["close"])
        return out
    except Exception as e:
        print("  [warn] 行情抓取失败 %s: %s" % (sina_symbol, e))
        return {}


def _inv_shfe(symbol, ymd):
    try:
        d = ak.futures_shfe_warehouse_receipt(date=ymd)
        if not isinstance(d, dict):
            return None
        t = d.get(symbol.lower())
        return _extr_subtotal(t)
    except Exception:
        return None


def _inv_czce(symbol, ymd):
    try:
        d = ak.futures_warehouse_receipt_czce(date=ymd)
        if not isinstance(d, dict):
            return None
        t = d.get(symbol.upper())
        return _extr_subtotal(t)
    except Exception:
        return None


def _inv_dce(symbol, ymd):
    try:
        d = ak.futures_warehouse_receipt_dce(date=ymd)
        if not hasattr(d, "columns"):
            return None
        sc = [c for c in d.columns if "品种" in str(c)]
        if not sc:
            return None
        row = d[d[sc[0]].astype(str).str.lower() == symbol.lower()]
        if row.empty:
            return None
        cols = [c for c in d.columns if "仓单" in str(c) or "数量" in str(c)]
        if not cols:
            return None
        v = _to_float(row.iloc[0][cols[0]])
        return v if (v is not None and v > 0) else None
    except Exception:
        return None


def _inv_ine(symbol, ymd):
    try:
        d = ak.futures_ine_warehouse_receipt(date=ymd)
        if not isinstance(d, dict):
            return None
        t = d.get(symbol.lower())
        return _extr_subtotal(t)
    except Exception:
        return None


INV_FN = {"SHFE": _inv_shfe, "CZCE": _inv_czce, "DCE": _inv_dce, "INE": _inv_ine}


def fetch_inventory(exchange, symbol, start, end):
    """逐交易日抽取真实仓单库存 -> {date: inventory_total(吨)}"""
    fn = INV_FN.get(exchange)
    if fn is None:
        return {}
    out = {}
    d = start
    while d <= end:
        ymd = d.strftime("%Y%m%d")
        iso = d.strftime("%Y-%m-%d")
        v = fn(symbol, ymd)
        if v is not None:
            out[iso] = v
        d += datetime.timedelta(days=1)
    return out


def fetch_one(exchange, symbol, days):
    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    s, e = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    print("抓取 %s/%s (%s ~ %s) ..." % (exchange, symbol, s, e))
    kl = fetch_kline(symbol, s, e)
    inv = fetch_inventory(exchange, symbol, start, end)
    dates = sorted(set(kl.keys()) | set(inv.keys()))
    rows = []
    for d in dates:
        iv = inv.get(d)
        rows.append({
            "date": d,
            "close": kl.get(d),
            "inventory": iv,
            "inventory_total": iv,
            "inventory_circ": None,
            "inventory_warehouse": iv,
            "inventory_bonded": None,
        })
    if not rows:
        print("  [skip] 无数据")
        return False
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, "futures_%s_%s.json" % (exchange, symbol))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("  [ok] 写入 %s (%d 条, 库存点 %d)" % (path, len(rows), len(inv)))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default=None)
    ap.add_argument("--exchange", default="SHFE")
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--all", action="store_true", help="抓取内置全品种列表")
    args = ap.parse_args()

    targets = []
    if args.all:
        targets = DEFAULT_SYMBOLS
    elif args.symbol:
        targets = [(args.exchange, args.symbol)]
    else:
        targets = DEFAULT_SYMBOLS[:1]  # 默认只抓纸浆 SP，最常用

    ok = 0
    for ex, sym in targets:
        try:
            if fetch_one(ex, sym, args.days):
                ok += 1
        except Exception as e:
            print("  [error] %s/%s: %s" % (ex, sym, e))
    print("\n完成：成功 %d / 共 %d" % (ok, len(targets)))
    print("后端 /api/futures 现在会优先读取这些真实缓存文件 -> 期库镜默认真实数据。")


if __name__ == "__main__":
    main()
