# -*- coding: utf-8 -*-
"""诊断：遍历所有国内商品期货品种，实测 akshare futures_inventory_em 能否拿到真实库存。
输出每个品种的：成功行数 / 空 / 异常（异常信息截断）。
结论用于决定哪些品种需要烘焙库存、哪些品种确实无库存（前端诚实走空状态）。
"""
import warnings
warnings.filterwarnings("ignore")
import akshare as ak

# (交易所, 代码) -> 东方财富中文名
PROBE = {
    ("SHFE","cu"):"沪铜", ("SHFE","al"):"沪铝", ("SHFE","zn"):"沪锌",
    ("SHFE","pb"):"沪铅", ("SHFE","ni"):"沪镍", ("SHFE","sn"):"沪锡",
    ("SHFE","au"):"沪金", ("SHFE","ag"):"沪银", ("SHFE","rb"):"螺纹钢",
    ("SHFE","hc"):"热轧卷板", ("SHFE","ss"):"不锈钢", ("SHFE","ao"):"氧化铝",
    ("SHFE","ru"):"天然橡胶", ("SHFE","nr"):"20号胶", ("SHFE","bu"):"沥青",
    ("SHFE","fu"):"燃料油", ("SHFE","bc"):"国际铜",
    ("DCE","a"):"豆一", ("DCE","m"):"豆粕", ("DCE","y"):"豆油",
    ("DCE","p"):"棕榈油", ("DCE","c"):"玉米", ("DCE","cs"):"玉米淀粉",
    ("DCE","pp"):"聚丙烯", ("DCE","v"):"PVC", ("DCE","l"):"聚乙烯",
    ("DCE","j"):"焦炭", ("DCE","jm"):"焦煤", ("DCE","i"):"铁矿石",
    ("DCE","jd"):"鸡蛋", ("DCE","eg"):"乙二醇", ("DCE","eb"):"苯乙烯",
    ("DCE","pg"):"液化石油气", ("DCE","lh"):"生猪", ("DCE","sp"):"纸浆",
    ("DCE","rr"):"粳米",
    ("CZCE","CF"):"棉花", ("CZCE","SR"):"白糖", ("CZCE","RM"):"菜粕",
    ("CZCE","TA"):"PTA", ("CZCE","MA"):"甲醇", ("CZCE","FG"):"玻璃",
    ("CZCE","OI"):"菜油", ("CZCE","UR"):"尿素", ("CZCE","SA"):"纯碱",
    ("CZCE","PF"):"短纤", ("CZCE","PK"):"花生", ("CZCE","AP"):"苹果",
    ("CZCE","CJ"):"红枣", ("CZCE","PX"):"对二甲苯", ("CZCE","SH"):"烧碱",
    ("INE","sc"):"原油", ("INE","lu"):"低硫燃料油", ("INE","nr"):"20号胶",
}

# 这些本身无实物库存，预期失败（用于区分"真无数据"与"接口异常"）
NO_INV_EXPECT = set()

print("=== 实测 futures_inventory_em（每只最多 ~3s） ===")
ok, empty, err = [], [], []
for (ex, code), cn in sorted(PROBE.items()):
    try:
        df = ak.futures_inventory_em(symbol=cn)
        if df is None or len(df) == 0:
            empty.append((ex, code, cn, "空"))
            print("  EMPTY  %-5s %-4s %-6s" % (ex, code, cn))
        else:
            # 找库存列
            cols = list(df.columns)
            inv_col = next((c for c in cols if "库存" in str(c)), None)
            n = len(df)
            val = df.iloc[-1].get(inv_col) if inv_col else None
            ok.append((ex, code, cn, n, val))
            print("  OK     %-5s %-4s %-6s rows=%-3d last=%s" % (ex, code, cn, n, val))
    except Exception as e:
        msg = repr(e)[:80]
        err.append((ex, code, cn, msg))
        print("  ERROR  %-5s %-4s %-6s %s" % (ex, code, cn, msg))

print("\n=== 汇总 ===")
print("成功拿库存: %d" % len(ok))
print("返回空:     %d -> %s" % (len(empty), [(e[0],e[1]) for e in empty]))
print("异常失败:   %d -> %s" % (len(err), [(e[0],e[1],e[3]) for e in err]))
