# -*- coding: utf-8 -*-
"""用 akshare futures_inventory_em（东方财富统一期货库存口径）把真实库存
烘焙进各品种缓存 futures_<EXCH>_<SYM>.json 的 inventory_total 字段。
覆盖全 6 品种 + 沪铜(CU，用户截图品种)，日期对齐最近 72 天真实库存。
"""
import json, os, sys, warnings
warnings.filterwarnings("ignore")
import akshare as ak

DATA = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA, exist_ok=True)

# 品种 -> (中文名, 交易所, 代码)  —— 仅用于兼容旧调用，main() 已改用 MASTER 全量列表
VARIETIES = {
    "SP": ("纸浆", "SHFE", "sp"),
    "CU": ("沪铜", "SHFE", "cu"),
    "FG": ("玻璃", "CZCE", "FG"),
    "SA": ("纯碱", "CZCE", "SA"),
    "SR": ("白糖", "CZCE", "SR"),
    "JD": ("鸡蛋", "DCE", "JD"),
    "EG": ("乙二醇", "DCE", "EG"),
}

# 交易所+代码 -> 东方财富中文名称（用于 futures_inventory_em）
# 名称必须严格匹配 akshare futures_inventory_em 的合法白名单（见 _probe_inv.py 抓取的完整表）
CN_NAMES = {
    ("SHFE", "CU"): "沪铜", ("SHFE", "AL"): "沪铝", ("SHFE", "ZN"): "沪锌",
    ("SHFE", "PB"): "沪铅", ("SHFE", "NI"): "镍", ("SHFE", "SN"): "锡",
    ("SHFE", "AU"): "沪金", ("SHFE", "AG"): "沪银", ("SHFE", "RB"): "螺纹钢",
    ("SHFE", "HC"): "热卷", ("SHFE", "SS"): "不锈钢", ("SHFE", "AO"): "氧化铝",
    ("SHFE", "RU"): "橡胶", ("SHFE", "NR"): "20号胶", ("SHFE", "BU"): "沥青",
    ("SHFE", "FU"): "燃油", ("SHFE", "BC"): "国际铜",
    ("DCE", "A"): "豆一", ("DCE", "M"): "豆粕", ("DCE", "Y"): "豆油",
    ("DCE", "P"): "棕榈", ("DCE", "C"): "玉米", ("DCE", "CS"): "玉米淀粉",
    ("DCE", "PP"): "聚丙烯", ("DCE", "V"): "PVC", ("DCE", "L"): "塑料",
    ("DCE", "J"): "焦炭", ("DCE", "JM"): "焦煤", ("DCE", "I"): "铁矿石",
    ("DCE", "JD"): "鸡蛋", ("DCE", "EG"): "乙二醇", ("DCE", "EB"): "苯乙烯",
    ("DCE", "PG"): "液化石油气", ("DCE", "LH"): "生猪",
    ("SHFE", "SP"): "纸浆",
    ("DCE", "RR"): "粳米", ("INE", "NR"): "20号胶",
    ("CZCE", "CF"): "郑棉", ("CZCE", "SR"): "白糖", ("CZCE", "RM"): "菜粕",
    ("CZCE", "TA"): "PTA", ("CZCE", "MA"): "甲醇", ("CZCE", "FG"): "玻璃",
    ("CZCE", "OI"): "菜油", ("CZCE", "UR"): "尿素", ("CZCE", "SA"): "纯碱",
    ("CZCE", "PF"): "短纤", ("CZCE", "PK"): "花生", ("CZCE", "AP"): "苹果",
    ("CZCE", "CJ"): "红枣", ("CZCE", "PX"): "对二甲苯", ("CZCE", "SH"): "烧碱",
    ("INE", "LU"): "低硫燃料油", ("INE", "NR"): "20号胶",
    # 原油(INE sc)：东方财富 inventory_em 白名单无此口径，无库存数据，前端诚实走空状态
}

# 与前端 SYMBOLS 下拉框对齐的全量国内商品期货列表（排除 CFFEX 股指/国债、LME/COMEX 境外）
# 格式：(exchange, code, 中文名)
MASTER = [
    ("SHFE", "cu", "沪铜"), ("SHFE", "al", "沪铝"), ("SHFE", "zn", "沪锌"),
    ("SHFE", "pb", "沪铅"), ("SHFE", "ni", "镍"), ("SHFE", "sn", "锡"),
    ("SHFE", "au", "沪金"), ("SHFE", "ag", "沪银"), ("SHFE", "rb", "螺纹钢"),
    ("SHFE", "hc", "热卷"), ("SHFE", "ss", "不锈钢"), ("SHFE", "ao", "氧化铝"),
    ("SHFE", "ru", "橡胶"), ("SHFE", "nr", "20号胶"), ("SHFE", "bu", "沥青"),
    ("SHFE", "fu", "燃油"), ("SHFE", "bc", "国际铜"),
    ("DCE", "a", "豆一"), ("DCE", "m", "豆粕"), ("DCE", "y", "豆油"),
    ("DCE", "p", "棕榈"), ("DCE", "c", "玉米"), ("DCE", "cs", "玉米淀粉"),
    ("DCE", "pp", "聚丙烯"), ("DCE", "v", "PVC"), ("DCE", "l", "塑料"),
    ("DCE", "j", "焦炭"), ("DCE", "jm", "焦煤"), ("DCE", "i", "铁矿石"),
    ("DCE", "jd", "鸡蛋"), ("DCE", "eg", "乙二醇"), ("DCE", "eb", "苯乙烯"),
    ("DCE", "pg", "液化石油气"), ("DCE", "lh", "生猪"),
    ("SHFE", "sp", "纸浆"),
    ("DCE", "rr", "粳米"), ("INE", "nr", "20号胶"),
    ("CZCE", "CF", "郑棉"), ("CZCE", "SR", "白糖"), ("CZCE", "RM", "菜粕"),
    ("CZCE", "TA", "PTA"), ("CZCE", "MA", "甲醇"), ("CZCE", "FG", "玻璃"),
    ("CZCE", "OI", "菜油"), ("CZCE", "UR", "尿素"), ("CZCE", "SA", "纯碱"),
    ("CZCE", "PF", "短纤"), ("CZCE", "PK", "花生"), ("CZCE", "AP", "苹果"),
    ("CZCE", "CJ", "红枣"), ("CZCE", "PX", "对二甲苯"), ("CZCE", "SH", "烧碱"),
    ("INE", "lu", "低硫燃料油"), ("INE", "nr", "20号胶"),
    ("INE", "sc", "原油"),
]


def load_cache(exch, sym):
    path = os.path.join(DATA, "futures_%s_%s.json" % (exch, sym))
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else d.get("rows", d.get("data", []))
    return None


def build_from_daily(code):
    """缓存不存在时，用新浪日线构造基础结构（只取最近约 500 行，避免前端过慢）。"""
    import akshare as ak2
    df = ak2.futures_zh_daily_sina(symbol=code + "0")
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "date": str(r["date"])[:10],
            "close": float(r["close"]) if r.get("close") is not None else None,
            "inventory": None, "inventory_total": None,
            "inventory_circ": None, "inventory_warehouse": None,
            "inventory_bonded": None,
        })
    rows = rows[-500:]  # 截断到最近 500 行
    return rows


def refresh_one(exchange, symbol, verbose=True):
    """刷新单个品种的本地缓存：行情优先用本地缓存，库存用 akshare futures_inventory_em 真抓。
    返回 {"ok":bool, "rows":int, "filled":int, "last_inv":float|None, "msg":str}。
    """
    exchange = exchange.upper()
    symbol = symbol.upper()
    # 原油(IN E sc)：无交易所仓单库存口径，改用美国EIA周度原油库存变动(百万桶)作为真实库存信号
    if exchange == "INE" and symbol == "SC":
        return refresh_crude(exchange, symbol, verbose)
    cn = CN_NAMES.get((exchange, symbol))
    if not cn:
        # 尝试 VARIETIES 兜底
        info = VARIETIES.get(symbol)
        if info:
            cn = info[0]
        else:
            return {"ok": False, "rows": 0, "filled": 0, "last_inv": None,
                    "msg": "未找到 %s/%s 的中文名称映射，无法调用 inventory_em" % (exchange, symbol)}

    rows = load_cache(exchange, symbol)
    if not rows:
        # 取行情代码：国内主力连续 = symbol.lower() + "0"
        code = symbol.lower() if exchange in ("SHFE", "DCE", "CZCE", "INE") else symbol
        try:
            rows = build_from_daily(code)
            if verbose:
                print("[%s/%s] 缓存缺失，已从新浪日线重建 %d 行" % (exchange, symbol, len(rows)))
        except Exception as e:
            return {"ok": False, "rows": 0, "filled": 0, "last_inv": None,
                    "msg": "缓存缺失且日线重建失败: %s" % e}

    # 拉库存
    try:
        inv_df = ak.futures_inventory_em(symbol=cn)
    except Exception as e:
        return {"ok": False, "rows": len(rows), "filled": 0, "last_inv": None,
                "msg": "inventory_em 抓取失败: %s" % e}
    if inv_df is None or len(inv_df) == 0:
        return {"ok": False, "rows": len(rows), "filled": 0, "last_inv": None,
                "msg": "inventory_em 返回为空"}

    # 建 date -> inv 映射
    inv_map = {}
    for _, r in inv_df.iterrows():
        dt = str(r["日期"])[:10]
        val = r.get("库存")
        try:
            val = float(val) if val is not None else None
        except Exception:
            val = None
        inv_map[dt] = val

    filled = 0
    for row in rows:
        row["inventory"] = None
        row["inventory_total"] = None
        row["inventory_circ"] = None
        row["inventory_warehouse"] = None
        row["inventory_bonded"] = None
    for row in rows:
        dt = row.get("date")
        if dt in inv_map and inv_map[dt] is not None:
            row["inventory_total"] = inv_map[dt]
            row["inventory"] = inv_map[dt]
            row["inventory_warehouse"] = inv_map[dt]
            filled += 1

    out_path = os.path.join(DATA, "futures_%s_%s.json" % (exchange, symbol))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=0)
    inv_vals = [r["inventory_total"] for r in rows if r.get("inventory_total") is not None]
    last_inv = inv_vals[-1] if inv_vals else None
    if verbose:
        print("[%s/%s] 写回 %s, 填库存 %d 行, 库存区间 %.0f~%.0f" % (
            exchange, symbol, out_path, filled,
            inv_vals[0] if inv_vals else 0, inv_vals[-1] if inv_vals else 0))
    return {"ok": True, "rows": len(rows), "filled": filled, "last_inv": last_inv,
            "msg": "已刷新 %d 行数据，其中 %d 行有库存" % (len(rows), filled)}


def refresh_crude(exchange, symbol, verbose=True):
    """原油(sc) 无交易所仓单库存口径；接入美国EIA周度原油库存变动(百万桶)作为真实库存信号。
    行情用新浪日线 sc0；库存用 akshare macro_usa_eia_crude_rate（每周三发布，单位百万桶，1982 至今）。
    """
    from bisect import bisect_right
    code = "sc"
    rows = load_cache(exchange, symbol)
    if not rows:
        try:
            rows = build_from_daily(code)
            if verbose:
                print("[%s/%s] 缓存缺失，已从新浪日线重建 %d 行" % (exchange, symbol, len(rows)))
        except Exception as e:
            return {"ok": False, "rows": 0, "filled": 0, "last_inv": None,
                    "msg": "日线重建失败: %s" % e}
    # EIA 周度原油库存变动（今值，百万桶）
    try:
        df = ak.macro_usa_eia_crude_rate()
    except Exception as e:
        return {"ok": False, "rows": len(rows), "filled": 0, "last_inv": None,
                "msg": "EIA 抓取失败: %s" % e}
    eia = []
    for _, r in df.iterrows():
        dt = str(r["日期"])[:10]
        val = r.get("今值")
        try:
            val = float(val) if (val is not None and not (isinstance(val, float) and val != val)) else None
        except Exception:
            val = None
        if val is not None:
            eia.append((dt, val))
    eia.sort(key=lambda x: x[0])
    dates = [e[0] for e in eia]
    last_eia_date = dates[-1] if dates else None
    filled = 0
    for row in rows:
        d = row.get("date")
        # 取 <= 该行日期最近的 EIA 值（日线按周对齐，形成阶梯）；
        # 超出 EIA 数据覆盖期(截至 last_eia_date)的日线行保持 null，绝不向前外推，避免伪造"当前"库存
        idx = bisect_right(dates, d) - 1
        if idx >= 0 and d <= last_eia_date:
            row["eia_crude_change"] = eia[idx][1]
            filled += 1
        else:
            row["eia_crude_change"] = None
        # 清掉其它仓单口径字段（原油无此口径）
        row["inventory"] = None
        row["inventory_total"] = None
        row["inventory_circ"] = None
        row["inventory_warehouse"] = None
        row["inventory_bonded"] = None
    out_path = os.path.join(DATA, "futures_%s_%s.json" % (exchange, symbol))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=0)
    vals = [r["eia_crude_change"] for r in rows if r.get("eia_crude_change") is not None]
    last_inv = vals[-1] if vals else None
    last_date = dates[-1] if dates else None
    if verbose:
        print("[%s/%s] 写回 %s, EIA库存变动填 %d 行, 最新变动 %.1f 百万桶 (截至 %s)" % (
            exchange, symbol, out_path, filled, last_inv if last_inv else 0, last_date))
    return {"ok": True, "rows": len(rows), "filled": filled, "last_inv": last_inv,
            "msg": "原油已接入美国EIA周度原油库存变动(百万桶), 截至 %s" % last_date}


def main():
    ok_list, fail_list = [], []
    for exch, code, cn in MASTER:
        res = refresh_one(exch, code, verbose=True)
        if res["ok"]:
            ok_list.append((exch, code, res["rows"], res["filled"], res["last_inv"]))
        else:
            fail_list.append((exch, code, cn, res["msg"]))
            print("[%s/%s %s] 刷新失败: %s" % (exch, code, cn, res["msg"]))
    print("\n=== SUMMARY（成功 %d / 失败 %d）===" % (len(ok_list), len(fail_list)))
    for s in ok_list:
        print("  OK   %s/%s  rows=%-4d filled=%-4d last_inv=%s" % s)
    if fail_list:
        print("  失败品种：")
        for f in fail_list:
            print("    - %s/%s (%s): %s" % f)


if __name__ == "__main__":
    main()
