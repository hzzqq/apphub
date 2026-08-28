# 限时库存补抓：对可抓到的交易所品种，填充真实仓单库存到已烤缓存。
# DCE(JD/EG) 接口在本环境不稳定，跳过。抓不到的日期保持 null（诚实，绝不编造）。
import os, sys, time, datetime, json
import akshare as ak

DATA = os.path.join(os.path.dirname(__file__), "data")

def extract_shfe(date, sym="sp"):
    d = ak.futures_shfe_warehouse_receipt(date=date)
    if not isinstance(d, dict): return None
    t = d.get(sym)
    if t is None: return None
    try:
        sub = t[t.iloc[:,0].astype(str).str.contains("小计")]
        col = [c for c in t.columns if "仓单" in str(c) or "数量" in str(c)]
        if sub.empty or not col: return None
        return float(sub.iloc[0][col[0]])
    except Exception:
        return None

def extract_czce(date, sym):
    d = ak.futures_warehouse_receipt_czce(date=date)
    if not isinstance(d, dict): return None
    t = d.get(sym)
    if t is None: return None
    try:
        sub = t[t.iloc[:,0].astype(str).str.contains("小计")]
        col = [c for c in t.columns if "仓单" in str(c) or "数量" in str(c)]
        if sub.empty or not col: return None
        return float(sub.iloc[0][col[0]])
    except Exception:
        return None

TARGETS = [
    ("SHFE", "sp", "futures_SHFE_sp.json", extract_shfe, "sp"),
    ("CZCE", "FG", "futures_CZCE_FG.json", extract_czce, "FG"),
    ("CZCE", "SA", "futures_CZCE_SA.json", extract_czce, "SA"),
    ("CZCE", "SR", "futures_CZCE_SR.json", extract_czce, "SR"),
]

# 近期约 4 个月工作日（轻量，避免全年遍历被限流）
start = datetime.date(2026, 5, 1)
end = datetime.date(2026, 8, 26)
dates = []
d = start
while d <= end:
    if d.weekday() < 5:  # 周一到周五
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
        # 缓存里的日期格式是 YYYY-MM-DD
        iso = ds[:4] + "-" + ds[4:6] + "-" + ds[6:]
        if iso not in by_date:
            continue
        if by_date[iso].get("inventory_total") is not None:
            continue  # 已有真实库存，跳过
        try:
            val = fn(ds, key) if exchange == "SHFE" else fn(ds, key)
        except Exception:
            val = None
        if val is not None:
            by_date[iso]["inventory"] = val
            by_date[iso]["inventory_total"] = val
            by_date[iso]["inventory_warehouse"] = val
            filled += 1
        time.sleep(0.12)
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("ENRICH %s: filled=%d  total_rows=%d" % (fname, filled, len(rows)))

print("ALL_DONE")
