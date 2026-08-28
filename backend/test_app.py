# -*- coding: utf-8 -*-
"""
期库镜/价格预警/牧羊人 后端 接口契约测试 (OFFLINE_MODE 下全部可离线跑)。

运行 (在项目根):
    pytest -q test_app.py

覆盖: 各端点返回结构正确、offline 标志、data 形状、参数边界。
真实抓取路径(OFFLINE_MODE=False)依赖外网+akshare, 此处不测。
"""
import logging

import app as backend


def _client():
    return backend.app.test_client()


def test_index():
    r = _client().get("/api/info")
    assert r.status_code == 200
    j = r.get_json()
    assert "endpoints" in j
    assert set(["/api/futures", "/api/corr_top", "/api/quote", "/api/shepherd"]).issubset(
        set(j["endpoints"]))


def test_cors_header_present():
    # 前端跨源(可能是 file:// 或其他本地端口)调用需 CORS 放行
    r = _client().get("/api/futures?symbol=cu")
    assert r.headers.get("Access-Control-Allow-Origin") is not None


def test_logger_configured():
    # 可观测性: 异常/请求应有日志落盘, 而非静默失败
    assert hasattr(backend, "logger")
    assert logging.getLogger("backend").handlers or logging.root.handlers


def test_futures_single_shape():
    r = _client().get("/api/futures?symbol=cu&exchange=SHFE")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    # 默认真实数据: 有网/有缓存=真实(offline False), 纯沙箱禁网=离线样本(offline True)
    assert j["offline"] in (True, False)
    assert isinstance(j["data"], list) and len(j["data"]) > 0
    assert set(["date", "close", "inventory"]).issubset(j["data"][0].keys())


def test_futures_invalid_mode_400():
    r = _client().get("/api/futures?mode=bogus")
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_futures_invalid_exchange_400():
    r = _client().get("/api/futures?exchange=FOO")
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_futures_bad_date_400():
    # 非法日期格式不再被静默降级, 而是明确 400
    r = _client().get("/api/futures?start=2026/01/01")
    assert r.status_code == 400
    assert r.get_json()["ok"] is False
    # end 早于 start
    r2 = _client().get("/api/futures?start=2026-05-01&end=2026-04-01")
    assert r2.status_code == 400
    assert r2.get_json()["ok"] is False


def test_futures_global_sum():
    r = _client().get("/api/futures?mode=global")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    # 全球合计: 库存 = SHFE+LME+COMEX, 应 > 单个 cu 库存
    single = _client().get("/api/futures?symbol=cu").get_json()
    assert j["data"][-1]["inventory"] > single["data"][-1]["inventory"]


def test_corr_top_default_n():
    r = _client().get("/api/corr_top")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert len(j["top"]) <= 5  # 默认 n=5
    # 按 |r| 降序
    abs_r = [abs(x["corr"]) for x in j["top"]]
    assert abs_r == sorted(abs_r, reverse=True)


def test_corr_top_n_param():
    r = _client().get("/api/corr_top?n=3")
    assert r.status_code == 200
    j = r.get_json()
    assert len(j["top"]) <= 3


def test_corr_top_invalid_n_tolerated():
    # 坏输入(非整数/超大)不再 400, 而是夹紧到安全默认, 前端不因脏参数中断
    r = _client().get("/api/corr_top?n=abc")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    r2 = _client().get("/api/corr_top?n=9999")
    assert r2.status_code == 200
    assert r2.get_json()["ok"] is True


def test_corr_top_bad_date_400():
    r = _client().get("/api/corr_top?start=not-a-date")
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_quote_offline_shape():
    r = _client().get("/api/quote?code=sh600519")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert {"name", "price", "prev", "chg"}.issubset(j.keys())


def test_shepherd_offline_shape():
    r = _client().get("/api/shepherd")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert "temperature" in j and 0 <= j["temperature"] <= 100
    assert "indicators" in j and "thresholds" in j
    # 8 项指标齐全
    assert len(j["indicators"]) == 8


# ───────────────────── 新增端点契约测试 (离线) ─────────────────────
def test_blackswan_no_code():
    r = _client().get("/api/blackswan")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert isinstance(j["events"], list) and len(j["events"]) > 0
    assert isinstance(j["stocks"], list) and len(j["stocks"]) > 0


def test_blackswan_with_code_scan_shape():
    r = _client().get("/api/blackswan?code=600519")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["code"] == "600519"
    scan = j["scan"]
    # 离线扫描必须含: 风险评分 + 四维业绩雷框架
    assert "risk_score" in scan and "risk_level" in scan
    assert "earnings_forecast" in scan
    ef = scan["earnings_forecast"]
    assert {"name", "signals", "prob", "grade", "summary"}.issubset(ef.keys())
    # 四维信号齐全
    assert len(ef["signals"]) == 4


def test_earnings_missing_code_400():
    r = _client().get("/api/earnings")
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_earnings_offline_shape():
    r = _client().get("/api/earnings?code=600519")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert isinstance(j["rows"], list) and len(j["rows"]) > 0
    assert {"year", "eps", "roe", "rev", "profit"}.issubset(j["rows"][0].keys())
    # year 过滤生效
    r2 = _client().get("/api/earnings?code=600519&year=2021")
    assert all(x["year"] == "2021" for x in r2.get_json()["rows"])


def test_earnings_unknown_code_empty():
    r = _client().get("/api/earnings?code=999999")
    assert r.status_code == 200
    assert r.get_json()["rows"] == []


def test_search_invalid_type_400():
    r = _client().get("/api/search?type=foo")
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_search_offline_stock_match():
    r = _client().get("/api/search?q=茅台&type=stock")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert len(j["results"]) > 0
    assert any("茅台" in x["name"] for x in j["results"])


def test_search_no_q_returns_popular():
    r = _client().get("/api/search?type=index")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    # 未传关键词返回热门示例(非空)
    assert len(j["results"]) > 0


def test_search_no_match_returns_empty():
    # 传了关键词但库中无匹配 -> 空结果(而非降级为全量列表), 前端据此提示无结果
    r = _client().get("/api/search?q=zzz_not_exist&type=stock")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["results"] == []


def test_code_teacher_default_kind():
    # 无法识别的代码 -> default 解释, 且文本非空
    r = _client().get("/api/code_teacher?code=x = 1")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert isinstance(j["text"], str) and len(j["text"]) > 0


# ───────────────────── 端点发现 & 数据质量 ─────────────────────
def test_index_lists_all_endpoints():
    r = _client().get("/api/info")
    assert r.status_code == 200
    eps = set(r.get_json()["endpoints"])
    # 全部真实端点(含 health)都应暴露给前端, 供前端自动发现
    assert {
        "/api/health", "/api/futures", "/api/corr_top", "/api/quote", "/api/shepherd",
        "/api/blackswan", "/api/earnings", "/api/search", "/api/etf", "/api/sector",
        "/api/data", "/api/futures_spread", "/api/trading_agents", "/api/code_teacher", "/api/theme",
    }.issubset(eps)


def test_search_stock_no_duplicate_results():
    # 去重后, "茅台" 只应命中一条贵州茅台, 而非样本库重复条目
    r = _client().get("/api/search?q=茅台&type=stock")
    res = r.get_json()["results"]
    maotai = [x for x in res if x["code"] == "600519"]
    assert len(maotai) == 1


# ───────────────────── 存活检查 & 静态数据端点契约测试 ─────────────────────
def test_health_shape():
    r = _client().get("/api/health")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True and j["status"] == "up"
    assert j["endpoints"] >= 10
    # data 目录静态文件清单应非空(后端真实数据源就绪)
    assert isinstance(j["data_files"], list) and len(j["data_files"]) > 0


def test_404_returns_json_not_html():
    # 前端 fetch 错路径须收到 JSON 而非 HTML, 否则 JSON.parse 失败破坏契约
    r = _client().get("/api/does_not_exist")
    assert r.status_code == 404
    assert r.is_json
    assert r.get_json()["ok"] is False


def test_etf_offline_shape():
    r = _client().get("/api/etf")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert isinstance(j["rows"], list) and len(j["rows"]) > 0
    # type 过滤生效
    r2 = _client().get("/api/etf?type=ETF")
    rows2 = r2.get_json()["rows"]
    assert all(x.get("type") == "ETF" for x in rows2)


def test_sector_offline_shape():
    r = _client().get("/api/sector")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert isinstance(j["rows"], list) and len(j["rows"]) > 0
    assert {"name", "chg"}.issubset(j["rows"][0].keys())


def test_data_whitelist_and_404():
    # 白名单内文件可读
    r = _client().get("/api/data?file=etf.json")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    assert "rows" in r.get_json()
    # 白名单外/含路径穿越的文件被拒(防目录穿越/越权读取), 先于存在性检查 -> 400
    r2 = _client().get("/api/data?file=../app.py")
    assert r2.status_code == 400
    assert r2.get_json()["ok"] is False
    # 白名单外(不在允许清单)的文件同样被拒 -> 400
    r3 = _client().get("/api/data?file=missing.json")
    assert r3.status_code == 400


def test_trading_agents_offline_shape():
    r = _client().get("/api/trading_agents?symbol=600519")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["symbol"] == "600519"
    assert "agents" in j and "report" in j


def test_code_teacher_offline_shape():
    # 循环类代码 -> loop 解释
    r = _client().get("/api/code_teacher?code=for i in range(10): pass")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["mode"] == "mom"
    assert isinstance(j["text"], str) and len(j["text"]) > 0
    # mode 非法回落到默认 mom
    r2 = _client().get("/api/code_teacher?code=def f(): pass&mode=bogus")
    assert r2.get_json()["mode"] == "mom"


def test_theme_offline_shape():
    r = _client().get("/api/theme")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert isinstance(j["themes"], (list, dict))


def test_safe_code_sanitizes():
    # 仅保留字母数字和点, 拒绝路径分隔符与空白
    assert backend.safe_code("sh600519") == "sh600519"
    dirty = backend.safe_code(" ../../etc/passwd ")
    assert "/" not in dirty and " " not in dirty
    # 超长截断
    assert len(backend.safe_code("a" * 50)) <= 16


def test_cap_len_truncates():
    assert len(backend.cap_len("x" * 200, 64)) == 64
    assert backend.cap_len(None) == ""


def test_safe_int_clamps_and_falls_back():
    assert backend.safe_int("abc", 5) == 5        # 解析失败回退默认
    assert backend.safe_int("3.5", 0) == 0        # 非整数回退默认
    assert backend.safe_int("99", 1, 1, 50) == 50  # 超上限夹紧
    assert backend.safe_int("-5", 0, 1, 10) == 1   # 超下限夹紧


def test_quote_rejects_malicious_code_without_crash():
    # 注入路径穿越字符不应导致 500 或文件读取
    r = _client().get("/api/quote?code=../../etc/passwd")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert "/" not in j.get("name", "")


def test_search_accepts_html_injection_safely():
    # q 含 HTML/超长不应崩溃
    r = _client().get("/api/search?q=<script>alert(1)</script>")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_futures_events_returns_seeded_sp_events():
    # 时间轴后端数据源: SHFE:sp 应返回内置研究样本(11 条)
    r = _client().get("/api/futures_events?exchange=SHFE&symbol=sp")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["key"] == "SHFE:sp"
    assert isinstance(j["events"], list)
    assert len(j["events"]) >= 10
    # 事件结构完整
    ev = j["events"][0]
    assert all(k in ev for k in ("date", "type", "tag", "title", "desc"))


def test_futures_events_unknown_symbol_returns_empty():
    r = _client().get("/api/futures_events?exchange=FOO&symbol=bar")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["events"] == []


def test_futures_events_sanitizes_input_without_crash():
    # 注入不应崩溃且 key 被清洗
    r = _client().get("/api/futures_events?exchange=<b>&symbol=../x")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert "../" not in j["key"]


def test_llm_empty_body_returns_400():
    r = _client().post("/api/llm", json={})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_llm_returns_json_not_html():
    # 沙箱无 Ollama/网络 -> 期望 502 JSON; 有本地模型 -> 200 JSON。
    # 两种情况下都必须是 JSON(绝不 HTML), 且字段结构正确。
    r = _client().post("/api/llm", json={
        "system": "你是测试助手",
        "user": "用一句话自我介绍",
    })
    assert r.status_code in (200, 502)
    j = r.get_json()
    assert j["ok"] is not None
    if r.status_code == 200:
        assert isinstance(j["content"], str) and len(j["content"]) > 0


def test_llm_endpoint_registered_in_index():
    r = _client().get("/api/info")
    assert "/api/llm" in r.get_json()["endpoints"]


# ───────────────────── 期货价差 /api/futures_spread ─────────────────────
def test_futures_spread_default_shape():
    r = _client().get("/api/futures_spread?variety=sp&monthA=2505&monthB=2509")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["variety"] == "sp"
    assert j["monthA"] == "2505"
    assert j["monthB"] == "2509"
    assert isinstance(j["data"], list) and len(j["data"]) > 30
    pt = j["data"][0]
    assert set(["date", "priceA", "priceB", "spread", "y"]).issubset(pt.keys())
    assert isinstance(j["corr"], float)


def test_futures_spread_stock_index_uses_index_y():
    # 股指期货应自动映射到对应现货指数
    r = _client().get("/api/futures_spread?variety=IF&monthA=2506&monthB=2509")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ytype"] == "index"
    assert "沪深300" in j["y_label"]
    # Y 值应接近沪深 300 点位(样本约 3900 附近)，而非期货价格
    y_values = [x["y"] for x in j["data"]]
    assert 3000 < sum(y_values) / len(y_values) < 5000


def test_futures_spread_invalid_month_400():
    r = _client().get("/api/futures_spread?variety=sp&monthA=2505&monthB=2505")
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_futures_spread_sanitizes_input():
    # 注入字符应被 safe_code 清洗，接口不崩溃
    r = _client().get("/api/futures_spread?variety=<b>&monthA=../x&monthB=2509")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert "<" not in j["variety"] and "/" not in j["monthA"]


def test_data_status_reports_freshness_per_symbol():
    # 数据新鲜度总览: 每个缓存应报出最新数据日期与距今天数
    r = _client().get("/api/data_status")
    assert r.status_code == 200
    j = r.get_json()
    assert j["ok"] is True
    assert j["count"] > 0, "应扫描到期货缓存文件"
    assert isinstance(j["items"], list)
    sp = [i for i in j["items"] if i["exchange"] == "SHFE" and i["symbol"].upper() == "SP"]
    assert sp, "SHFE SP 缓存应存在"
    item = sp[0]
    assert item["records"] > 0
    assert item["latest_date"], "应能取到最新数据日期"
    assert item["age_days"] is not None and item["age_days"] >= 0
    assert j["stale_count"] >= 0
    if j["with_data"]:
        assert j["newest_age_days"] <= j["oldest_age_days"]


def test_data_status_endpoint_registered():
    r = _client().get("/api/info")
    assert r.status_code == 200
    assert "/api/data_status" in r.get_json()["endpoints"]


def test_health_reports_refresh_diagnostics():
    # 刷新调度器应暴露可诊断字段(失败明细/下次刷新/轮次), 便于部署后排查
    j = _client().get("/api/health").get_json()
    ar = j["auto_refresh"]
    for k in ("running", "last_run", "last_ok", "last_fail", "cycle_sec",
              "runs", "consecutive_fails", "next_run", "last_errors", "degraded"):
        assert k in ar, "缺少刷新诊断字段: " + k
    assert isinstance(ar["last_errors"], list)
    assert isinstance(ar["degraded"], list)
