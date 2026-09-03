# -*- coding: utf-8 -*-
"""从东方财富 futures_inventory_em 取全品种真实周度库存，生成前端内置 REAL_DATA 紧凑块。
口径与 _bake_inv_em.py 一致（交易所库存/仓单，单位吨），保证离线(file://)与在线(后端缓存)一致。
输出：_realdata_block.js  —— 含 const REAL_DATA = {...}; 可直接嵌入 index.html 替换原 REAL_DATA。
"""
import json, os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))
import _bake_inv_em as B
import akshare as ak

KEEP = 40  # 每品种保留最近 N 个真实库存点（周度，约 40 周 ≈ 9 个月，足够图表+推演播种）

out = {}
ok, fail = [], []
for exch, code, cn in B.MASTER:
    key = "%s:%s" % (exch.upper(), code.lower())
    try:
        df = ak.futures_inventory_em(symbol=cn)
        if df is None or len(df) == 0:
            fail.append((key, cn, "empty"))
            continue
        rows = []
        for _, r in df.iterrows():
            dt = str(r["日期"])[:10]
            v = r.get("库存")
            try:
                v = float(v) if v is not None else None
            except Exception:
                v = None
            if v is None:
                continue
            rows.append({"date": dt, "inventory_total": int(v), "inventory": int(v)})
        if not rows:
            fail.append((key, cn, "no-numeric"))
            continue
        rows = rows[-KEEP:]
        out[key] = rows
        ok.append((key, cn, len(rows), rows[-1]["date"], rows[-1]["inventory_total"]))
    except Exception as e:
        fail.append((key, cn, repr(e)[:80]))

# 写 JS 块
lines = ["const REAL_DATA = {"]
for i, (key, cn, n, lastd, lastv) in enumerate(ok):
    rows = out[key]
    lines.append('  "%s": [' % key)
    for j, r in enumerate(rows):
        comma = "," if j < len(rows) - 1 else ""
        lines.append('    {date:"%s", inventory_total:%d, inventory:%d}%s' % (
            r["date"], r["inventory_total"], r["inventory"], comma))
    comma = "," if i < len(ok) - 1 else ""
    lines.append("  ]" + comma)
lines.append("};")
block = "\n".join(lines)

with open(os.path.join(os.path.dirname(__file__), "_realdata_block.js"), "w", encoding="utf-8") as f:
    f.write(block)

print("=== 离线 REAL_DATA 生成 ===")
print("成功品种 %d / 失败 %d" % (len(ok), len(fail)))
for k, cn, n, d, v in ok:
    print("  OK   %-14s %-5s rows=%-3d last=%s inv=%d" % (k, cn, n, d, v))
if fail:
    print("  失败:")
    for k, cn, m in fail:
        print("    - %-14s %-5s %s" % (k, cn, m))
print("字节数:", len(block))
