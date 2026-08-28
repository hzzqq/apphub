# 修正版库存补抓：CZCE 总库存 = 所有"小计"行仓单数量之和；SHFE 取末条小计(合计)。
import os, time, datetime, json
import akshare as ak
import pandas as pd

DATA = os.path.join(os.path.dirname(__file__), "data")

def extract_czce(date, sym):
    d = ak.futures_warehouse_receipt_czce(date=date)
    if not isinstance(d, dict): return None
    t = d.get(sym)
    if t is None: return None
    try:
        sub = t[t.iloc[:,0].astype(str).str.contains("小计")]
        col = [c for c in t.columns if "仓单" in str(c) or "数量" in str(c)]
        if sub.empty or not col: return None
        vals = pd.to_numeric(sub[col[0]], errors="coerce").dropna()
        if vals.empty: return None
        return float(vals.sum())  # 全部小计之和 = 总仓单
    except Exception:
        return None

def extract_shfe(date, sym):
    d = ak.futures_shfe_warehouse_receipt(date=date)
    if not isinstance(d, dict): return None
    t = d.get(sym)
    if t is None: return None
    try:
        sub = t[t.iloc[:,0].astype(str).str.contains("小计")]
        col = [c for c in t.columns if "仓单" in str(c) or "数量" in str(c)]
        if sub.empty or not col: return None
        v = pd.to_numeric(sub[col[0]], errors="coerce").dropna()
        if v.empty: return None
        return float(v.iloc[-1])  # 末条小计=合计
    except Exception:
        return None

TARGETS = [
    ("CZCE", "FG", "futures_CZCE_FG.json", extract_czce, "FG"),
    ("CZCE", "SA", "futures_CZCE_SA.json", extract_czce, "SA"),
    ("CZCE", "SR", "futures_CZCE_SR.json", extract_czce, "SR"),
]

start = datetime.date(2026, 5, 1)
end = datetime.date(2026, 8, 26)
dates = []
d = start
while d <= end:
    if d.weekday() < 5:
        dates.append(d.strftime("%Y%m%d"))
    d += datetime.timedelta(days=1)

for exchange, sym, fname, fn, key in TARGETS:
    path = os.path.join(DATA, fname)
    if not os.path.exists(path):
        print("SKIP (no cache):", fname); continue
    rows = json.load(open(path, encoding="utf-8"))
    by_date = {r["date"]: r for r in rows if isinstance(r, dict) and r.get("date")}
    filled = 0
    for ds in dates:
        iso = ds[:4] + "-" + ds[4:6] + "-" + ds[6:]
        if iso not in by_date:
            continue
        if by_date[iso].get("inventory_total") not in (None, 0):
            continue  # 已有真实非零库存，跳过
        try:
            val = fn(ds, key)
        except Exception:
            val = None
        if val is not None and val > 0:
            by_date[iso]["inventory"] = val
            by_date[iso]["inventory_total"] = val
            by_date[iso]["inventory_warehouse"] = val
            filled += 1
        time.sleep(0.12)
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    nonempty = sum(1 for r in rows if r.get("inventory_total") not in (None, 0))
    print("ENRICH %s: filled=%d  nonzero_inventory_rows=%d" % (fname, filled, nonempty))

print("ALL_DONE")
