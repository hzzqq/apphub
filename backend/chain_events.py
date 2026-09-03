# -*- coding: utf-8 -*-
"""
产业链事件归因 · 真实数据来源（akshare）
====================================
替代（在线时）futures_chain.py 中手工撰写的 CHAIN_EVENTS 叙事知识库：
用 akshare 实时抓取真实事件，按品种关键词筛选，作为「事件 / 阶段驱动归因」的实据。

数据源（均在沙箱/本机验证可用）：
  - 金属品种：ak.futures_news_shmet(symbol=中文名)  → 符号级期货新闻（上海金属网）
  - 通用：ak.news_economic_baidu()                  → 宏观事件日历（真实日期+公布/预期/前值）
  - 通用：ak.stock_news_main_cx()                   → 财经快讯（tag/summary/url）

离线（OFFLINE_MODE=True）或 LIVE_EVENTS 关闭或抓取失败时，返回 []，
由 futures_chain.render_report 回退到 CHAIN_EVENTS 知识库卡。

关键词筛选：每个品种预置一组产业关键词，只保留命中关键词的事件，保证"相关性"。
"""
import os
import socket

OFFLINE_MODE = os.environ.get("OFFLINE_MODE", "True").strip().lower() in ("1", "true", "yes", "on")
LIVE_EVENTS = os.environ.get("LIVE_EVENTS", "1").strip().lower() in ("1", "true", "yes", "on")

# 金属品种 → SHMET 中文名（有符号级新闻）
METAL_SHMET = {
    "CU": "铜", "AL": "铝", "ZN": "锌", "PB": "铅", "NI": "镍", "SN": "锡",
    "AU": "黄金", "AG": "白银", "RB": "螺纹", "HC": "热卷", "RU": "橡胶",
    "BU": "沥青", "I": "铁矿石",
}

# 品种 → 产业关键词（用于筛选宏观日历 / 财经快讯，只留相关事件）
# 分两层：① 品种精确词（直接命中）；② 宏观驱动词（房地产/光伏/农产品/CPI/人民币等，本就是真实产业链驱动）
KEYWORDS = {
    "SP": ["纸浆", "木浆", "造纸", "木片", "烧碱", "人民币", "汇率", "浆价", "浆", "纸", "包装", "木材"],
    "FG": ["玻璃", "房地产", "地产", "楼市", "竣工", "建筑", "基建", "开工", "施工", "建材", "光伏", "纯碱"],
    "SA": ["纯碱", "光伏", "新能源", "多晶硅", "碳酸锂", "玻璃", "化工", "碱"],
    "JD": ["鸡蛋", "禽", "养殖", "饲料", "猪", "玉米", "豆粕", "农产品", "通胀", "CPI", "食品", "居民消费"],
    "SR": ["白糖", "糖", "巴西", "印度", "原糖", "甘蔗", "汇率", "糖浆", "农产品", "CPI"],
    "EG": ["乙二醇", "聚酯", "PTA", "化工", "原油", "乙烯", "煤", "纺织", "油价"],
    # 顺带覆盖其它常见金属/农产品，便于未来扩展
    "CU": ["铜", "电网", "新能源", "房地产"], "AL": ["铝", "电解铝"], "ZN": ["锌"],
    "AU": ["黄金", "央行", "避险", "美元"], "AG": ["白银"], "RB": ["螺纹", "房地产", "钢", "基建"],
    "RU": ["橡胶", "轮胎", "汽车"], "BU": ["沥青", "基建", "房地产"], "I": ["铁矿", "钢铁", "房地产"],
    "M": ["豆粕", "大豆", "美豆", "农产品"], "Y": ["豆油", "农产品"], "C": ["玉米", "农产品"],
    "CF": ["棉花", "农产品"], "TA": ["PTA", "聚酯", "光伏"], "MA": ["甲醇", "化工"],
    "PP": ["聚丙烯", "化工"], "L": ["塑料", "聚乙烯", "化工"],
}


def _with_timeout(fn, *args, **kwargs):
    """给 akshare 网络调用套一层超时，避免卡死报告生成。"""
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(12)
    try:
        return fn(*args, **kwargs)
    finally:
        socket.setdefaulttimeout(old)


def _fetch_shmet(name):
    import akshare as ak
    df = ak.futures_news_shmet(symbol=name)
    out = []
    for _, row in df.iterrows():
        t = str(row.get("发布时间", ""))[:10]
        c = str(row.get("内容", "")).strip()
        if c:
            out.append({"date": t, "text": c[:180], "source": "上海金属网 SHMET", "url": ""})
    return out


def _fetch_macro(kws):
    import akshare as ak
    df = ak.news_economic_baidu()
    out = []
    for _, row in df.iterrows():
        ev = str(row.get("事件", ""))
        if any(k in ev for k in kws):
            txt = "%s | 公布:%s 预期:%s 前值:%s" % (
                ev, row.get("公布", ""), row.get("预期", ""), row.get("前值", ""))
            out.append({"date": "%s %s" % (row.get("日期", ""), row.get("时间", "")),
                        "text": txt, "source": "百度宏观日历", "url": ""})
    return out


def _fetch_mainnews(kws):
    import akshare as ak
    df = ak.stock_news_main_cx()
    out = []
    for _, row in df.iterrows():
        s = str(row.get("summary", "")).strip()
        if not s:
            continue
        if any(k in s for k in kws):
            out.append({"date": str(row.get("date", "")), "text": s[:160],
                        "source": "财经快讯(%s)" % row.get("tag", ""),
                        "url": str(row.get("url", ""))})
    return out


def fetch_real_events(symbol, exchange=None, topn=18):
    """抓取该品种的真实事件列表。

    返回 [{"date","text","source","url"}]。无任何真实来源时返回 []（触发知识库回退）。
    """
    if OFFLINE_MODE or not LIVE_EVENTS:
        return []
    sym = (symbol or "").upper()
    kws = KEYWORDS.get(sym, [])
    events = []

    # 1) 金属走符号级 SHMET 新闻（不依赖关键词，全量取近期）
    nm = METAL_SHMET.get(sym)
    if nm:
        try:
            events += _fetch_shmet(nm)
        except Exception:
            pass

    # 2) 有产业关键词则筛选宏观日历 + 财经快讯
    if kws:
        try:
            events += _fetch_macro(kws)
        except Exception:
            pass
        try:
            events += _fetch_mainnews(kws)
        except Exception:
            pass

    # 去重（按文本前 30 字）
    seen, uniq = set(), []
    for e in events:
        key = e["text"][:30]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq[:topn]


if __name__ == "__main__":
    for s in ["SP", "FG", "SA", "JD", "SR", "EG", "CU"]:
        ev = fetch_real_events(s)
        print("%-3s real_events=%d" % (s, len(ev)))
        for e in ev[:2]:
            print("   ", e["date"], e["source"], e["text"][:50])
