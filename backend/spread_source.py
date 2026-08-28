# -*- coding: utf-8 -*-
"""期货跨期价差 · 真实数据来源（akshare）。

被 backend/app.py（实时 API）与 backend/build_spread_cache.py（内嵌缓存构建）共用，
避免重复实现真实抓取逻辑（DRY）。

真实数据抓取失败时一律抛异常，由上层决定回退策略：
  - app.py 实时接口 -> 回退 _sample_spread_series 合成样本；
  - build_spread_cache.py -> 不写缓存（绝不以假乱真）。
"""
import os
import re
import sys
import json
from datetime import datetime, timedelta

try:
    import akshare as ak
    import pandas as pd
    _HAS_AK = True
except Exception:  # noqa
    _HAS_AK = False

# 品种 -> (交易所, 根代码, 类型 commodity|index, 对应现货指数代码)
# 根代码用于拼接合约: root + YYMM, 例如 sp + 2509 = "sp2509"
SPREAD_META = {
    "sp": ("SHFE", "sp", "commodity", None),
    "cu": ("SHFE", "cu", "commodity", None),
    "al": ("SHFE", "al", "commodity", None),
    "zn": ("SHFE", "zn", "commodity", None),
    "au": ("SHFE", "au", "commodity", None),
    "ag": ("SHFE", "ag", "commodity", None),
    "rb": ("SHFE", "rb", "commodity", None),
    "i":  ("DCE",  "i",  "commodity", None),
    "j":  ("DCE",  "j",  "commodity", None),
    "m":  ("DCE",  "m",  "commodity", None),
    "y":  ("DCE",  "y",  "commodity", None),
    "p":  ("DCE",  "p",  "commodity", None),
    "c":  ("DCE",  "c",  "commodity", None),
    "jd": ("DCE",  "jd", "commodity", None),
    "eg": ("DCE",  "eg", "commodity", None),
    "eb": ("DCE",  "eb", "commodity", None),
    "SA": ("CZCE", "SA", "commodity", None),
    "FG": ("CZCE", "FG", "commodity", None),
    "SR": ("CZCE", "SR", "commodity", None),
    "CF": ("CZCE", "CF", "commodity", None),
    "MA": ("CZCE", "MA", "commodity", None),
    "TA": ("CZCE", "TA", "commodity", None),
    "sc": ("INE",  "sc", "commodity", None),
    "IF": ("CFFEX", "if", "index", "sh000300"),
    "IH": ("CFFEX", "ih", "index", "sh000016"),
    "IC": ("CFFEX", "ic", "index", "sh000905"),
    "IM": ("CFFEX", "im", "index", "sh000852"),
}


def _require_ak():
    if not _HAS_AK:
        raise RuntimeError("akshare 未安装，无法抓取真实数据")
    return ak, pd


# ───────────────── 郑商所(CZCE) 真实数据 ─────────────────
# 新浪期货接口当前对 CZCE 整体解析故障(list index out of range)，故改走
# get_futures_daily(market="CZCE") 一次性抓全市场后按品种+合约码提取。
# 该接口符号编码为「品种+1位年+2位月」(如 2026-09 -> '609')，与 sina 的
# 'sr2509' 不同，需做 yymm[1:] 映射。单次全市场抓取约 120s，进程内缓存复用。
_CZCE_MARKET = None  # {VARIETY: {yymm3: {date: close}}}
_BAKED_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "spread_cache.json")


def load_baked_cache(path=None):
    """读取 build_spread_cache.py 写出的本地已烘焙真实缓存(秒级、离线可用)。"""
    path = path or _BAKED_CACHE_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa
        return None


def fetch_czce_market(refresh=False):
    """一次性抓取郑商所全市场日线(约 400 交易日)，返回
    {VARIETY: {yymm3: {date: close}}}。结果进程内缓存，避免重复拉取。"""
    global _CZCE_MARKET
    if _CZCE_MARKET is not None and not refresh:
        return _CZCE_MARKET
    ak, pd = _require_ak()
    start = (datetime.today() - timedelta(days=400)).strftime("%Y%m%d")
    end = datetime.today().strftime("%Y%m%d")
    df = ak.get_futures_daily(start_date=start, end_date=end, market="CZCE")
    m = {}
    for _, r in df.iterrows():
        sym = str(r.get("symbol", ""))
        mm = re.match(r"^([A-Za-z]+)(\d{3})$", sym)
        if not mm:
            continue
        var, code = mm.group(1).upper(), mm.group(2)
        d = str(r.get("date", ""))[:10]
        if not d:
            continue
        try:
            c = float(r["close"])
        except (TypeError, ValueError, KeyError):
            continue
        m.setdefault(var, {}).setdefault(code, {})[d] = c
    _CZCE_MARKET = m
    return m


def _fetch_czce_contract(variety, yymm):
    """郑商所合约真实收盘 -> {date: close}。

    优先读本地已烘焙缓存(秒级)，否则抓全市场(约120s)按 code=yymm[1:] 提取。
    """
    # 1) 本地已烘焙缓存(快速、离线友好)
    baked = load_baked_cache()
    if baked:
        rec = baked.get("varieties", {}).get(variety, {})
        ser = rec.get("contracts", {}).get(yymm)
        if ser:
            return dict(ser)
    # 2) 抓全市场提取
    mkt = fetch_czce_market()
    code = yymm[1:]  # '2509' -> '509'
    ser = mkt.get(variety.upper(), {}).get(code)
    if not ser:
        raise RuntimeError("CZCE 合约 %s%s 无数据" % (variety, yymm))
    return dict(ser)


def fetch_contract_kline(symbol):
    """特定合约日线收盘价 -> {date: close}。失败抛异常。

    郑商所(CZCE)合约因新浪接口故障改走 fetch_czce_market 路径。
    """
    vkey = symbol[:-4].upper() if len(symbol) >= 5 else symbol.upper()
    meta = SPREAD_META.get(vkey)
    if meta and meta[0] == "CZCE":
        return _fetch_czce_contract(vkey, symbol[-4:])
    ak, pd = _require_ak()
    df = ak.futures_zh_daily_sina(symbol=symbol.lower())
    if df is None or getattr(df, "empty", True):
        raise RuntimeError("合约 %s 无行情" % symbol)
    df = df.rename(columns=lambda c: str(c).strip())
    date_col = next((c for c in df.columns
                     if "date" in str(c).lower() or "日期" in c), None)
    close_col = next((c for c in df.columns
                      if "close" in str(c).lower() or "收盘" in c), None)
    if not date_col or not close_col:
        raise RuntimeError("合约 %s 列不匹配: %s" % (symbol, list(df.columns)))
    df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")
    out = {}
    for _, r in df[[date_col, close_col]].dropna().iterrows():
        try:
            out[str(r[date_col])] = float(r[close_col])
        except (TypeError, ValueError):
            continue
    if not out:
        raise RuntimeError("合约 %s 空数据" % symbol)
    return out


def fetch_index_series(symbol):
    """现货指数日线 -> {date: close}。失败抛异常。"""
    ak, pd = _require_ak()
    df = ak.stock_zh_index_daily(symbol=symbol.lower())
    if df is None or getattr(df, "empty", True):
        raise RuntimeError("指数 %s 无数据" % symbol)
    df = df.rename(columns=lambda c: str(c).strip())
    date_col = next((c for c in df.columns
                     if "date" in str(c).lower() or "日期" in c), None)
    close_col = next((c for c in df.columns
                      if "close" in str(c).lower() or "收盘" in c), None)
    if not date_col or not close_col:
        raise RuntimeError("指数 %s 列不匹配: %s" % (symbol, list(df.columns)))
    df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
    df[date_col] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
    out = {}
    for _, r in df[[date_col, close_col]].dropna().iterrows():
        out[r[date_col]] = float(r[close_col])
    if not out:
        raise RuntimeError("指数 %s 空数据" % symbol)
    return out


def compute_spread_series(variety, monthA, monthB, ytype, start="", end=""):
    """返回 [{date, priceA, priceB, spread, y}, ...]；失败抛异常。

    spread = priceA(近月) - priceB(远月)，可正可负；
    y = 商品近月价 / 股指对应现货指数(ytype=index 时)。
    """
    meta = SPREAD_META.get(variety)
    if not meta:
        raise ValueError("未知品种 %s" % variety)
    _exch, root, vtype, index_sym = meta

    A = fetch_contract_kline("%s%s" % (root, monthA))
    B = fetch_contract_kline("%s%s" % (root, monthB))
    dates = sorted(set(A) & set(B))
    if not dates:
        raise RuntimeError("合约 %s/%s 无重叠交易日" % (monthA, monthB))

    if ytype == "index" and vtype == "index" and index_sym:
        ymap = fetch_index_series(index_sym)
        use_idx = True
    else:
        ymap = A
        use_idx = False

    out = []
    for d in dates:
        if use_idx:
            yv = ymap.get(d)
            if yv is None:
                continue
        else:
            yv = A[d]
        out.append({
            "date": d,
            "priceA": round(A[d], 2),
            "priceB": round(B[d], 2),
            "spread": round(A[d] - B[d], 2),
            "y": round(yv, 2),
        })

    if start:
        out = [r for r in out if r["date"] >= start]
    if end:
        out = [r for r in out if r["date"] <= end]
    if len(out) < 3:
        raise RuntimeError("真实价差数据过少")
    return out
