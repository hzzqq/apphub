# -*- coding: utf-8 -*-
"""
期货价差望远镜 · 真实缓存构建脚本（在有网机器上运行一次，长期使用）
================================================================
把 akshare 真实合约日线抓下来，内嵌写进 futures-spread/index.html 的
REAL_CACHE 占位符。这样即便后端黑窗口被关，双击该 HTML 也能显示真实
（快照）价差数据，而不只是合成样本。

用法:
    cd E:/project/app/backend
    pip install akshare pandas
    python build_spread_cache.py                 # 抓取全部品种(默认)
    python build_spread_cache.py --varieties sp cu rb   # 只抓指定品种
    python build_spread_cache.py --missing-only  # 只补齐 REAL_CACHE 中缺失的品种(保留已有真实数据)

说明:
    - 每个品种抓取 当前月-14 ~ 当前月+4 的 19 个 YYMM 合约月份的日线收盘;
      未上市合约 akshare 返回空 -> 自动跳过。
    - 股指(IF/IH/IC/IM)额外抓取对应现货指数序列作为 Y 轴。
    - 真实抓取失败绝不写入假数据: 若整轮无任何真实数据, 不覆盖已有缓存。
    - 配合 refresh_data.bat 使用: 双击 refresh_data.bat 即重新烘焙真实快照。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spread_source as ss

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "..", "futures-spread", "index.html")
CACHE_RE = re.compile(r"/\*__SPREAD_CACHE_START__\*/.*?/\*__SPREAD_CACHE_END__\*/", re.S)


def gen_months():
    """生成覆盖 当前月-14 ~ 当前月+4 的 19 个 YYMM 合约月份。

    偏重历史已上市合约(便于抓取真实序列做快照), 远月越界(未上市)由
    akshare 返回空 -> 自动跳过, 不影响其它合约。
    """
    now = datetime.now()
    y, m = now.year, now.month - 14
    arr = []
    for _ in range(19):
        if m > 12:
            y += 1
            m -= 12
        if m < 1:
            m += 12
            y -= 1
        arr.append("%02d%02d" % (y % 100, m))
        m += 1
    return arr


def read_existing_cache():
    """读取 index.html 中已有的 REAL_CACHE(避免重跑时丢失已抓真实数据)。"""
    try:
        html = open(HTML, "r", encoding="utf-8").read()
        m = CACHE_RE.search(html)
        if m:
            inner = re.search(r"const REAL_CACHE = (.*?);", m.group(0), re.S)
            if inner:
                return json.loads(inner.group(1))
    except Exception:  # noqa
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--varieties", nargs="*", default=None,
                    help="只抓指定品种(默认全部)")
    ap.add_argument("--missing-only", action="store_true",
                    help="只补充 REAL_CACHE 中缺失的品种, 保留已有真实数据")
    args = ap.parse_args()

    existing = read_existing_cache() or {"varieties": {}}
    existing_varieties = existing.get("varieties", {})

    if args.missing_only:
        varieties = [v for v in ss.SPREAD_META.keys() if v not in existing_varieties]
        print("REAL_CACHE 已含 %d 品种; 待补齐缺失品种: %s" %
              (len(existing_varieties), ", ".join(varieties) or "无(已全部就绪)"))
    else:
        varieties = args.varieties or list(ss.SPREAD_META.keys())

    months = gen_months()
    out = {"cached_at": datetime.now().strftime("%Y-%m-%d"), "varieties": {}}
    # 先合并已有真实数据(保留), 再补充缺失 —— 绝不丢弃已抓真实序列
    for v, rec in existing_varieties.items():
        out["varieties"][v] = rec

    # 区分郑商所(CZCE)与非CZCE: CZCE 新浪接口故障, 需一次性抓全市场后提取
    czce_vars = [v for v in varieties if ss.SPREAD_META.get(v, ("", "", "", ""))[0] == "CZCE"]
    other_vars = [v for v in varieties if v not in czce_vars]

    print("期货价差真实缓存构建: 新抓 %d 品种(其中 CZCE %d), 每品种 %d 合约月份"
          % (len(varieties), len(czce_vars), len(months)))

    # 非 CZCE: 逐合约 sina(快速)
    for v in other_vars:
        if v not in ss.SPREAD_META:
            print("  [skip] 未知品种 %s" % v)
            continue
        _exch, root, vtype, index_sym = ss.SPREAD_META[v]
        contracts = {}
        for mo in months:
            try:
                kl = ss.fetch_contract_kline("%s%s" % (root, mo))
                if kl:
                    contracts[mo] = kl
            except Exception as e:  # noqa
                print("  [skip] %s/%s: %s" % (v, mo, str(e)[:50]))
        rec = {"contracts": contracts}
        if vtype == "index" and index_sym:
            try:
                rec["index"] = ss.fetch_index_series(index_sym)
                print("  [ok] %s: %d 合约 + 指数(%d点)" % (v, len(contracts), len(rec["index"])))
            except Exception as e:  # noqa
                print("  [warn] %s 指数失败: %s" % (v, str(e)[:50]))
        if contracts:
            out["varieties"][v] = rec
            print("  [ok] %s: %d 合约数据" % (v, len(contracts)))
        else:
            print("  [skip] %s: 无合约数据" % v)

    # CZCE: 一次性抓全市场(约120s), 按 品种+code(yymm[1:]) 提取各合约
    if czce_vars:
        print("  [CZCE] 一次性抓取郑商所全市场(约120s)...")
        mkt = ss.fetch_czce_market()
        for v in czce_vars:
            contracts = {}
            for mo in months:
                code = mo[1:]          # '2509' -> '509'(与 get_futures_daily 符号对齐)
                ser = mkt.get(v, {}).get(code)
                if ser:
                    contracts[mo] = ser
            if contracts:
                out["varieties"][v] = {"contracts": contracts}
                print("  [ok] %s(CZCE): %d 合约" % (v, len(contracts)))
            else:
                print("  [skip] %s(CZCE): 全市场未含该品种合约" % v)

    if len(out["varieties"]) < len(existing_varieties):
        # 极端情况: 真实抓取全失败且合并异常, 不覆盖已有缓存
        print("\n[x] 有效品种数少于原有缓存，已保留原有 REAL_CACHE（不写入假数据）。")
        sys.exit(1)

    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    html = open(HTML, "r", encoding="utf-8").read()
    if not CACHE_RE.search(html):
        print("[x] 未在 index.html 找到 REAL_CACHE 占位符")
        sys.exit(1)
    block = "/*__SPREAD_CACHE_START__*/\nconst REAL_CACHE = %s;\n/*__SPREAD_CACHE_END__*/" % payload
    html2 = CACHE_RE.sub(block, html)
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html2)
    # 额外写本地磁盘缓存: 后端实时路径(CZCE)可直接秒级读取真实数据, 避免 120s 全市场抓取
    try:
        os.makedirs(os.path.dirname(ss._BAKED_CACHE_PATH), exist_ok=True)
        with open(ss._BAKED_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        print("  [ok] 已写本地磁盘缓存 %s (后端实时读取真实 CZCE 用)" % os.path.normpath(ss._BAKED_CACHE_PATH))
    except Exception as e:  # noqa
        print("  [warn] 写本地磁盘缓存失败: %s" % str(e)[:60])
    added = len(out["varieties"]) - len(existing_varieties)
    print("\n[ok] 已写入 REAL_CACHE 到 %s（抓取日 %s，共 %d 品种，新增 %d）" %
          (os.path.normpath(HTML), out["cached_at"], len(out["varieties"]), added))
    print("     现在即使关闭后端黑窗口，双击该 HTML 也能显示真实价差快照。")


if __name__ == "__main__":
    main()
