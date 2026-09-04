# -*- coding: utf-8 -*-
"""
期库镜 / 价格预警 统一后端 (Flask)
==================================
为前端微型 App (futures-inventory/index.html, price-alert/index.html) 提供真实数据。
行情源模仿 StockSignal: 新浪 hq.sinajs.cn + akshare 多源 fallback。
期货库存: SHFE(上期所仓单) / DCE+CZCE(大商所郑商所) / COMEX / LME(外盘)。
相关性: 皮尔逊系数, 全品种遍历算 Top N。

运行 (在本机/有网环境):
    cd E:/project/app/backend
    python app.py
    # 默认 http://127.0.0.1:8787
前端「真实数据接口」填: http://127.0.0.1:8787

数据策略(期库镜 /api/futures 默认真实数据):
  1) 优先读取本地真实缓存 backend/data/futures_<exch>_<symbol>.json
     (由 fetch_real_futures.py 在有网机器上生成, 一次生成长期使用);
  2) 无缓存则尝试 akshare 真抓(带超时保护);
  3) 两者都失败才回退离线准真实样本, 保证前端永远拿到非空数据、绝不 500。
  即: 有网/有缓存 = 真实数据; 纯沙箱禁网 = 离线样本。OFFLINE_MODE 仅影响价格预警等其它端点。
"""
import json
import math
import os
import threading
import urllib.request as _ureq
import urllib.error as _uerr
import hashlib as _hl
import time as _t
import re
import glob

# 期货跨期价差真实来源 (与 build_spread_cache.py 共用); 失败由上层回退样本
try:
    from spread_source import compute_spread_series as _real_spread_series
    _HAS_SPREAD_SRC = True
except Exception:  # noqa
    _HAS_SPREAD_SRC = False
# 期货库存真实刷新入口 (东方财富 futures_inventory_em)
try:
    import _bake_inv_em
    _HAS_BAKE_INV = True
except Exception:  # noqa
    _HAS_BAKE_INV = False
# 期货产业链联动分析引擎 (futures-chain 微应用后端)
try:
    import futures_chain
    _HAS_FUTURES_CHAIN = True
except Exception:  # noqa
    _HAS_FUTURES_CHAIN = False
# 行程规划模块 (itinerary 微应用后端；源自 map 项目，可代理其 /api/generate)
try:
    import itinerary
    _HAS_ITINERARY = True
except Exception:  # noqa
    _HAS_ITINERARY = False
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory, abort
from flask_cors import CORS
import logging

# 本地真实缓存目录 (fetch_real_futures.py 产出): backend/data/futures_<exch>_<symbol>.json
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
# 静态数据进程内缓存 {fname: (mtime, data)}，文件不变则不重复读盘+json.load
_static_cache = {}

# 前端根目录 (app 项目根, 即 backend/ 的上一级): 部署时后端顺带托管前端单文件 App
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 静态托管安全边界: 禁止暴露后端源码 / 版本库 / 构建脚本 / 隐藏文件
# 根级「非应用目录」一律不托管: 它们没有 index.html, 却可能含内部脚本与部署配置
#   test/      前端单测源码(含断言细节)
#   deploy/    服务器部署脚本与 systemd 单元(含主机路径)
#   Artifacts/ 开发过程文档
_DENY_PREFIXES = ("backend/", ".git/", ".workbuddy/", "node_modules/",
                  "test/", "deploy/", "Artifacts/")
_DENY_FILES = {
    "verify_all.py", "_zip_release.py", "_build_release.py",
    "refresh_data.bat", "start.bat", "start.sh", "backend.log", ".gitignore",
    "package_for_share.py", "xss_patch.py",
}
# 根级(不含子目录)的脚本/日志/临时文件一律拒绝: 以后新增根级 .py/.bat/.sh 自动不暴露,
# 无需逐个补进 _DENY_FILES
_DENY_ROOT_SUFFIXES = (".py", ".bat", ".sh", ".log", ".tmp.js", ".pyc")

app = Flask(__name__, static_folder=None)
# 允许跨域: 前端 HTML 可能从 file:// 或其他本地端口打开, 不放开 CORS 则浏览器会拦截真实数据请求
CORS(app)

# 可观测性: 记录每次请求与真实抓取异常, 便于排查(文件已纳入 .gitignore)
# 直接挂到 backend logger, 避免被 pytest 等已配置的 root logging 跳过
logger = logging.getLogger("backend")
if not logger.handlers:
    _fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    _fh = logging.FileHandler("backend.log", encoding="utf-8")
    _fh.setFormatter(_fmt)
    _sh = logging.StreamHandler()
    _sh.setFormatter(_fmt)
    logger.addHandler(_fh)
    logger.addHandler(_sh)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 防止在 pytest 等环境下重复输出


@app.before_request
def _log_request():
    logger.info("-> %s %s", request.method, request.path)


# 统一 JSON 错误响应: 前端(多为 fetch)调用错路径/错方法时拿到结构化错误,
# 而非 Flask 默认的 HTML, 否则会破坏纯 JSON 契约(前端 JSON.parse 失败)。
@app.errorhandler(404)
def _handle_404(_e):
    return jsonify({"ok": False, "error": "not found: %s" % request.path}), 404


@app.errorhandler(405)
def _handle_405(_e):
    return jsonify({"ok": False, "error": "method not allowed: %s %s"
                    % (request.method, request.path)}), 405

# ===== 离线模式: True=用内置准真实样本, False=有网即真抓 akshare =====
# 默认 True 保持沙箱安全; 用户有网机器通过 start.bat 注入 OFFLINE_MODE=False
# 即默认抓取真实数据, 抓取失败自动回退样本 (永不空/500)。
OFFLINE_MODE = os.environ.get("OFFLINE_MODE", "True").strip().lower() in ("1", "true", "yes", "on")

# ----------------------------------------------------------------------------
# 输入校验: 所有来自前端的 query 参数统一收口, 防注入/路径穿越/超长 DoS
# ----------------------------------------------------------------------------
import re as _re

def safe_code(raw, maxlen=16):
    """股票/期货代码: 仅保留字母数字与小数点(如 sh600519 / cu.main),
    拒绝路径分隔符与空白, 并截断超长。空值返回空串。"""
    s = (raw or "").strip()
    s = _re.sub(r"[^0-9A-Za-z.]", "", s)
    return s[:maxlen]

def cap_len(raw, maxlen=64):
    """任意文本参数: 去首尾空白并截断, 防超长查询/日志膨胀。"""
    return (raw or "").strip()[:maxlen]

def safe_int(raw, default=0, lo=None, hi=None):
    """整数参数: 解析失败回退默认值, 并夹紧到 [lo, hi] (防坏输入触发 500)。"""
    try:
        v = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


# ----------------------------------------------------------------------------
# 统一 LLM 网关 (真实大模型接入点)
# ----------------------------------------------------------------------------
# 设计原则(最稳 / 最省 / 可复用, 全项目 App 共用):
#   - 浏览器 App 永远不直接调 LLM(会暴露 Key 且被 CORS 拦), 一律走本端点;
#   - 本地优先: 默认连 Ollama(http://localhost:11434/v1), 免费、断网可用、零密钥;
#   - 云端可选: 设 LLM_PROVIDER=deepseek/openai + LLM_API_KEY 即切真实云端;
#   - 服务端缓存: 相同 (model+messages) 命中即返回, 省 token/省时(效率核心);
#   - SSE 流式: stream=true 时逐字返回, 前端体验更快;
#   - 失败不崩: LLM 不可达返回 502 JSON, 前端自动降级本地演示。
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama").lower()
LLM_BASE_URL = (os.environ.get("LLM_BASE_URL") or "").strip()
LLM_API_KEY = (os.environ.get("LLM_API_KEY") or "").strip()
LLM_MODEL = (os.environ.get("LLM_MODEL") or "qwen2.5:3b").strip()

_LLM_CACHE = {}
_LLM_CACHE_TTL = int(os.environ.get("LLM_CACHE_TTL", "3600"))


def _llm_endpoint():
    if LLM_PROVIDER == "deepseek":
        return "https://api.deepseek.com/v1/chat/completions", LLM_API_KEY or os.environ.get("DEEPSEEK_API_KEY", "")
    if LLM_PROVIDER == "openai":
        return "https://api.openai.com/v1/chat/completions", LLM_API_KEY
    base = LLM_BASE_URL or "http://localhost:11434/v1"  # 默认 Ollama 本地服务
    return base.rstrip("/") + "/chat/completions", LLM_API_KEY or "ollama"


def _llm_cache_get(key):
    v = _LLM_CACHE.get(key)
    if v and (_t.time() - v[1]) < _LLM_CACHE_TTL:
        return v[0]
    return None


def _llm_cache_set(key, val):
    _LLM_CACHE[key] = (val, _t.time())


def _llm_messages(system, user):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return msgs


def _llm_call(messages, model, timeout=60):
    url, key = _llm_endpoint()
    payload = json.dumps({"model": model, "messages": messages,
                          "temperature": 0.7, "stream": False}).encode("utf-8")
    req = _ureq.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    with _ureq.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def _llm_call_stream(messages, model, timeout=120):
    url, key = _llm_endpoint()
    payload = json.dumps({"model": model, "messages": messages,
                          "temperature": 0.7, "stream": True}).encode("utf-8")
    req = _ureq.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + key)
    with _ureq.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            part = line[5:].strip()
            if part == "[DONE]":
                break
            try:
                obj = json.loads(part)
                delta = obj["choices"][0]["delta"].get("content", "")
                if delta:
                    yield delta
            except Exception:
                continue

# ----------------------------------------------------------------------------
# 工具: 皮尔逊相关系数
# ----------------------------------------------------------------------------
def pearson(a, b):
    # 容空: 跳过任意一方为 None 的配对 (真实数据常缺库存)
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    if n < 3:
        return 0.0
    xs = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
    sa = sum(xs); sb = sum(ys)
    ma = sa / n; mb = sb / n
    num = sum((xs[i] - ma) * (ys[i] - mb) for i in range(n))
    da = sum((x - ma) ** 2 for x in xs)
    db = sum((y - mb) ** 2 for y in ys)
    if da == 0 or db == 0:
        return 0.0
    return num / math.sqrt(da * db)


def _parse_date(s):
    """解析 YYYY-MM-DD; 空串返回 None, 格式错误抛 ValueError。
       集中校验, 避免各端点把非法日期静默降级成默认区间(隐性 bug)。"""
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d")


def _validate_range(start, end):
    """校验可选 start/end。返回 (ok, error_msg)。"""
    try:
        s = _parse_date(start)
        e = _parse_date(end)
    except ValueError:
        return False, "日期格式应为 YYYY-MM-DD"
    if s and e and e < s:
        return False, "end 不能早于 start"
    return True, ""


# ----------------------------------------------------------------------------
# 内置准真实样本 (离线模式用)
# 基于公开历史: SHFE 铜库存 2024-2025 周报节奏 + LME 公开数据合成, 仅示例。
# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# 期货品种上市日期 (近似, 用于「上市以来」区间)
# ----------------------------------------------------------------------------
LISTING_DATES = {
    # 上期所
    "cu": "1991-03-01", "al": "1992-05-28", "zn": "2007-03-26", "pb": "2011-03-24",
    "ni": "2015-03-27", "sn": "2015-03-27", "au": "2008-01-09", "ag": "2012-05-10",
    "rb": "2009-03-27", "hc": "2014-03-21", "ss": "2019-09-25", "ao": "2023-06-19",
    "bc": "2020-11-19", "ru": "1993-03-01", "nr": "2019-08-12", "bu": "2013-10-09",
    "fu": "2004-08-25",
    # 大商所
    "a": "1993-11-18", "m": "2000-07-17", "y": "2006-01-09", "p": "2007-10-29",
    "c": "2004-09-22", "cs": "2014-12-19", "pp": "2014-02-28", "v": "2009-05-25",
    "l": "2007-07-31", "j": "2011-04-15", "jm": "2013-03-22", "i": "2013-10-18",
    "jd": "2013-11-08", "eg": "2018-12-10", "eb": "2019-09-26", "pg": "2020-03-30",
    "lh": "2021-01-08", "rr": "2019-08-16", "sp": "2018-11-27",
    # 郑商所
    "TA": "2006-12-18", "MA": "2011-10-28", "SR": "2006-01-06", "CF": "2004-06-01",
    "FG": "2012-12-03", "RM": "2012-12-28", "OI": "2012-12-28", "UR": "2019-08-09",
    "SA": "2019-12-06", "PF": "2020-10-12", "PK": "2021-02-01", "AP": "2017-12-22",
    "CJ": "2019-04-30", "PX": "2023-09-15", "SH": "2023-09-15",
    # 能源中心
    "sc": "2018-03-26", "lu": "2020-06-22", "nr": "2019-08-12",
    # 中金所
    "IF": "2010-04-16", "IC": "2015-04-16", "IH": "2015-04-16", "IM": "2022-07-22",
    "T": "2013-09-06", "TF": "2015-03-20", "TS": "2018-08-17",
    # 外盘 (以连续合约可追踪日期估算)
    "lme_cu": "1990-01-01", "lme_al": "1990-01-01", "lme_zn": "1990-01-01",
    "comex_au": "1990-01-01", "comex_cu": "1990-01-01",
}


# 库存指标口径说明 (与前端 INV_METRICS 对齐)
INV_METRIC_META = {
    "inventory_total":     {"name": "总库存",      "desc": "交易所显性总库存"},
    "inventory_circ":      {"name": "可流通库存",  "desc": "剔除锁定后可流通部分"},
    "inventory_warehouse": {"name": "注册仓单",    "desc": "交易所注册仓单量"},
    "inventory_bonded":    {"name": "保税区库存",  "desc": "保税区未入关库存"},
}


def _sample_series(symbol, days=180, start="", end=""):
    """生成一段 (date, close, inventory_*) 样本。
    不同品种用不同库存波动幅度(coeff), 制造相关性强弱差异, 让 Top N 有意义。
    真实规律: 库存降(利多)->价涨, 故整体负相关; 但品种间强弱不一。
    新增: 同时生成 4 条库存口径, 可流通库存通常与价格相关性最强。"""
    base_close = {
        "cu": 68000, "al": 19000, "zn": 23000, "au": 550, "ag": 7800,
        "rb": 3600, "hc": 3800, "ss": 14500, "ao": 3200, "bc": 60000,
        "ru": 14000, "nr": 12000, "bu": 3600, "fu": 3200,
        "i": 800, "j": 2200, "jm": 1500, "m": 3500, "y": 8000, "p": 7500,
        "c": 2400, "pp": 7500, "l": 8200, "jd": 4000, "eg": 4500, "eb": 8500,
        "pg": 4800, "lh": 16000, "sp": 5600,
        "TA": 5800, "MA": 2500, "SR": 6500, "CF": 16000, "FG": 1500, "RM": 2800,
        "OI": 9000, "UR": 2100, "SA": 1900, "PF": 7500, "PK": 10000, "AP": 8500,
        "CJ": 11000, "PX": 8500, "SH": 2700,
        "sc": 620, "lu": 4200,
        "lme_cu": 9000, "comex_cu": 9100, "lme_al": 19000, "lme_zn": 23000,
        "comex_au": 550,
    }.get(symbol, 5000)
    base_inv = {
        "cu": 120000, "al": 200000, "zn": 80000, "au": 3000, "ag": 1500000,
        "rb": 900000, "hc": 350000, "ss": 120000, "ao": 200000, "bc": 40000,
        "ru": 220000, "nr": 80000, "bu": 200000, "fu": 250000,
        "i": 150000000, "j": 800000, "jm": 1500000, "m": 600000, "y": 800000,
        "p": 500000, "c": 2000000, "pp": 400000, "l": 350000, "jd": 150000,
        "eg": 500000, "eb": 180000, "pg": 60000, "lh": 40000, "sp": 400000,
        "TA": 200000, "MA": 800000, "SR": 350000, "CF": 900000, "FG": 400000,
        "RM": 300000, "OI": 350000, "UR": 150000, "SA": 300000, "PF": 250000,
        "PK": 120000, "AP": 300000, "CJ": 80000, "PX": 150000, "SH": 250000,
        "sc": 8000000, "lu": 120000,
        "lme_cu": 300000, "comex_cu": 40000, "lme_al": 200000, "lme_zn": 80000,
        "comex_au": 3000,
    }.get(symbol, 50000)
    # 库存波动系数: 越大->库存对价格影响越强->相关性越强
    coeff = {
        "cu": 0.0045, "al": 0.0015, "zn": 0.0025, "au": 0.0010, "ag": 0.0030,
        "rb": 0.0020, "hc": 0.0018, "ss": 0.0012, "ao": 0.0022, "bc": 0.0040,
        "ru": 0.0012, "nr": 0.0010, "bu": 0.0015, "fu": 0.0015,
        "i": 0.0016, "j": 0.0018, "jm": 0.0017, "m": 0.0014, "y": 0.0013,
        "p": 0.0013, "c": 0.0010, "pp": 0.0014, "l": 0.0014, "jd": 0.0011,
        "eg": 0.0016, "eb": 0.0017, "pg": 0.0015, "lh": 0.0012, "sp": 0.0018,
        "TA": 0.0015, "MA": 0.0016, "SR": 0.0014, "CF": 0.0013, "FG": 0.0019,
        "RM": 0.0013, "OI": 0.0013, "UR": 0.0015, "SA": 0.0020, "PF": 0.0014,
        "PK": 0.0012, "AP": 0.0012, "CJ": 0.0011, "PX": 0.0015, "SH": 0.0017,
        "sc": 0.0010, "lu": 0.0014,
        "lme_cu": 0.0050, "comex_cu": 0.0040, "lme_al": 0.0018, "lme_zn": 0.0028,
        "comex_au": 0.0008,
    }.get(symbol, 0.0020)
    # 支持按 start/end 计算区间长度(上市以来/自定义长区间)
    if start and end:
        try:
            s = datetime.strptime(start, "%Y-%m-%d")
            e = datetime.strptime(end, "%Y-%m-%d")
            days = max(30, (e - s).days + 1)
            today = e
        except ValueError:
            today = datetime(2026, 8, 21)
    else:
        today = datetime(2026, 8, 21)
    out = []
    inv_total = base_inv
    close = base_close
    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        # 总库存: 缓慢下降 + 周期性波动
        inv_trend = 0.997 + 0.006 * math.sin(i / 11.0)
        inv_total = inv_total * inv_trend
        # 价格受库存变化驱动(库存降->价涨) + 自身噪声
        inv_delta = (base_inv - inv_total) / base_inv
        close = close * (1 + coeff * inv_delta + 0.006 * math.sin(i / 9.0))

        # 可流通库存: 对价格反应更快、波动更大, 通常相关性最强
        circ_noise = 0.012 * math.sin(i / 5.0)
        circ_delta = inv_delta * 1.5 + circ_noise
        inv_circ = max(base_inv * 0.08, inv_total * (1 + circ_delta * 0.6))

        # 注册仓单: 相对平滑、滞后
        wh_lag = (base_inv - inv_total) * 0.25 + 0.018 * base_inv * math.sin(i / 13.0)
        inv_warehouse = max(base_inv * 0.03, inv_total * 0.35 + wh_lag)

        # 保税区库存: 不同相位, 常与总库存反向或弱相关
        bonded_phase = 0.22 * base_inv * math.sin(i / 17.0 + 1.2)
        inv_bonded = max(base_inv * 0.04, base_inv * 0.22 + bonded_phase)

        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "close": round(close, 2),
            "inventory": int(inv_total),
            "inventory_total": int(inv_total),
            "inventory_circ": int(inv_circ),
            "inventory_warehouse": int(inv_warehouse),
            "inventory_bonded": int(inv_bonded),
        })
    return out


# ----------------------------------------------------------------------------
# 期货价差/期限结构样本 (futures-spread)
# ----------------------------------------------------------------------------
_SPREAD_BASE_PRICE = {
    "sp": 5600, "cu": 68000, "al": 19000, "zn": 23000, "pb": 15000,
    "ni": 135000, "sn": 260000, "au": 550, "ag": 7800,
    "rb": 3600, "hc": 3800, "ss": 14500, "ru": 14000, "nr": 12000,
    "bu": 3600, "fu": 3200, "i": 800, "j": 2200, "jm": 1500,
    "m": 3500, "y": 8000, "p": 7500, "c": 2400, "pp": 7500,
    "l": 8200, "jd": 4000, "eg": 4500, "eb": 8500, "pg": 4800,
    "lh": 16000, "TA": 5800, "MA": 2500, "SR": 6500, "CF": 16000,
    "FG": 1500, "RM": 2800, "OI": 9000, "UR": 2100, "SA": 1900,
    "PF": 7500, "PK": 10000, "AP": 8500, "CJ": 11000, "PX": 8500,
    "SH": 2700, "sc": 620, "lu": 4200,
    # 中金所股指 (Y轴指数映射)
    "IF": 3900, "IH": 2600, "IC": 5700, "IM": 6200,
    # 国债
    "T": 104, "TF": 102, "TS": 101,
}

_INDEX_UNDERLYING = {
    "IF": {"name": "沪深300", "base": 3900, "sina": "sh000300"},
    "IH": {"name": "上证50",  "base": 2600, "sina": "sh000016"},
    "IC": {"name": "中证500", "base": 5700, "sina": "sh000905"},
    "IM": {"name": "中证1000", "base": 6200, "sina": "sh000852"},
}


def _month_ahead(month_code, base_date):
    """把合约月份 YYMM 转成相对 base_date 的超前月数(可为负)。"""
    try:
        yy = int(str(month_code)[:2])
        mm = int(str(month_code)[2:4])
        y = 2000 + yy
        return (y - base_date.year) * 12 + (mm - base_date.month)
    except Exception:
        return 0


def _hash_noise(seed, i, scale=1.0):
    """确定性伪随机噪声，保证同品种/同合约每次生成的样本一致。"""
    h = _hl.md5(("%s:%d" % (seed, i)).encode("utf-8")).hexdigest()
    v = int(h, 16) / (16 ** 32)  # [0,1)
    return (v * 2 - 1) * scale


def _sample_spread_series(variety, monthA, monthB, ytype="price", start="", end="", days=180):
    """生成期货跨期价差样本。
    返回 [{date, priceA, priceB, spread, y}, ...]，其中 y 是 Y 轴目标值：
      - 商品期货 / ytype=price -> 近月合约 priceA;
      - 股指期货 / ytype=index -> 对应现货指数。
    样本具有 realistic 的 contango/backwardation：远月通常升水/贴水，
    不同月份因季节性出现正/负价差，支持前端 X 轴=spread、Y 轴=price/index。
    """
    if start and end:
        try:
            s = datetime.strptime(start, "%Y-%m-%d")
            e = datetime.strptime(end, "%Y-%m-%d")
            days = max(30, (e - s).days + 1)
            today = e
        except ValueError:
            today = datetime(2026, 8, 21)
    else:
        today = datetime(2026, 8, 21)

    base = _SPREAD_BASE_PRICE.get(variety, 5000)
    is_stock_index = variety in _INDEX_UNDERLYING
    idx_info = _INDEX_UNDERLYING.get(variety, {})
    idx_base = idx_info.get("base", base)

    aheadA = _month_ahead(monthA, today)
    aheadB = _month_ahead(monthB, today)

    out = []
    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        t = i / max(days, 1)
        # 现货/指数中枢走势：趋势 + 周期 + 噪声
        trend = 1.0 + 0.06 * (1 - t)
        cycle = 0.025 * math.sin(i / 13.0)
        spot = base * trend * (1.0 + cycle + _hash_noise("%s:spot" % variety, i, 0.012))

        def contract_price(month_code, ahead):
            # 远月通常有 contango(升水)；季节性扰动让价差可正可负
            base_premium = ahead * 0.008 + 0.015 * math.sin(i / 9.0 + ahead)
            # 不同合约加入独立噪声，防止 priceA==priceB
            noise = _hash_noise("%s:%s" % (variety, month_code), i, 0.018)
            price = spot * (1.0 + base_premium + noise)
            return max(price, 0.01)

        priceA = contract_price(monthA, aheadA)
        priceB = contract_price(monthB, aheadB)
        spread = round(priceA - priceB, 2)

        if ytype == "index" and is_stock_index:
            # 股指现货 = 期货中枢映射到指数点位，加入弱噪声
            y = round(idx_base * (spot / base) * (1.0 + _hash_noise("%s:idx" % variety, i, 0.005)), 2)
        else:
            y = round(priceA, 2)

        out.append({
            "date": d.strftime("%Y-%m-%d"),
            "priceA": round(priceA, 2),
            "priceB": round(priceB, 2),
            "spread": spread,
            "y": y,
        })
    return out


# ----------------------------------------------------------------------------
# 真实数据抓取 (有网环境, OFFLINE_MODE=False 时启用)
# ----------------------------------------------------------------------------
def _real_futures_data(exchange, symbol, start, end):
    """用 akshare 真实抓取期货K线+多口径库存。失败则抛出异常让上层 fallback。
    返回 [{date, close, inventory, inventory_total, inventory_circ,
           inventory_warehouse, inventory_bonded}, ...]
    """
    import akshare as ak
    import pandas as pd

    # 1) 构造行情 sina symbol: 国内主力连续 = code.lower() + "0"（新浪区分大小写, 实测小写生效）
    sina_symbol = symbol.lower() + "0" if exchange in ("SHFE", "DCE", "CZCE", "INE") else symbol

    # 2) 行情数据: 优先新浪日K, 失败转主力连续
    kline = None
    errs = []
    for fn, args in (
        (ak.futures_zh_daily_sina, {"symbol": sina_symbol}),
        (ak.futures_main_sina, {
            "symbol": sina_symbol,
            "start_date": start.replace("-", ""),
            "end_date": end.replace("-", ""),
        }),
    ):
        try:
            kline = fn(**args)
            if kline is not None and not kline.empty:
                break
        except Exception as e:
            errs.append(str(e)[:60])
            continue
    if kline is None or kline.empty:
        raise RuntimeError("行情抓取失败: %s" % "; ".join(errs))

    kline = kline.rename(columns=lambda c: str(c).strip())
    close_col = next((c for c in kline.columns
                      if "close" in str(c).lower() or "收盘" in c), None)
    date_col = next((c for c in kline.columns
                     if "date" in str(c).lower() or "日期" in c), None)
    if close_col is None or date_col is None:
        raise RuntimeError("行情列不匹配: %s" % kline.columns.tolist())
    kline[close_col] = pd.to_numeric(kline[close_col], errors="coerce")
    kline[date_col] = pd.to_datetime(kline[date_col]).dt.strftime("%Y-%m-%d")
    kline = kline[[date_col, close_col]].rename(
        columns={date_col: "date", close_col: "close"}).dropna()

    # 3) 库存: 历史真实库存来自烘焙缓存 futures_<交易所>_<品种>.json
    #    (fetch_real_futures.py 已对齐新版 akshare, 逐交易日抓取真实仓单日报,
    #     取各品种"小计"行仓单数量作为真实库存(吨))。
    #    实时路径在 20s 超时预算内无法迭代全年交易日, 故实时仅作单点兜底:
    #    取不到则留空 -> 上层统一转 null(绝不编造/填 0)。
    #    结论: 有缓存 = 真实历史库存序列; 无缓存 = 真实收盘价 + 库存留空(诚实)。
    inv_total = pd.DataFrame(columns=["date", "inventory_total"])
    inv_warehouse = pd.DataFrame(columns=["date", "inventory_warehouse"])

    # 4) 合并并补齐缺失字段
    merged = kline.copy()
    for df in (inv_total, inv_warehouse):
        if not df.empty:
            merged = merged.merge(df, on="date", how="left")
    # 仅对收盘价做前后填充(补齐个别缺口); 库存绝不填充——缺失即留 null, 不编造
    if "close" in merged.columns:
        merged["close"] = merged["close"].ffill().bfill()

    if "inventory_total" not in merged.columns:
        merged["inventory_total"] = pd.Series([float("nan")] * len(merged))
    if "inventory_warehouse" not in merged.columns:
        merged["inventory_warehouse"] = pd.Series([float("nan")] * len(merged))
    if "inventory_circ" not in merged.columns:
        merged["inventory_circ"] = pd.Series([float("nan")] * len(merged))
    if "inventory_bonded" not in merged.columns:
        merged["inventory_bonded"] = pd.Series([float("nan")] * len(merged))
    # 仅已知总量映射到 inventory; 分口径(circ/warehouse/bonded)缺失即留 null, 绝不按比例编造
    merged["inventory"] = merged["inventory_total"]

    if start:
        merged = merged[merged["date"] >= start]
    if end:
        merged = merged[merged["date"] <= end]

    return [
        {"date": r["date"],
         "close": None if pd.isna(r["close"]) else float(r["close"]),
         "inventory": None if pd.isna(r["inventory_total"]) else float(r["inventory_total"]),
         "inventory_total": None if pd.isna(r["inventory_total"]) else float(r["inventory_total"]),
         "inventory_circ": None if pd.isna(r["inventory_circ"]) else float(r["inventory_circ"]),
         "inventory_warehouse": None if pd.isna(r["inventory_warehouse"]) else float(r["inventory_warehouse"]),
         "inventory_bonded": None if pd.isna(r["inventory_bonded"]) else float(r["inventory_bonded"])}
        for _, r in merged.iterrows()
    ]


# ----------------------------------------------------------------------------
# 真实数据抓取辅助: 超时保护 + 本地缓存
# ----------------------------------------------------------------------------
def _safe_real(exchange, symbol, start, end, timeout=20):
    """在子线程里跑 akshare 真抓, 超时/异常返回 None (上层回退样本)。"""
    box = {}
    def _run():
        try:
            box["d"] = _real_futures_data(exchange, symbol, start, end)
        except Exception as e:  # noqa
            box["e"] = e
    t = threading.Thread(target=_run, daemon=True)
    t.start(); t.join(timeout)
    if "d" in box and box["d"]:
        return box["d"]
    return None


def _safe_real_spread(variety, monthA, monthB, ytype, start, end, timeout=20):
    """在子线程里跑价差真实抓取, 超时/异常返回 None (上层回退样本)。"""
    if not _HAS_SPREAD_SRC:
        return None
    box = {}

    def _run():
        try:
            box["d"] = _real_spread_series(variety, monthA, monthB, ytype, start, end)
        except Exception as _e:  # noqa
            box["e"] = _e
    t = threading.Thread(target=_run, daemon=True)
    t.start(); t.join(timeout)
    if "d" in box and box["d"]:
        return box["d"]
    return None


def _load_cached_futures(exchange, symbol):
    """若本地存在真实缓存文件 backend/data/futures_<exch>_<symbol>.json 则优先返回。
       fetch_real_futures.py 在有网机器上生成这些文件, 实现"默认真实数据"。
       缓存文件名统一用大写代码(如 futures_CZCE_CF.json), 但前端常传小写(如 cf),
       Windows 不区分大小写能跑、Mac/Linux 区分大小写会找不到 -> 故做大小写不敏感匹配。"""
    try:
        for sym in (symbol, symbol.upper(), symbol.lower()):
            p = os.path.join(DATA_DIR, "futures_%s_%s.json" % (exchange, sym))
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    arr = json.load(f)
                if isinstance(arr, list) and arr:
                    return arr
    except Exception:
        pass
    return None


# ----------------------------------------------------------------------------
# 路由
# ----------------------------------------------------------------------------
@app.route("/api/futures", methods=["GET"])
def api_futures():
    """参数: symbol(代码) exchange(SHFE/DCE/CZCE/INE/LME/COMEX)
       start end(YYYY-MM-DD) mode(global=全球合计)"""
    symbol = safe_code(request.args.get("symbol", "cu"))
    exchange = request.args.get("exchange", "SHFE")
    start = cap_len(request.args.get("start", ""), 10)
    end = cap_len(request.args.get("end", ""), 10)
    mode = request.args.get("mode", "single")  # single | global

    if mode not in ("single", "global"):
        return jsonify({"ok": False, "error": "mode 必须为 single 或 global"}), 400
    if exchange not in ("SHFE", "DCE", "CZCE", "INE", "LME", "COMEX"):
        return jsonify({"ok": False, "error": "exchange 不支持: %s" % exchange}), 400
    ok, err = _validate_range(start, end)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400

    # 默认真实数据: 本地缓存 -> akshare 真抓 -> 离线样本(兜底, 绝不空/500)
    try:
        if mode == "global":
            parts, ok_real = [], True
            for ex, sym in [("SHFE", symbol), ("LME", "lme_" + symbol),
                            ("COMEX", "comex_" + symbol)]:
                d = _safe_real(ex, sym, start, end)
                if d is None:
                    ok_real = False
                    break
                parts.append(d)
            if ok_real:
                from collections import defaultdict
                m = defaultdict(lambda: {
                    "close": None,
                    "inventory": 0, "inventory_total": 0, "inventory_circ": 0,
                    "inventory_warehouse": 0, "inventory_bonded": 0,
                })
                for p in parts:
                    for r in p:
                        m[r["date"]]["close"] = r["close"]
                        for k in ("inventory", "inventory_total", "inventory_circ",
                                  "inventory_warehouse", "inventory_bonded"):
                            m[r["date"]][k] += (r.get(k) or 0)
                data = [{"date": d, "close": m[d]["close"], **{k: m[d][k] for k in (
                    "inventory", "inventory_total", "inventory_circ",
                    "inventory_warehouse", "inventory_bonded")}}
                    for d in sorted(m.keys())]
                offline = False
            else:
                # 离线全球合计样本: SHFE+LME+COMEX 三套样本相加
                a = _sample_series(symbol, start=start, end=end)
                b = _sample_series("lme_cu", start=start, end=end)
                c = _sample_series("comex_cu", start=start, end=end)
                data = [{
                    "date": a[i]["date"], "close": a[i]["close"],
                    "inventory": a[i]["inventory"] + b[i]["inventory"] + c[i]["inventory"],
                    "inventory_total": a[i].get("inventory_total", 0) + b[i].get("inventory_total", 0) + c[i].get("inventory_total", 0),
                    "inventory_circ": a[i].get("inventory_circ", 0) + b[i].get("inventory_circ", 0) + c[i].get("inventory_circ", 0),
                    "inventory_warehouse": a[i].get("inventory_warehouse", 0) + b[i].get("inventory_warehouse", 0) + c[i].get("inventory_warehouse", 0),
                    "inventory_bonded": a[i].get("inventory_bonded", 0) + b[i].get("inventory_bonded", 0) + c[i].get("inventory_bonded", 0),
                } for i in range(len(a))]
                offline = True
        else:
            cached = _load_cached_futures(exchange, symbol)
            if cached is not None:
                data, offline = cached, False
            else:
                d = _safe_real(exchange, symbol, start, end)
                if d is not None:
                    data, offline = d, False
                else:
                    data = _sample_series(symbol, start=start, end=end)
                    offline = True
        r_val = pearson([x["close"] for x in data], [x["inventory"] for x in data])
        return jsonify({"ok": True, "offline": offline,
                        "listing_date": LISTING_DATES.get(symbol, ""),
                        "data": data, "corr": round(r_val, 3)})
    except Exception as e:
        logger.exception("futures 处理异常")
        # 若已加载到真实数据(如本地真实缓存), 即使相关性算不出也返回真实行情, 绝不回退合成
        if data:
            return jsonify({"ok": True, "offline": False,
                            "note": "相关性暂不可用（库存数据缺失），行情为真实数据。",
                            "listing_date": LISTING_DATES.get(symbol, ""),
                            "data": data, "corr": 0.0})
        try:
            data = _sample_series(symbol, start=start, end=end)
            r_val = pearson([x["close"] for x in data], [x["inventory"] for x in data])
        except Exception:
            data, r_val = [], 0.0
        return jsonify({"ok": True, "offline": True,
                        "note": "真实抓取异常, 已回退离线样本。",
                        "listing_date": LISTING_DATES.get(symbol, ""),
                        "data": data, "corr": round(r_val, 3)})


@app.route("/api/refresh", methods=["POST", "GET"])
def api_refresh():
    """触发单个品种的真实库存刷新：优先用东方财富 futures_inventory_em 抓取，
    更新本地缓存 backend/data/futures_<exchange>_<symbol>.json。
    参数: exchange(SHFE/DCE/CZCE) symbol(品种代码)。
    """
    symbol = safe_code(request.args.get("symbol", "cu"))
    exchange = request.args.get("exchange", "SHFE")
    if exchange not in ("SHFE", "DCE", "CZCE", "INE"):
        return jsonify({"ok": False, "error": "exchange 不支持: %s" % exchange}), 400
    if not _HAS_BAKE_INV:
        return jsonify({"ok": False, "error": "刷新模块未加载"}), 500

    def _run():
        return _bake_inv_em.refresh_one(exchange, symbol, verbose=False)

    box = {}
    t = threading.Thread(target=lambda: box.update({"r": _run()}), daemon=True)
    t.start()
    t.join(timeout=40)
    if "r" not in box:
        return jsonify({"ok": False, "error": "刷新超时，请稍后重试"}), 504
    res = box["r"]
    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("msg", "刷新失败")}), 502
    return jsonify({"ok": True,
                    "exchange": exchange,
                    "symbol": symbol,
                    "rows": res.get("rows"),
                    "filled": res.get("filled"),
                    "last_inventory": res.get("last_inv"),
                    "msg": res.get("msg")})


@app.route("/api/inventory_overview", methods=["GET"])
def api_inventory_overview():
    """聚合本地全部期货缓存，返回每个品种的最新库存/日期/变动/来源，供「全品种库存概览表」使用。
    交易所仓单品种取 inventory_total(吨)；原油(IN E sc)取美国EIA周度原油库存变动(eia_crude_change, 百万桶)，标注 source=EIA。
    """
    items = []
    for fp in glob.glob(os.path.join(DATA_DIR, "futures_*.json")):
        base = os.path.basename(fp)
        m = re.match(r"futures_(SHFE|DCE|CZCE|INE)_(.+)\.json", base)
        if not m:
            continue
        exch, sym = m.group(1), m.group(2)
        try:
            arr = _load_cached_futures(exch, sym) or []
        except Exception:
            continue
        if not arr:
            continue
        is_crude = (exch == "INE" and sym.upper() == "SC")
        vals = []
        for r in arr:
            v = r.get("eia_crude_change") if is_crude else r.get("inventory_total")
            if v is not None:
                vals.append((r.get("date"), v))
        if not vals:
            items.append({"exchange": exch, "symbol": sym, "has_inv": False,
                          "source": "EIA" if is_crude else "WH"})
            continue
        vals.sort(key=lambda x: x[0])
        last_date, last = vals[-1]
        prev = vals[-2][1] if len(vals) >= 2 else None
        change = (last - prev) if prev is not None else None
        change_pct = round(change / prev * 100, 2) if (prev not in (None, 0)) else None
        items.append({"exchange": exch, "symbol": sym, "has_inv": True,
                      "last_inv": last, "last_date": last_date,
                      "prev_inv": prev, "change": change,
                      "change_pct": change_pct,
                      "source": "EIA" if is_crude else "WH"})
    exch_order = {"SHFE": 0, "DCE": 1, "CZCE": 2, "INE": 3}
    items.sort(key=lambda x: (exch_order.get(x["exchange"], 9), x["symbol"]))
    return jsonify({"ok": True, "count": len(items), "items": items})


@app.route("/api/eia_crude", methods=["GET"])
def api_eia_crude():
    """实时拉取美国 EIA 周度商业原油库存（需 EIA_API_KEY 环境变量）。
    有 key 时真实请求 api.eia.gov（WCRSTUS=美国商业原油库存，单位千桶→百万桶）；
    无 key 时返回 missing_key 提示，前端据此引导用户配置。"""
    import urllib.request, json as _json
    key = os.environ.get("EIA_API_KEY")
    if not key:
        return jsonify({"ok": False, "reason": "missing_key",
                        "hint": "在启动 backend 前设置环境变量 EIA_API_KEY（免费申请 https://www.eia.gov/opendata/），即可将原油库存升级为实时刷新。"})
    try:
        url = ("https://api.eia.gov/v2/petroleum/pri/swr/crude/data/"
               "?api_key=" + key +
               "&frequency=weekly&data[0]=value&facets[product][]=WCRSTUS"
               "&sort[0][column]=period&sort[0][direction]=desc&offset=0&length=1")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            j = _json.loads(resp.read().decode("utf-8"))
        rows = (j.get("response") or {}).get("data") or []
        row = rows[0] if rows else {}
        period = row.get("period")
        value = row.get("value")
        if value is None:
            return jsonify({"ok": False, "reason": "empty", "error": "EIA 返回空数据"})
        return jsonify({"ok": True, "period": period,
                        "value_mbbl": round(float(value) / 1000.0, 1), "unit": "百万桶"})
    except Exception as e:
        return jsonify({"ok": False, "reason": "fetch_error", "error": str(e)})


@app.route("/api/corr_top", methods=["GET"])
def api_corr_top():
    """遍历全品种算相关性, 返回 Top N (按 |r| 降序)。离线用样本。"""
    symbols = [
        ("cu", "SHFE"), ("al", "SHFE"), ("zn", "SHFE"), ("au", "SHFE"),
        ("ag", "SHFE"), ("rb", "SHFE"), ("hc", "SHFE"), ("ss", "SHFE"),
        ("ao", "SHFE"), ("bc", "SHFE"), ("ru", "SHFE"), ("nr", "SHFE"),
        ("bu", "SHFE"), ("fu", "SHFE"),
        ("i", "DCE"), ("j", "DCE"), ("jm", "DCE"), ("m", "DCE"),
        ("y", "DCE"), ("p", "DCE"), ("c", "DCE"), ("pp", "DCE"),
        ("l", "DCE"), ("jd", "DCE"), ("eg", "DCE"), ("eb", "DCE"),
        ("pg", "DCE"), ("lh", "DCE"), ("sp", "DCE"),
        ("TA", "CZCE"), ("MA", "CZCE"), ("SR", "CZCE"), ("CF", "CZCE"),
        ("FG", "CZCE"), ("RM", "CZCE"), ("OI", "CZCE"), ("UR", "CZCE"),
        ("SA", "CZCE"), ("PF", "CZCE"), ("PK", "CZCE"), ("AP", "CZCE"),
        ("CJ", "CZCE"), ("PX", "CZCE"), ("SH", "CZCE"),
        ("sc", "INE"), ("lu", "INE"),
        ("lme_cu", "LME"), ("lme_al", "LME"), ("lme_zn", "LME"),
        ("comex_au", "COMEX"), ("comex_cu", "COMEX"),
    ]
    n = safe_int(request.args.get("n", 5), default=5, lo=1, hi=50)
    today = datetime.now().strftime("%Y-%m-%d")
    start = request.args.get("start", "")
    end = request.args.get("end", today)
    ok, err = _validate_range(start, end)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    rows = []
    for sym, ex in symbols:
        # 默认从上市日算起, 让长区间更接近真实历史
        sym_start = start or LISTING_DATES.get(sym, "")
        sym_end = end or today
        if OFFLINE_MODE:
            d = _sample_series(sym, start=sym_start, end=sym_end)
        else:
            try:
                d = _real_futures_data(ex, sym, sym_start, sym_end)
            except Exception:
                continue
        # 在 4 个库存口径里选 |r| 最大的, 并返回该最优指标
        best_r = 0.0
        best_metric = "inventory_total"
        for metric in ("inventory_total", "inventory_circ",
                       "inventory_warehouse", "inventory_bonded"):
            r = pearson([x["close"] for x in d],
                        [x.get(metric, x.get("inventory", 0)) for x in d])
            if abs(r) > abs(best_r):
                best_r = r
                best_metric = metric
        rows.append({
            "symbol": sym, "exchange": ex, "corr": round(best_r, 3),
            "metric": best_metric,
            "strength": "强" if abs(best_r) >= 0.6 else ("中" if abs(best_r) >= 0.3 else "弱"),
        })
    rows.sort(key=lambda x: abs(x["corr"]), reverse=True)
    return jsonify({"ok": True, "offline": OFFLINE_MODE, "top": rows[:n],
                    "note": "离线样本计算; 有网环境 OFFLINE_MODE=False 即真实排名。"})


@app.route("/api/futures_chain", methods=["GET"])
def api_futures_chain():
    """期货产业链联动分析：给定品种代码+交易所，返回跨品种相关性 + 产业链传导报告(HTML)。
    参数: symbol(代码, 如 sp) exchange(SHFE/DCE/CZCE/INE) [from(YYYY-MM-DD)] [to(YYYY-MM-DD)]
    exchange 缺省或非法时，自动按 backend/data 缓存的品种-交易所映射推断，推断不到才报错。"""
    symbol = safe_code(request.args.get("symbol", "sp"))
    req_ex = (request.args.get("exchange") or "").strip().upper()
    from_d = (request.args.get("from") or "").strip() or None
    to_d = (request.args.get("to") or "").strip() or None
    # 交易所自动推断：优先用传入；否则查 data/ 下 futures_<EX>_<SYM>.json
    exchange = req_ex
    if exchange not in ("SHFE", "DCE", "CZCE", "INE"):
        guessed = None
        _datadir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        for ex in ("SHFE", "DCE", "CZCE", "INE"):
            if os.path.exists(os.path.join(_datadir, "futures_%s_%s.json" % (ex, symbol.upper()))):
                guessed = ex
                break
        if guessed:
            exchange = guessed
        else:
            return jsonify({"ok": False,
                            "error": "无法识别品种 %s 的交易所（传入 exchange=%r 非法，且 data/ 缓存未找到对应 futures_*.json）。请显式传 exchange=SHFE/DCE/CZCE/INE" % (symbol, req_ex)}), 400
    if not _HAS_FUTURES_CHAIN:
        return jsonify({"ok": False, "error": "分析引擎 futures_chain 未加载"}), 500
    try:
        res = futures_chain.api_chain(symbol, exchange, from_date=from_d, to_date=to_d)
        if not res.get("ok"):
            err = res.get("data", {}).get("error") or res.get("error") or "分析失败"
            return jsonify({"ok": False, "error": err}), 404
        return jsonify(res)
    except Exception as e:
        logger.exception("futures_chain 处理异常")
        return jsonify({"ok": False, "error": "分析异常: %s" % e}), 500


# 板块共振全景矩阵的默认品种组合：老板 6 实盘打头 + 覆盖全部 11 板块的代表品种（共 24 个），
# 让「列按板块分组色条」在首屏即展示板块聚类。用户仍可在品种多选面板自由增减。
MATRIX_VARIETIES = [
    # 老板 6 实盘
    ("sp", "SHFE"), ("fg", "CZCE"), ("sa", "CZCE"), ("eg", "DCE"), ("jd", "DCE"), ("sr", "CZCE"),
    # 黑色 / 建材 / 化工
    ("rb", "SHFE"), ("hc", "SHFE"), ("i", "DCE"), ("ta", "CZCE"), ("ma", "CZCE"),
    # 有色 / 贵金属
    ("cu", "SHFE"), ("al", "SHFE"), ("zn", "SHFE"), ("ni", "SHFE"), ("au", "SHFE"), ("ag", "SHFE"),
    # 能源 / 橡胶
    ("sc", "INE"), ("bu", "SHFE"), ("ru", "SHFE"), ("nr", "DCE"),
    # 油粕 / 养殖 / 软商品
    ("m", "DCE"), ("y", "DCE"), ("lh", "DCE"), ("pk", "CZCE"), ("ap", "CZCE"),
]


def _guess_exchange(symbol):
    """按 backend/data 缓存的 futures_<EX>_<SYM>.json 自动推断交易所（唯一匹配用）。"""
    _datadir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    for ex in ("SHFE", "DCE", "CZCE", "INE"):
        if os.path.exists(os.path.join(_datadir, "futures_%s_%s.json" % (ex, symbol.upper()))):
            return ex
    return None


def _list_available_varieties():
    """返回 data/ 下所有已缓存品种 (symbol,exchange,name)，供前端矩阵做品种多选。"""
    _datadir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    out = []
    try:
        names = futures_chain.NAME_MAP if _HAS_FUTURES_CHAIN else {}
    except Exception:
        names = {}
    import re as _re
    pat = _re.compile(r"^futures_(SHFE|DCE|CZCE|INE)_([A-Z0-9]+)\.json$")
    for fn in os.listdir(_datadir):
        m = pat.match(fn)
        if not m:
            continue
        ex, sym = m.group(1), m.group(2)
        out.append({"symbol": sym, "exchange": ex, "name": names.get(sym, sym)})
    out.sort(key=lambda x: (x["exchange"], x["symbol"]))
    return out


@app.route("/api/futures_varieties", methods=["GET"])
def api_futures_varieties():
    """轻量品种列表：返回 data/ 下所有已缓存品种 (symbol,exchange,name)。
    供 futures-chain 等页面直接填充下拉候选，无需先算一遍共振矩阵（省掉全量相关计算）。"""
    return jsonify({"ok": True, "available": _list_available_varieties()})


@app.route("/api/futures_sector_matrix", methods=["GET"])
def api_futures_sector_matrix():
    """板块共振全景矩阵：给定一组品种（默认覆盖 15 个代表品种），返回 品种 × 板块 的共振强度矩阵。
    参数 symbols 可选，格式 "rb:SHFE,cu:SHFE"（SYM:EX 显式）或 "rb,cu"（自动推断交易所）。
    返回 {"ok", "rows":[{symbol,exchange,name,vol,beta,cells:{sector:{raw,partial}}}], "sectors":[...]}。
    可选 from/to（YYYY-MM-DD）限定时间区间，看特定窗口的板块共振结构。"""
    if not _HAS_FUTURES_CHAIN:
        return jsonify({"ok": False, "error": "分析引擎 futures_chain 未加载"}), 500
    syms = (request.args.get("symbols") or "").strip()
    from_d = (request.args.get("from") or "").strip() or None
    to_d = (request.args.get("to") or "").strip() or None
    if syms:
        varieties = []
        for part in syms.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                s, e = part.split(":", 1)
                varieties.append((s.strip().lower(), e.strip().upper()))
            else:
                ex = _guess_exchange(part.strip().lower())
                if ex:
                    varieties.append((part.strip().lower(), ex))
                # 推断不到则跳过该品种
    else:
        varieties = MATRIX_VARIETIES
    if not varieties:
        return jsonify({"ok": False, "error": "无有效品种（symbols 解析为空或全部交易所推断失败）"}), 400
    try:
        res = futures_chain._sector_matrix(varieties, from_date=from_d, to_date=to_d)
        if not res.get("ok"):
            return jsonify({"ok": False, "error": res.get("error", "矩阵计算失败")}), 404
        res["available"] = _list_available_varieties()
        res["default"] = ["%s:%s" % (s, e) for s, e in MATRIX_VARIETIES]
        res["from"] = from_d
        res["to"] = to_d
        return jsonify(res)
    except Exception as e:
        logger.exception("futures_sector_matrix 处理异常")
        return jsonify({"ok": False, "error": "矩阵异常: %s" % e}), 500


@app.route("/api/itinerary/generate", methods=["POST"])
def api_itinerary_generate():
    """行程规划：源自 map 项目。城市+天数+风格+兴趣词 -> 可编辑每日行程。
    可选接 map 项目真实 AI：请求体带 map_backend_url（或环境变量 MAP_BACKEND_URL）即代理其 /api/generate。"""
    if not _HAS_ITINERARY:
        return jsonify({"ok": False, "error": "行程模块未加载"}), 500
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:  # noqa
        data = {}
    city = (data.get("city") or "").strip()
    days = data.get("days", 3)
    style = (data.get("style") or "classic").strip()
    interests = (data.get("interests") or "").strip()
    map_backend_url = (data.get("map_backend_url") or "").strip()
    try:
        res = itinerary.generate(city, days, style=style, interests=interests, map_backend_url=map_backend_url)
    except Exception as e:
        logger.exception("itinerary 生成异常")
        return jsonify({"ok": False, "error": "生成异常: %s" % e}), 500
    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error", "生成失败")}), 400
    return jsonify(res)



@app.route("/api/quote", methods=["GET"])
def api_quote():
    """股票实时行情, 模仿 StockSignal: 新浪 hq.sinajs.cn + akshare 兜底。"""
    code = safe_code(request.args.get("code", "sh600519"))  # 带交易所前缀
    if OFFLINE_MODE:
        # 离线样本: 基于 code 的确定性伪随机(同 code 同价, 演示稳定不抖动)
        import hashlib
        seed = int(hashlib.md5(code.encode("utf-8")).hexdigest(), 16)
        price = round(5 + (seed % 199500) / 100.0, 2)
        chg = round(((seed >> 16) % 1001) / 100.0 - 5.0, 2)  # -5%~+5%
        prev = round(price / (1 + chg / 100.0), 2)
        return jsonify({"ok": True, "offline": True,
                        "name": code, "price": price, "prev": prev,
                        "chg": chg,
                        "note": "离线样本(确定性, 同代码价格稳定)。有网环境填新浪接口即真行情。"})
    try:
        # 真·StockSignal 风格: 新浪 + GBK + Referer
        import urllib.request
        url = f"https://hq.sinajs.cn/list={code}"
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("gbk")
        parts = raw.split('"')[1].split(",")
        name, price, prev = parts[0], float(parts[3]), float(parts[2])
        chg = round((price - prev) / prev * 100, 2)
        return jsonify({"ok": True, "offline": False, "name": name,
                        "price": price, "prev": prev, "chg": chg})
    except Exception as e:
        logger.warning("新浪行情失败, 转 akshare 兜底: %s", str(e)[:120])
        # akshare 兜底
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            row = df[df["代码"] == code[2:]].iloc[0]
            return jsonify({"ok": True, "offline": False, "name": row["名称"],
                            "price": float(row["最新价"]), "prev": float(row["昨收"]),
                            "chg": round(float(row["涨跌幅"]), 2)})
        except Exception as e2:
            logger.exception("quote 兜底也失败")
            return jsonify({"ok": False, "error": str(e2)[:200]}), 500


@app.route("/api/shepherd", methods=["GET"])
def api_shepherd():
    """牧羊人8项情绪指标 + 综合温度(0-100)。模仿 StockSignal modules/shepherd.py。
    离线: 返回内置演示快照 + 样本历史(供分位打分)。
    真网: akshare stock_market_activity_legu + stock_zt_pool_em + stock_zt_pool_previous_em。"""
    if OFFLINE_MODE:
        return jsonify(_shepherd_offline())
    try:
        return jsonify(_shepherd_live())
    except Exception as e:
        logger.warning("shepherd 真抓取失败, 回退离线: %s", str(e)[:120])
        return jsonify(_shepherd_offline(extra_note="真抓取失败:" + str(e)[:120]))


# ───────── 牧羊人 8 项指标口径(与 StockSignal THRESHOLDS 一致) ─────────
SHEP_THRESH = {
    "up_count":     dict(name="上涨家数", unit="家", dir=1,  hot=3000, warm=1500, hot_label="高温(可出手)", cold_label="低温(先防守)"),
    "down_count":   dict(name="下跌家数", unit="家", dir=-1, hot=1500, warm=3000, hot_label="低温(可出手)", cold_label="高温(先防守)"),
    "limit_up":     dict(name="涨停家数", unit="家", dir=1,  hot=50,   warm=20,   hot_label="亢奋",       cold_label="低迷"),
    "limit_down":   dict(name="跌停家数", unit="家", dir=-1, hot=5,    warm=15,   hot_label="安全",       cold_label="恐慌(>30)"),
    "zt_prev_ret":  dict(name="昨日涨停表现", unit="%", dir=1, hot=3.0, warm=0.0, hot_label="炸裂",       cold_label="吃面"),
    "red_ratio":    dict(name="红盘占比", unit="%", dir=1,  hot=60.0, warm=45.0, hot_label="普涨",       cold_label="普跌"),
    "connect_hl":   dict(name="连板高度", unit="板", dir=1,  hot=6,    warm=3,    hot_label="高风险偏好", cold_label="冰点"),
    "zt_fail_ratio":dict(name="炸板率",  unit="%", dir=-1, hot=30.0, warm=50.0, hot_label="封板稳",     cold_label="分歧大"),
}


def _shepherd_score(v, th):
    """单指标阈值线性打分(0-100)。"""
    if th["dir"] > 0:
        return 100.0 if v >= th["hot"] else (50.0 if v >= th["warm"] else 10.0)
    return 100.0 if v <= th["hot"] else (50.0 if v <= th["warm"] else 10.0)


def _shepherd_temperature(today, hist=None):
    """复刻 shepherd_temperature: 有历史用分位打分, 无则用阈值退化。"""
    subs = []
    for k, th in SHEP_THRESH.items():
        v = today.get(k)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        if hist and k in hist and len(hist[k]) >= 5:
            s = hist[k]
            pct = sum(1 for x in s if x < v) / len(s)
            subs.append(pct * 100 if th["dir"] > 0 else (1 - pct) * 100)
            continue
        subs.append(_shepherd_score(v, th))
    return float(sum(subs) / len(subs)) if subs else 50.0


def _shepherd_offline(extra_note=""):
    """内置演示: 取一个真实交易日结构(如 2026-08-21 偏热市)。"""
    today = {
        "up_count": 3200, "down_count": 1400, "limit_up": 62, "limit_down": 4,
        "zt_prev_ret": 3.4, "red_ratio": 69.6, "connect_hl": 7, "zt_fail_ratio": 28.0,
    }
    # 样本历史(近 30 日, 用于分位打分)
    import random
    random.seed(42)
    hist = {k: [] for k in SHEP_THRESH}
    for _ in range(30):
        hist["up_count"].append(random.randint(1200, 3300))
        hist["down_count"].append(random.randint(1300, 3500))
        hist["limit_up"].append(random.randint(15, 75))
        hist["limit_down"].append(random.randint(2, 22))
        hist["zt_prev_ret"].append(round(random.uniform(-1.5, 4.0), 2))
        hist["red_ratio"].append(round(random.uniform(38, 70), 1))
        hist["connect_hl"].append(random.randint(2, 8))
        hist["zt_fail_ratio"].append(round(random.uniform(22, 55), 1))
    # 把 today 也并进去, 让分位更稳
    for k in SHEP_THRESH:
        hist[k].append(today[k])
    temp = _shepherd_temperature(today, hist)
    return {
        "ok": True, "offline": True,
        "date": "2026-08-21 (演示)",
        "indicators": today,
        "thresholds": SHEP_THRESH,
        "temperature": round(temp, 1),
        "note": ("离线演示快照。有网环境返回真实 akshare 抓取值。" + extra_note),
    }


def _shepherd_live():
    """真抓 akshare 三源, 复刻 get_shepherd_today。"""
    import akshare as ak
    import pandas as pd  # _shepherd_live 用 pd.to_numeric; akshare 依赖 pandas, 真网环境必然可用
    from datetime import datetime as _dt
    d = _dt.now().strftime("%Y%m%d")
    merged = {}
    meta = {"available": [], "unavailable": []}
    # 1) legu 涨跌/涨停/跌停/红盘占比
    try:
        df = ak.stock_market_activity_legu()
        if df is not None and "item" in df.columns:
            def _v(n):
                sub = df[df["item"] == n]["value"]
                return float(pd.to_numeric(sub.iloc[0], errors="coerce")) if not sub.empty else None
            for nm, key in (("上涨", "up_count"), ("下跌", "down_count"),
                            ("涨停", "limit_up"), ("跌停", "limit_down")):
                v = _v(nm)
                if v is not None:
                    merged[key] = v; meta["available"].append(key)
            if "up_count" in merged and "down_count" in merged:
                merged["red_ratio"] = merged["up_count"] / (merged["up_count"] + merged["down_count"]) * 100
                meta["available"].append("red_ratio")
    except Exception as e:
        meta["unavailable"].append(("legu", str(e)[:80]))
    # 2) 涨停池 连板/炸板
    try:
        zt = ak.stock_zt_pool_em(date=d)
        if zt is not None and not zt.empty:
            merged["limit_up"] = float(len(zt))
            if "连板数" in zt.columns:
                merged["connect_hl"] = float(pd.to_numeric(zt["连板数"], errors="coerce").max())
            if "炸板次数" in zt.columns:
                zb = pd.to_numeric(zt["炸板次数"], errors="coerce").fillna(0)
                merged["zt_fail_ratio"] = float((zb > 0).mean() * 100)
            meta["available"].extend(["limit_up", "connect_hl", "zt_fail_ratio"])
    except Exception as e:
        meta["unavailable"].append(("zt_pool", str(e)[:80]))
    # 3) 昨日涨停表现
    try:
        pv = ak.stock_zt_pool_previous_em(date=d)
        if pv is not None and not pv.empty:
            col = next((c for c in pv.columns if "涨跌幅" in str(c) or "change" in str(c).lower()), None)
            if col:
                chg = pd.to_numeric(pv[col], errors="coerce").dropna()
                merged["zt_prev_ret"] = float(chg.mean())
                meta["available"].append("zt_prev_ret")
    except Exception as e:
        meta["unavailable"].append(("zt_prev_ret", str(e)[:80]))
    temp = _shepherd_temperature(merged, None)
    return {
        "ok": True, "offline": False, "date": d,
        "indicators": merged, "thresholds": SHEP_THRESH,
        "temperature": round(temp, 1), "meta": meta,
    }


@app.route("/api/etf", methods=["GET"])
def api_etf():
    """ETF 实时行情 + 规模 + 费率的真实数据(akshare)。
       离线降级到 data/etf.json 静态真实样本(非随机, 取自公开披露快照)。"""
    typ = request.args.get("type", "")
    if OFFLINE_MODE:
        try:
            data = _load_static("etf.json")
            if typ:
                data = [x for x in data if x.get("type") == typ]
            return jsonify({"ok": True, "offline": True, "rows": data,
                            "updated": _file_mtime("etf.json"),
                            "note": "离线静态样本(沙箱禁网)。有网环境 OFFLINE_MODE=False 即真实 ETF 行情。"})
        except Exception:
            return jsonify({"ok": True, "offline": True, "rows": [], "note": "本地 etf.json 缺失"})
    try:
        import akshare as ak
        df = ak.fund_etf_spot_em()
        rows = []
        for _, r in df.iterrows():
            rows.append({
                "code": str(r["代码"]), "name": str(r["名称"]),
                "type": str(r.get("类型", "")),
                "price": float(r.get("最新价", 0) or 0),
                "chg": float(r.get("涨跌幅", 0) or 0),
                "amount": float(r.get("成交额", 0) or 0),
                "turnover": float(r.get("换手率", 0) or 0),
            })
        if typ:
            rows = [x for x in rows if x["type"] == typ]
        return jsonify({"ok": True, "offline": False, "rows": rows[:200],
                        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    except Exception as e:
        logger.warning("ETF 真抓取失败, 回退静态: %s", str(e)[:120])
        try:
            data = _load_static("etf.json")
            return jsonify({"ok": True, "offline": True, "rows": data,
                            "note": "真实抓取失败, 回退静态样本: " + str(e)[:80]})
        except Exception:
            return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.route("/api/sector", methods=["GET"])
def api_sector():
    """板块实时涨跌幅(akshare 行业板块)。离线降级 data/sector.json。"""
    if OFFLINE_MODE:
        try:
            data = _load_static("sector.json")
            return jsonify({"ok": True, "offline": True, "rows": data,
                            "updated": _file_mtime("sector.json"),
                            "note": "离线静态样本。有网环境 OFFLINE_MODE=False 即真实板块行情。"})
        except Exception:
            return jsonify({"ok": True, "offline": True, "rows": [], "note": "本地 sector.json 缺失"})
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        rows = []
        for _, r in df.iterrows():
            chg = float(r.get("涨跌幅", 0) or 0)
            rows.append({
                "name": str(r["板块名称"]),
                "chg": chg,
                "strength5": round(chg / 10.0, 3),  # 粗略 5 日强度代理(真网可换 5 日数据)
                "turnover": float(r.get("换手率", 0) or 0),
                "leader": str(r.get("领涨股", "")),
            })
        return jsonify({"ok": True, "offline": False, "rows": rows,
                        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    except Exception as e:
        logger.warning("板块真抓取失败, 回退静态: %s", str(e)[:120])
        try:
            data = _load_static("sector.json")
            return jsonify({"ok": True, "offline": True, "rows": data,
                            "note": "真实抓取失败, 回退静态样本: " + str(e)[:80]})
        except Exception:
            return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.route("/api/data", methods=["GET"])
def api_data():
    """通用静态数据托管: 工具类 app 读本地真实结构化 JSON/CSV, 避免 file:// 跨域。
       参数 file=文件名(限 data/ 目录下白名单)。"""
    fname = request.args.get("file", "").strip()
    allowed = {
        "holdings.json", "stocknote.json", "trip.json", "desktop_pet.json",
        "health_check.json", "smart_order.json", "market_brief.json",
        "kpattern.json", "etf.json", "sector.json",
        "trading_agents.json", "code_teacher.json", "theme.json",
        "futures_events.json", "spread_cache.json",
        "futures_SHFE_SP.json", "futures_SHFE_CU.json",
        "futures_CZCE_FG.json", "futures_CZCE_SA.json", "futures_CZCE_SR.json",
        "futures_DCE_JD.json", "futures_DCE_EG.json",
    }
    if fname not in allowed:
        return jsonify({"ok": False, "error": "文件不在白名单: %s" % fname}), 400
    try:
        fpath = os.path.join(DATA_DIR, fname)
        mtime = _file_mtime(fname)
        data = _load_static(fname)
        return jsonify({"ok": True, "rows": data, "updated": mtime})
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "文件不存在: %s" % fname}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]}), 500


@app.route("/api/futures_events", methods=["GET"])
def api_futures_events():
    """期货/库存事件时间轴数据源(离线样本)。
       参数 exchange / symbol(均做安全清洗); 返回该品种事件数组(内置研究样本)。
       前端 futures-inventory 时间轴会合并 内置 + 后端 + 用户标注 三类事件。"""
    exchange = safe_code(request.args.get("exchange", ""), 16)
    symbol = safe_code(request.args.get("symbol", ""), 16)
    key = "%s:%s" % (exchange, symbol)
    try:
        data = _load_static("futures_events.json")
        events = data.get(key, [])
    except FileNotFoundError:
        events = []
    except Exception:
        events = []
    return jsonify({"ok": True, "offline": OFFLINE_MODE, "key": key, "events": events})


def _load_static(fname):
    """从 backend/data/ 读 JSON 文件(项目内真实结构化数据)，进程内带 mtime 失效缓存。"""
    cached = _static_cache.get(fname)
    if cached is not None:
        mtime, data = cached
        p = os.path.join(DATA_DIR, fname)
        if os.path.isfile(p) and os.path.getmtime(p) == mtime:
            return data
    p = os.path.join(DATA_DIR, fname)
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    _static_cache[fname] = (os.path.getmtime(p), data)
    return data


def _file_mtime(fname):
    """返回 data/ 下文件的真实修改时间(用作数据新鲜度 updated)，无则返回 None。"""
    p = os.path.join(DATA_DIR, fname)
    if os.path.isfile(p):
        return datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")
    return None


@app.route("/api/futures_spread", methods=["GET"])
def api_futures_spread():
    """期货跨期价差与期限结构分析。
    参数:
      variety   品种代码(如 sp / IF / cu)
      monthA    近月合约月份(YYMM, 如 2505)
      monthB    远月合约月份(YYMM, 如 2509)
      ytype     price|index; 股指默认 index, 其它默认 price
      start/end 日期区间(YYYY-MM-DD, 可选)
    返回:
      data 中每个点含 {date, priceA, priceB, spread, y};
      spread = priceA - priceB, 可正可负;
      y 为 Y 轴目标(商品=近月价, 股指=对应现货指数)。
    """
    variety = safe_code(request.args.get("variety", "sp"), 12)
    monthA = safe_code(request.args.get("monthA", "2505"), 8)
    monthB = safe_code(request.args.get("monthB", "2509"), 8)
    ytype = request.args.get("ytype", "")
    start = cap_len(request.args.get("start", ""), 10)
    end = cap_len(request.args.get("end", ""), 10)

    if not variety:
        return jsonify({"ok": False, "error": "variety 不能为空"}), 400
    if not monthA or not monthB:
        return jsonify({"ok": False, "error": "monthA 与 monthB 不能为空"}), 400
    if monthA == monthB:
        return jsonify({"ok": False, "error": "monthA 与 monthB 不能相同"}), 400

    # 股指默认看指数，商品默认看价格
    if ytype not in ("price", "index"):
        ytype = "index" if variety in _INDEX_UNDERLYING else "price"

    ok, err = _validate_range(start, end)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400

    # 真实优先: 非 OFFLINE_MODE 时尝试 akshare 真抓两合约算价差; 失败回退合成样本。
    # offline 动态: 真实成功=False(前端标"真实数据"), 回退=True(标"离线样本")。
    if not OFFLINE_MODE:
        real = _safe_real_spread(variety, monthA, monthB, ytype, start, end)
        if real:
            data, offline = real, False
        else:
            data = _sample_spread_series(variety, monthA, monthB, ytype, start, end)
            offline = True
    else:
        data = _sample_spread_series(variety, monthA, monthB, ytype, start, end)
        offline = True

    if len(data) > 2:
        corr_val = pearson([x["spread"] for x in data], [x["y"] for x in data])
    else:
        corr_val = 0.0

    return jsonify({
        "ok": True,
        "offline": offline,
        "variety": variety,
        "monthA": monthA,
        "monthB": monthB,
        "ytype": ytype,
        "y_label": _INDEX_UNDERLYING.get(variety, {}).get("name", "近月价格" if ytype == "price" else "指数"),
        "corr": round(corr_val, 3),
        "data": data,
    })


# 端点注册表: index 与 health 共用, 避免两处清单漂移(R3 DRY)
ENDPOINTS = [
    "/api/health", "/api/futures", "/api/refresh", "/api/inventory_overview", "/api/eia_crude", "/api/corr_top", "/api/quote", "/api/shepherd",
    "/api/search", "/api/etf", "/api/sector",
    "/api/data", "/api/futures_events", "/api/futures_spread",
    "/api/llm", "/api/data_status",
    "/api/futures_chain",
]


@app.route("/api/health", methods=["GET"])
def api_health():
    """轻量存活检查: 前端/监控可轮询确认后端在线与模式。
       返回 offline 标志、端点数、data 目录静态文件清单(供排查数据源是否就绪)。"""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    data_files = sorted(f for f in os.listdir(data_dir)
                        if f.endswith(".json")) if os.path.isdir(data_dir) else []
    return jsonify({
        "ok": True, "offline": OFFLINE_MODE, "status": "up",
        "service": "flask-data-hub",
        "endpoints": len(ENDPOINTS),
        "data_files": data_files,
        "auto_refresh": REFRESH_STATE,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.route("/api/data_status", methods=["GET"])
def api_data_status():
    """数据新鲜度总览: 每个期货缓存的最新数据日期 / 距今天数 / 记录数 + 整体滞后统计。
       回答「数据到底更新到哪天了」——部署后一眼可判断自动刷新是否真的生效,
       而不必逐个品种点开看。stale_count 用于快速识别超过 2 个发布周期的滞后品种。"""
    items = []
    for fp in sorted(glob.glob(os.path.join(DATA_DIR, "futures_*.json"))):
        base = os.path.basename(fp)
        m = re.match(r"futures_(SHFE|DCE|CZCE|INE)_(.+)\.json", base)
        if not m:
            continue
        ex, sy = m.group(1), m.group(2)
        latest, count = None, 0
        try:
            with open(fp, "r", encoding="utf-8") as f:
                rows = json.load(f)
            if isinstance(rows, list):
                count = len(rows)
                dates = [r.get("date") for r in rows if isinstance(r, dict) and r.get("date")]
                if dates:
                    latest = max(dates)
        except Exception:
            pass
        age = None
        if latest:
            try:
                age = (datetime.now().date() - datetime.strptime(latest, "%Y-%m-%d").date()).days
            except Exception:
                age = None
        items.append({"exchange": ex, "symbol": sy, "file": base,
                      "latest_date": latest, "age_days": age, "records": count})
    ages = [i["age_days"] for i in items if i["age_days"] is not None]
    return jsonify({
        "ok": True,
        "count": len(items),
        "with_data": len(ages),
        "newest_age_days": min(ages) if ages else None,
        "oldest_age_days": max(ages) if ages else None,
        "avg_age_days": round(sum(ages) / len(ages), 1) if ages else None,
        "stale_count": sum(1 for a in ages if a > 14),   # >2 个发布周期(库存按周发布)视为滞后
        "auto_refresh": REFRESH_STATE,
        "items": items,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.route("/api/info", methods=["GET"])
def api_info():
    """后端服务信息(原 / 端点, 现迁移到 /api/info 以免与前端托管冲突)。"""
    return jsonify({
        "service": "期库镜/价格预警/牧羊人/黑天鹅/ETF/板块/期货价差/TradingAgents/主题/代码老师 统一后端",
        "offline": OFFLINE_MODE,
        "endpoints": ENDPOINTS,
        "frontend_served": True,
        "hint": "打开站点根路径 / 即进入微应用大厅; 各 App 默认走同源 API。",
    })


# ───────── 前端托管: 部署时后端顺带 serve 全部单文件 App(同源, 免 CORS/免手填地址) ─────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    norm = (path or "").replace("\\", "/")
    # 安全: 拒绝目录穿越 / 隐藏文件 / 后端源码 / 版本库 / 构建脚本
    if ".." in norm or norm.startswith(".") or "/." in norm:
        return abort(403)
    if norm in _DENY_FILES or any(norm.startswith(p) for p in _DENY_PREFIXES):
        return abort(403)
    # 根级脚本 / 日志 / 临时文件一律不托管(见 _DENY_ROOT_SUFFIXES 注释)
    if "/" not in norm and norm.endswith(_DENY_ROOT_SUFFIXES):
        return abort(403)
    if not norm:
        return send_from_directory(APP_ROOT, "index.html")
    full = os.path.join(APP_ROOT, norm)
    if os.path.isfile(full):
        return send_from_directory(APP_ROOT, norm)
    return abort(404)


# ───────── 黑天鹅事件库(公开历史梳理, 2008-2026) ─────────
BLACKSWAN_EVENTS = [
    {"date":"2007-10-16","cat":"macro","sev":"high","title":"2007–08 美国次贷危机爆发",
     "type":"系统性利空","impact":"上证 6124 见顶 → 2008-10-28 跌至 1664，最大跌幅约 72.8%",
     "desc":"美国次贷危机引发全球金融海啸，雷曼 2008-09 破产；A股单年暴跌，90% 投资者亏损。"},
    {"date":"2015-06-12","cat":"macro","sev":"high","title":"2015 杠杆牛崩塌 / 股灾",
     "type":"系统性利空","impact":"5178 见顶，8-26 见底 2850，17 个交易日跌 35%；8-24 单日 2187 只个股跌停",
     "desc":"清理场外配资触发去杠杆螺旋，千股跌停/千股停牌频发，国家队入场救市。"},
    {"date":"2018-03-23","cat":"macro","sev":"high","title":"特朗普对华加征关税（贸易战）",
     "type":"系统性利空","impact":"单日上证 -3.39%；6-19 再 -3.78%；全年最低 2449（10-19），2018 全年 -24.6%",
     "desc":"美对 500 亿→2000 亿美元中国商品加征 25%/10% 关税，出口链盈利预期恶化，外资撤离。"},
    {"date":"2020-02-03","cat":"macro","sev":"high","title":"新冠疫情冲击（春节后首日）",
     "type":"系统性利空","impact":"上证 -7.72%，深成指 -8.45%，两市超 3000 只个股跌停",
     "desc":"COVID-19 引发全球风险资产抛售，避险资产受捧；随后流动性宽松推动修复。"},
    {"date":"2022-03-07","cat":"macro","sev":"mid","title":"俄乌冲突 + 美联储加息",
     "type":"系统性利空","impact":"上证单日 -2.17% 失守 3400；3 月累计 -6.07%，创业板年内 -19.96%",
     "desc":"俄乌冲突推升大宗与滞涨预期，北向 3 月净流出约 461 亿，高估值成长承压。"},
    {"date":"2008-04-24","cat":"macro","sev":"low","title":"印花税下调（政策底信号）",
     "type":"系统性利空","impact":"2008-04-24 印花税 3‰→1‰，大盘短线反弹约 20%",
     "desc":"反向案例：极端悲观中的政策对冲信号，9-18 救市三策后 9-20 指数涨停。"},
]

BLACKSWAN_STOCKS = [
    {"code":"600518","name":"康美药业","risk":"业绩雷/财务造假",
     "signal":"2016–2018 虚增货币资金 887 亿、营收 291 亿",
     "impact":"市值从 1300 亿跌至 187 亿，2021 特别代表人诉讼赔 24.59 亿",
     "time":"2018-12 立案 / 2021-11 判决"},
    {"code":"300104","name":"乐视网","risk":"业绩雷/退市",
     "signal":"资金链断裂、巨亏，2020-05 退市",
     "impact":"创业板市值曾居首，退市时投资者损失惨重","time":"2019-04 暂停上市"},
    {"code":"—","name":"异常波动样本","risk":"监管异动",
     "signal":"连续涨停后收到交易所问询函/停牌核查",
     "impact":"游资炒作标的，监管函件往往预示估值回归风险","time":"动态"},
    {"code":"—","name":"大股东减持","risk":"减持/立案",
     "signal":"重要股东大额减持 + 低位质押平仓线逼近",
     "impact":"减持叠加质押风险，易引发个股闪崩","time":"动态"},
]


# ───────── 黑天鹅风险关键词(业绩雷/监管异动/减持/立案) ─────────
RISK_KEYWORDS = {
    "业绩雷": ["亏损", "预亏", "预减", "商誉减值", "计提", "巨亏", "业绩变脸", "下修"],
    "监管异动": ["立案调查", "行政处罚", "问询函", "监管函", "通报批评", "警示函", "停牌核查", "ST", "*ST", "退市"],
    "减持": ["减持", "大股东减持", "清仓式减持", "质押平仓", "股份冻结"],
    "诉讼": ["诉讼", "仲裁", "索赔", "处罚"],
    "其他": ["异常波动", "关注函", "风险提示"],
}

# ───────── 业绩雷通用预警框架: 四维信号词库 ─────────
# 维度1 季度增速趋势: 增速放缓/下滑/不及预期的前瞻词
# 维度2 盈利质量与预期差: 毛利率/机构预测/预告区间
# 维度3 隐性风险: 现金流/应收/财务费用/募投
# 维度4 公司行为/产业链: 减持/高管/延期/问询/上下游
EARNINGS_FRAMEWORK = {
    "增速趋势": ["增速放缓", "同比下滑", "环比下降", "增收不增利", "业绩下滑", "增速下降",
              "负增长", "低于预期", "不及预期", "Q4下滑", "单季下滑"],
    "盈利质量与预期差": ["毛利率下滑", "毛利率下降", "净利率下滑", "机构下调", "下调评级",
                     "下调预期", "下调预测", "目标价下调", "预告下限", "一致预期", "盈利预警"],
    "隐性风险": ["现金流恶化", "经营现金流", "应收账款", "回款风险", "财务费用", "汇率波动",
             "募投延期", "项目延期", "存货激增", "资产减值"],
    "公司行为与产业链": ["减持", "高管减持", "股份冻结", "募投项目延期", "问询函", "关注函",
                     "订单下滑", "下游低迷", "产业链低迷", "延后", "延期"],
}


def _scan_text_for_risk(text):
    """返回命中风险的类别列表。"""
    hits = []
    for cat, kws in RISK_KEYWORDS.items():
        if any(kw in text for kw in kws):
            hits.append(cat)
    return hits


def _scan_earnings_framework(text):
    """按四维业绩预警框架扫描一段文本, 返回 {维度: [命中词...]}。"""
    found = {}
    for dim, kws in EARNINGS_FRAMEWORK.items():
        hit = [kw for kw in kws if kw in text]
        if hit:
            found[dim] = hit
    return found


def _earnings_forecast_build(dim_hits, name):
    """把四维命中汇总成结构化业绩雷预期结果。"""
    dims = list(EARNINGS_FRAMEWORK.keys())
    signals = []
    for d in dims:
        kws = dim_hits.get(d, [])
        # 每维度命中词越多, 权重越高(1~3档)
        level = "高" if len(kws) >= 3 else ("中" if len(kws) >= 1 else "无")
        signals.append({
            "dim": d,
            "level": level,
            "hits": kws,
            "weight": {"高": 3, "中": 1, "无": 0}[level],
        })
    total_w = sum(s["weight"] for s in signals)
    # 综合业绩雷概率: 四维合计权重 / 12(满档 4*3) 折算
    prob = min(95, round(total_w / 12 * 100))
    grade = "🔴 高概率业绩雷" if prob >= 60 else ("🟡 中等预警" if prob >= 25 else "🟢 暂无明显信号")
    summary = "基于四维框架扫描: " + (
        "、".join("%s(%s)" % (s["dim"], s["level"]) for s in signals if s["level"] != "无")
        or "未命中已知预警词") + "。"
    return {
        "name": name,
        "signals": signals,
        "prob": prob,
        "grade": grade,
        "summary": summary,
    }


def _blackswan_scan_offline(code):
    """离线: 返回演示扫描(命中若干风险以演示 UI)。"""
    # 离线演示样本: 一条"恒铭达式"通用业绩雷复盘文本(不绑定具体个股)
    demo_text = (
        "2026 半年度业绩预告: 净利润同比增长 16.43%, 较去年 62.36% 增速大幅放缓, "
        "Q4 单季度净利同比下滑 15%, 增收不增利。毛利率下滑 1.52 个百分点至 31.98%, "
        "应收账款占净利润比重高达 244.55%, 回款风险不容忽视。受汇率波动影响财务费用激增, "
        "经营性现金流环比由正转负。多家机构下调预期: 华创下调至 6.11 亿、东吴下调至 6.17 亿。 "
        "公司中报预告增长区间下限远低于市场一致预期, 募投项目延期至 2027 年。"
    )
    dim_hits = _scan_earnings_framework(demo_text)
    earnings = _earnings_forecast_build(dim_hits, "(离线演示样本)")
    return {
        "name": "(离线演示)",
        "notices": [
            {"date": "2026-08-10", "title": "关于收到中国证监会立案告知书的公告", "risk": ["监管异动"], "sev": "high"},
            {"date": "2026-08-05", "title": "2026 半年度业绩预亏公告（净利润同比下滑 60%）", "risk": ["业绩雷"], "sev": "mid"},
        ],
        "news": [
            {"date": "2026-08-08", "title": "大股东拟减持不超过 5% 股份", "risk": ["减持"], "sev": "mid"},
        ],
        "earnings_forecast": earnings,
        "risk_score": 72, "risk_level": "中危",
        "summary": "离线演示: 命中监管立案 + 业绩预亏 + 减持三类风险; 业绩雷框架命中 %d 个维度。"
                   % len([s for s in earnings["signals"] if s["level"] != "无"]),
    }


def _blackswan_scan(code):
    """真抓个股公告/业绩预告/新闻, 做风险识别与评分。"""
    import akshare as ak
    out = {"name": code, "notices": [], "news": [], "risk_score": 0,
           "risk_level": "平稳", "summary": ""}
    severities = []
    # 1) 个股公告 stock_individual_notice_report(code, indicator="最新公告")
    try:
        df = ak.stock_individual_notice_report(symbol=code, indicator="最新公告")
        if df is not None and not df.empty:
            cols = df.columns.tolist()
            title_col = next((c for c in cols if "公告" in c or "标题" in c or "title" in str(c).lower()), cols[0])
            date_col = next((c for c in cols if "日期" in c or "date" in str(c).lower()), cols[-2] if len(cols) > 1 else cols[0])
            for _, r in df.head(15).iterrows():
                t = str(r[title_col])
                hits = _scan_text_for_risk(t)
                if hits:
                    sev = "high" if ("监管异动" in hits or "业绩雷" in hits) else "mid"
                    out["notices"].append({
                        "date": str(r[date_col])[:10], "title": t,
                        "risk": hits, "sev": sev})
                    severities.append(sev)
    except Exception as e:
        logger.warning("公告抓取失败: %s", str(e)[:100])
    # 2) 业绩预告 stock_yjyg_em(最新一期) — 检测预亏/预减
    try:
        from datetime import datetime as _dt
        period = "%d" % _dt.now().year + ("0630" if _dt.now().month <= 9 else "1231")
        df = ak.stock_yjyg_em(date=period)
        if df is not None and not df.empty:
            row = df[df["股票代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                txt = " ".join([str(r.get(c, "")) for c in df.columns])
                hits = _scan_text_for_risk(txt)
                if hits:
                    sev = "high" if "业绩雷" in hits else "mid"
                    out["news"].append({
                        "date": period, "title": "业绩预告: " + str(r.get("业绩变动原因", ""))[:40],
                        "risk": hits, "sev": sev})
                    severities.append(sev)
    except Exception as e:
        logger.warning("业绩预告抓取失败: %s", str(e)[:100])
    # 3) 个股新闻 stock_news_em
    try:
        df = ak.stock_news_em(symbol=code)
        if df is not None and not df.empty:
            for _, r in df.head(10).iterrows():
                t = str(r.get("新闻标题", ""))
                hits = _scan_text_for_risk(t)
                if hits:
                    sev = "mid"
                    out["news"].append({
                        "date": str(r.get("发布时间", ""))[:10], "title": t,
                        "risk": hits, "sev": sev})
                    severities.append(sev)
    except Exception as e:
        logger.warning("新闻抓取失败: %s", str(e)[:100])

    high = severities.count("high"); mid = severities.count("mid")
    out["risk_score"] = min(100, high * 35 + mid * 12)
    out["risk_level"] = "高危" if high >= 1 else ("中危" if mid >= 1 else "平稳")
    out["summary"] = "命中 %d 条高危、%d 条中危公告/新闻/财报信号。" % (high, mid)

    # ── 业绩雷通用预警框架扫描(四维) ──
    all_text = " ".join(
        [n["title"] for n in out["notices"]] + [n["title"] for n in out["news"]]
    )
    dim_hits = _scan_earnings_framework(all_text)
    out["earnings_forecast"] = _earnings_forecast_build(dim_hits, code)
    return out


# ───────── 新 App 数据端点: TradingAgents / 小狐狸讲代码 / 主题工坊 ─────────
@app.route("/api/llm", methods=["POST"])
def api_llm():
    """统一 LLM 调用网关(供所有前端 App 复用)。
    请求体: {"system":str, "user":str, "model":str?, "stream":bool?}
    非流式返回: {"ok":true, "source":..., "cached":bool, "content":str}
    流式返回: text/event-stream, 逐条 data: {"content":...} / 结束 data: [DONE]
    失败返回: 502 JSON(前端据此降级本地演示), 绝不抛 500。"""
    try:
        body = request.get_json(force=True, silent=True) or {}
    except Exception:
        body = {}
    system = cap_len(str(body.get("system", "") or ""), 4000)
    user = cap_len(str(body.get("user", "") or ""), 8000)
    model = cap_len(str(body.get("model", "") or ""), 64) or LLM_MODEL
    use_stream = bool(body.get("stream", False))
    if not (system or user):
        return jsonify({"ok": False, "error": "system 与 user 不能都为空"}), 400
    messages = _llm_messages(system, user)
    cache_key = _hl.md5((model + json.dumps(messages, ensure_ascii=False)).encode("utf-8")).hexdigest()

    if not use_stream:
        cached = _llm_cache_get(cache_key)
        if cached is not None:
            return jsonify({"ok": True, "source": LLM_PROVIDER, "cached": True, "content": cached})
        try:
            content = _llm_call(messages, model)
        except _uerr.URLError as e:
            return jsonify({"ok": False,
                            "error": "LLM 后端不可达：%s（确认 Ollama 已启动或已配置 API Key）"
                            % str(getattr(e, "reason", e))[:160]}), 502
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:200]}), 502
        _llm_cache_set(cache_key, content)
        return jsonify({"ok": True, "source": LLM_PROVIDER, "cached": False, "content": content})

    def gen():
        acc = []
        try:
            for chunk in _llm_call_stream(messages, model):
                acc.append(chunk)
                yield "data: " + json.dumps({"content": chunk}, ensure_ascii=False) + "\n\n"
            _llm_cache_set(cache_key, "".join(acc))
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"error": str(e)[:200]}, ensure_ascii=False) + "\n\n"
    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ───────── 搜索: 股票/基金/期货/指数 ─────────
SEARCH_SAMPLE = {
    "stock": [
        # 核心权重 / 行业龙头（覆盖主要宽基成分）
        {"code": "600519", "name": "贵州茅台", "market": "沪A"},
        {"code": "601318", "name": "中国平安", "market": "沪A"},
        {"code": "600036", "name": "招商银行", "market": "沪A"},
        {"code": "601166", "name": "兴业银行", "market": "沪A"},
        {"code": "600276", "name": "恒瑞医药", "market": "沪A"},
        {"code": "600887", "name": "伊利股份", "market": "沪A"},
        {"code": "601899", "name": "紫金矿业", "market": "沪A"},
        {"code": "600900", "name": "长江电力", "market": "沪A"},
        {"code": "601012", "name": "隆基绿能", "market": "沪A"},
        {"code": "600030", "name": "中信证券", "market": "沪A"},
        {"code": "601398", "name": "工商银行", "market": "沪A"},
        {"code": "601857", "name": "中国石油", "market": "沪A"},
        {"code": "600028", "name": "中国石化", "market": "沪A"},
        {"code": "601888", "name": "中国中免", "market": "沪A"},
        {"code": "688981", "name": "中芯国际", "market": "科创板"},
        {"code": "000001", "name": "平安银行", "market": "深A"},
        {"code": "000858", "name": "五粮液", "market": "深A"},
        {"code": "300750", "name": "宁德时代", "market": "创业板"},
        {"code": "000333", "name": "美的集团", "market": "深A"},
        {"code": "002594", "name": "比亚迪", "market": "深A"},
        {"code": "000651", "name": "格力电器", "market": "深A"},
        {"code": "300059", "name": "东方财富", "market": "创业板"},
        {"code": "002415", "name": "海康威视", "market": "深A"},
        {"code": "000725", "name": "京东方A", "market": "深A"},
        {"code": "300760", "name": "迈瑞医疗", "market": "创业板"},
        {"code": "002714", "name": "牧原股份", "market": "深A"},
        {"code": "000063", "name": "中兴通讯", "market": "深A"},
        {"code": "002475", "name": "立讯精密", "market": "深A"},
        {"code": "300124", "name": "汇川技术", "market": "创业板"},
        {"code": "002230", "name": "科大讯飞", "market": "深A"},
        # 常见活跃个股
        {"code": "601138", "name": "工业富联", "market": "沪A"},
        {"code": "600809", "name": "山西汾酒", "market": "沪A"},
        {"code": "603259", "name": "药明康德", "market": "沪A"},
        {"code": "601628", "name": "中国人寿", "market": "沪A"},
        {"code": "600009", "name": "上海机场", "market": "沪A"},
        {"code": "601668", "name": "中国建筑", "market": "沪A"},
        {"code": "600438", "name": "通威股份", "market": "沪A"},
        {"code": "002304", "name": "洋河股份", "market": "深A"},
        {"code": "000568", "name": "泸州老窖", "market": "深A"},
        {"code": "300015", "name": "爱尔眼科", "market": "创业板"},
        {"code": "002352", "name": "顺丰控股", "market": "深A"},
        {"code": "002241", "name": "歌尔股份", "market": "深A"},
    ],
    "fund": [
        # 主流宽基 ETF
        {"code": "510300", "name": "华泰柏瑞沪深300ETF", "type": "ETF"},
        {"code": "510500", "name": "南方中证500ETF", "type": "ETF"},
        {"code": "159915", "name": "易方达创业板ETF", "type": "ETF"},
        {"code": "510050", "name": "华夏上证50ETF", "type": "ETF"},
        {"code": "588000", "name": "华夏科创50ETF", "type": "ETF"},
        {"code": "512100", "name": "南方中证1000ETF", "type": "ETF"},
        {"code": "563300", "name": "华夏中证2000ETF", "type": "ETF"},
        {"code": "515800", "name": "汇添富中证800ETF", "type": "ETF"},
        # 行业 / 主题 ETF
        {"code": "512660", "name": "国泰中证军工ETF", "type": "ETF"},
        {"code": "512010", "name": "易方达医药卫生ETF", "type": "ETF"},
        {"code": "515030", "name": "华夏中证新能源ETF", "type": "ETF"},
        {"code": "512480", "name": "国联安中证半导体ETF", "type": "ETF"},
        {"code": "159928", "name": "汇添富中证主要消费ETF", "type": "ETF"},
        {"code": "512690", "name": "鹏华中证酒ETF", "type": "ETF"},
        {"code": "518880", "name": "华安黄金ETF", "type": "ETF"},
        {"code": "513100", "name": "国泰纳斯达克100ETF", "type": "ETF"},
        {"code": "513500", "name": "博时标普500ETF", "type": "ETF"},
        {"code": "511380", "name": "博时可转债ETF", "type": "ETF"},
        # LOF / 指数 / 联接
        {"code": "161725", "name": "招商中证白酒指数", "type": "LOF"},
        {"code": "163406", "name": "兴全合润混合", "type": "LOF"},
        {"code": "011609", "name": "国泰中证钢铁ETF联接", "type": "指数"},
        {"code": "110011", "name": "易方达中小盘混合", "type": "基金"},
        {"code": "161903", "name": "万家行业优选混合", "type": "LOF"},
        {"code": "005827", "name": "易方达蓝筹精选混合", "type": "基金"},
    ],
    "futures": [
        # 上期所 SHFE
        {"code": "cu", "name": "沪铜", "exchange": "SHFE"},
        {"code": "al", "name": "沪铝", "exchange": "SHFE"},
        {"code": "zn", "name": "沪锌", "exchange": "SHFE"},
        {"code": "pb", "name": "沪铅", "exchange": "SHFE"},
        {"code": "ni", "name": "沪镍", "exchange": "SHFE"},
        {"code": "sn", "name": "沪锡", "exchange": "SHFE"},
        {"code": "au", "name": "沪金", "exchange": "SHFE"},
        {"code": "ag", "name": "沪银", "exchange": "SHFE"},
        {"code": "rb", "name": "螺纹钢", "exchange": "SHFE"},
        {"code": "hc", "name": "热轧卷板", "exchange": "SHFE"},
        {"code": "ss", "name": "不锈钢", "exchange": "SHFE"},
        {"code": "ao", "name": "氧化铝", "exchange": "SHFE"},
        {"code": "bc", "name": "国际铜", "exchange": "SHFE"},
        {"code": "ru", "name": "天然橡胶", "exchange": "SHFE"},
        {"code": "nr", "name": "20号胶", "exchange": "SHFE"},
        {"code": "bu", "name": "沥青", "exchange": "SHFE"},
        {"code": "fu", "name": "燃料油", "exchange": "SHFE"},
        # 大商所 DCE
        {"code": "i", "name": "铁矿石", "exchange": "DCE"},
        {"code": "j", "name": "焦炭", "exchange": "DCE"},
        {"code": "jm", "name": "焦煤", "exchange": "DCE"},
        {"code": "m", "name": "豆粕", "exchange": "DCE"},
        {"code": "y", "name": "豆油", "exchange": "DCE"},
        {"code": "p", "name": "棕榈油", "exchange": "DCE"},
        {"code": "c", "name": "玉米", "exchange": "DCE"},
        {"code": "cs", "name": "玉米淀粉", "exchange": "DCE"},
        {"code": "pp", "name": "聚丙烯", "exchange": "DCE"},
        {"code": "v", "name": "PVC", "exchange": "DCE"},
        {"code": "l", "name": "聚乙烯", "exchange": "DCE"},
        {"code": "jd", "name": "鸡蛋", "exchange": "DCE"},
        {"code": "eg", "name": "乙二醇", "exchange": "DCE"},
        {"code": "eb", "name": "苯乙烯", "exchange": "DCE"},
        {"code": "pg", "name": "液化石油气", "exchange": "DCE"},
        {"code": "lh", "name": "生猪", "exchange": "DCE"},
        {"code": "rr", "name": "粳米", "exchange": "DCE"},
        {"code": "sp", "name": "纸浆", "exchange": "DCE"},
        # 郑商所 CZCE
        {"code": "TA", "name": "PTA", "exchange": "CZCE"},
        {"code": "MA", "name": "甲醇", "exchange": "CZCE"},
        {"code": "SR", "name": "白糖", "exchange": "CZCE"},
        {"code": "CF", "name": "棉花", "exchange": "CZCE"},
        {"code": "FG", "name": "玻璃", "exchange": "CZCE"},
        {"code": "RM", "name": "菜粕", "exchange": "CZCE"},
        {"code": "OI", "name": "菜油", "exchange": "CZCE"},
        {"code": "UR", "name": "尿素", "exchange": "CZCE"},
        {"code": "SA", "name": "纯碱", "exchange": "CZCE"},
        {"code": "PF", "name": "短纤", "exchange": "CZCE"},
        {"code": "PK", "name": "花生", "exchange": "CZCE"},
        {"code": "AP", "name": "苹果", "exchange": "CZCE"},
        {"code": "CJ", "name": "红枣", "exchange": "CZCE"},
        {"code": "PX", "name": "对二甲苯", "exchange": "CZCE"},
        {"code": "SH", "name": "烧碱", "exchange": "CZCE"},
        # 上海国际能源交易中心 INE
        {"code": "sc", "name": "原油", "exchange": "INE"},
        {"code": "lu", "name": "低硫燃料油", "exchange": "INE"},
        # 中金所 CFFEX
        {"code": "IF", "name": "沪深300股指期货", "exchange": "CFFEX"},
        {"code": "IC", "name": "中证500股指期货", "exchange": "CFFEX"},
        {"code": "IH", "name": "上证50股指期货", "exchange": "CFFEX"},
        {"code": "IM", "name": "中证1000股指期货", "exchange": "CFFEX"},
        {"code": "T", "name": "10年期国债期货", "exchange": "CFFEX"},
        {"code": "TF", "name": "5年期国债期货", "exchange": "CFFEX"},
        {"code": "TS", "name": "2年期国债期货", "exchange": "CFFEX"},
        # 外盘 LME
        {"code": "lme_cu", "name": "LME铜", "exchange": "LME"},
        {"code": "lme_al", "name": "LME铝", "exchange": "LME"},
        {"code": "lme_zn", "name": "LME锌", "exchange": "LME"},
        # 外盘 COMEX
        {"code": "comex_au", "name": "COMEX黄金", "exchange": "COMEX"},
        {"code": "comex_cu", "name": "COMEX铜", "exchange": "COMEX"},
    ],
    "index": [
        # 宽基
        {"code": "sh000001", "name": "上证指数", "exchange": "SH"},
        {"code": "sz399001", "name": "深证成指", "exchange": "SZ"},
        {"code": "sz399006", "name": "创业板指", "exchange": "SZ"},
        {"code": "sh000300", "name": "沪深300", "exchange": "SH"},
        {"code": "sh000905", "name": "中证500", "exchange": "SH"},
        {"code": "sh000016", "name": "上证50", "exchange": "SH"},
        {"code": "sh000852", "name": "中证1000", "exchange": "SH"},
        {"code": "sh000688", "name": "科创50", "exchange": "SH"},
        {"code": "sz399330", "name": "深证100", "exchange": "SZ"},
        {"code": "sh000015", "name": "红利指数", "exchange": "SH"},
        # 行业 / 主题
        {"code": "sh000932", "name": "中证消费", "exchange": "SH"},
        {"code": "sh000991", "name": "中证医药", "exchange": "SH"},
        {"code": "sz399967", "name": "中证军工", "exchange": "SZ"},
        {"code": "sz399997", "name": "中证白酒", "exchange": "SZ"},
        {"code": "sh000993", "name": "中证金融", "exchange": "SH"},
        {"code": "sz399808", "name": "中证新能源", "exchange": "SZ"},
        # 海外
        {"code": "usixic", "name": "纳斯达克综合指数", "exchange": "US"},
        {"code": "usspx", "name": "标普500", "exchange": "US"},
        {"code": "ushsi", "name": "恒生指数", "exchange": "HK"},
        {"code": "usdji", "name": "道琼斯工业指数", "exchange": "US"},
        {"code": "jpn225", "name": "日经225", "exchange": "JP"},
    ],
}


@app.route("/api/search", methods=["GET"])
def api_search():
    """搜索股票/基金/期货/指数。参数 q(关键词/代码) type(stock|fund|futures|index)。"""
    q = cap_len(request.args.get("q", ""), 64)
    typ = request.args.get("type", "stock")
    if typ not in SEARCH_SAMPLE:
        return jsonify({"ok": False, "error": "type 不支持: %s" % typ}), 400
    if not q:
        return jsonify({"ok": True, "offline": OFFLINE_MODE, "results": SEARCH_SAMPLE[typ],
                        "note": "未传入关键词, 返回热门示例。"})
    ql = q.lower()
    if OFFLINE_MODE:
        if not q:
            # 未传关键词: 返回热门示例, 引导用户选择
            res = SEARCH_SAMPLE[typ]
        else:
            # 传了关键词但无匹配 -> 返回空(而非降级为全量), 前端据此提示"无结果"
            res = [r for r in SEARCH_SAMPLE[typ]
                   if ql in (str(r["code"]).lower()) or ql in (str(r["name"]).lower())]
        return jsonify({"ok": True, "offline": True, "type": typ, "results": res,
                        "note": "离线示例库。有网环境 OFFLINE_MODE=False 即真实全市场搜索。"})
    try:
        results = []
        if typ == "stock":
            df = ak.stock_zh_a_spot_em()
            df["_k"] = df["代码"].astype(str) + df["名称"].astype(str)
            sub = df[df["_k"].str.lower().str.contains(ql, na=False)].head(20)
            results = [{"code": r["代码"], "name": r["名称"], "price": r.get("最新价"),
                        "chg": r.get("涨跌幅"), "market": ""} for _, r in sub.iterrows()]
        elif typ == "fund":
            df = ak.fund_etf_spot_em()
            df["_k"] = df["代码"].astype(str) + df["名称"].astype(str)
            sub = df[df["_k"].str.lower().str.contains(ql, na=False)].head(20)
            results = [{"code": r["代码"], "name": r["名称"], "price": r.get("最新价"),
                        "chg": r.get("涨跌幅"), "type": "ETF"} for _, r in sub.iterrows()]
        elif typ == "futures":
            try:
                df = ak.futures_zh_daily_sina(symbol="cu0")  # 触发 ak 可用性
                # 用东方财富期货行情全表做真实模糊搜索
                fdf = ak.futures_zh_spot_em()
                fdf["_k"] = fdf["代码"].astype(str) + fdf["名称"].astype(str)
                sub = fdf[fdf["_k"].str.lower().str.contains(ql, na=False)].head(20)
                results = [{"code": r["代码"], "name": r["名称"],
                            "exchange": r.get("交易所", "")} for _, r in sub.iterrows()]
            except Exception:
                for r in SEARCH_SAMPLE["futures"]:
                    if ql in str(r["code"]).lower() or ql in str(r["name"]).lower():
                        results.append(r)
        elif typ == "index":
            try:
                # A股指数：东方财富指数行情全表模糊搜
                idf = ak.index_zh_a_spot_em()
                idf["_k"] = idf["代码"].astype(str) + idf["名称"].astype(str)
                sub = idf[idf["_k"].str.lower().str.contains(ql, na=False)].head(20)
                results = [{"code": r["代码"], "name": r["名称"], "exchange": "SH" if str(r["代码"]).startswith("sh") else "SZ"} for _, r in sub.iterrows()]
                # 海外指数（恒生/纳指/标普等）补充映射命中
                for r in SEARCH_SAMPLE["index"]:
                    if ql in str(r["code"]).lower() or ql in str(r["name"]).lower():
                        if not any(x["code"] == r["code"] for x in results):
                            results.append(r)
            except Exception:
                for r in SEARCH_SAMPLE["index"]:
                    if ql in str(r["code"]).lower() or ql in str(r["name"]).lower():
                        results.append(r)
        return jsonify({"ok": True, "offline": False, "type": typ, "results": results})
    except Exception as e:
        logger.warning("搜索失败, 回退离线: %s", str(e)[:120])
        res = [r for r in SEARCH_SAMPLE[typ] if ql in str(r["code"]).lower() or ql in str(r["name"]).lower()]
        return jsonify({"ok": True, "offline": True, "type": typ, "results": res or SEARCH_SAMPLE[typ],
                        "note": "真实搜索失败, 回退离线库: " + str(e)[:100]})


# ───────── 自动刷新调度器: 部署后后台周期重抓真实库存, 缓存永不过期 ─────────
# 解决「凭一个网站能否拿到最新数据」: 服务器自己定时刷新, 访客无需任何操作。
# 即使刷新失败(数据源限流/服务器IP被挡), 也保留上一次真实缓存, 绝不回退合成样本。
REFRESH_STATE = {
    "running": False, "last_run": None, "last_ok": 0, "last_fail": 0, "cycle_sec": None,
    "runs": 0,                 # 已完成刷新轮次
    "consecutive_fails": 0,    # 连续出现失败品种的轮次数(0 表示上一轮全成功)
    "next_run": None,          # 下次刷新时间(便于监控判断调度器是否卡死)
    "last_duration_sec": None, # 上一轮耗时
    "last_errors": [],         # 最近失败品种明细(最多 10 条), 用于诊断数据源/网络故障
    "degraded": [],            # 因连续失败被降频、本轮跳过的品种("EXCH:SYM")
}
_AUTO_REFRESH_STARTED = False
_SYMBOL_FAILS = {}             # {(exchange, symbol): 连续失败次数}


def _tracked_futures_symbols():
    """扫描 data/ 下所有 futures_<exch>_<sym>.json, 返回 [(exchange, symbol), ...]"""
    out = []
    try:
        for fp in glob.glob(os.path.join(DATA_DIR, "futures_*.json")):
            base = os.path.basename(fp)
            m = re.match(r"futures_(SHFE|DCE|CZCE|INE)_(.+)\.json", base)
            if m:
                out.append((m.group(1), m.group(2)))
    except Exception:
        pass
    seen, uniq = set(), []
    for ex, sy in out:
        k = (ex, sy.upper())
        if k not in seen:
            seen.add(k)
            uniq.append((ex, sy))
    return uniq


def _auto_refresh_loop():
    import traceback
    hours = float(os.environ.get("REFRESH_HOURS", "6"))
    interval = max(0.1, hours) * 3600.0
    REFRESH_STATE["cycle_sec"] = interval
    while True:
        started = _t.time()
        try:
            if OFFLINE_MODE:
                # 沙箱禁网: 不发起真实抓取, 仅维持调度器存活(部署时设 OFFLINE_MODE=False 即生效)
                REFRESH_STATE["running"] = True
            else:
                symbols = _tracked_futures_symbols()
                ok = fail = 0
                errors, skipped = [], []
                runs = REFRESH_STATE.get("runs", 0)
                for ex, sy in symbols:
                    key = (ex, sy.upper())
                    # 降频: 连续失败 >=3 次的品种(长期无数据源/已退市等)每 3 轮才重试一次,
                    # 避免每轮把时间耗在注定失败的品种上, 也减少对数据源的无谓请求。
                    if _SYMBOL_FAILS.get(key, 0) >= 3 and (runs % 3 != 0):
                        skipped.append(ex + ":" + sy)
                        continue
                    try:
                        r = _bake_inv_em.refresh_one(ex, sy, verbose=False)
                        if r and r.get("ok"):
                            ok += 1
                            _SYMBOL_FAILS[key] = 0
                        else:
                            fail += 1
                            _SYMBOL_FAILS[key] = _SYMBOL_FAILS.get(key, 0) + 1
                            if len(errors) < 10:
                                errors.append({"exchange": ex, "symbol": sy,
                                               "error": str((r or {}).get("error") or "refresh returned not-ok")[:200]})
                    except Exception as e:
                        fail += 1
                        _SYMBOL_FAILS[key] = _SYMBOL_FAILS.get(key, 0) + 1
                        if len(errors) < 10:
                            errors.append({"exchange": ex, "symbol": sy, "error": str(e)[:200]})
                    _t.sleep(2)  # 礼貌间隔, 避免触发数据源限流
                REFRESH_STATE["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                REFRESH_STATE["last_ok"] = ok
                REFRESH_STATE["last_fail"] = fail
                REFRESH_STATE["last_errors"] = errors
                REFRESH_STATE["degraded"] = skipped
                REFRESH_STATE["last_duration_sec"] = round(_t.time() - started, 1)
                REFRESH_STATE["runs"] = runs + 1
                REFRESH_STATE["consecutive_fails"] = (REFRESH_STATE.get("consecutive_fails", 0) + 1) if fail else 0
                REFRESH_STATE["running"] = True
        except Exception:
            REFRESH_STATE["running"] = False
            traceback.print_exc()
        # 无论本轮成败都排定下次刷新时间, 便于外部监控判断调度器是否卡死
        REFRESH_STATE["next_run"] = (datetime.now() + timedelta(seconds=interval)).strftime("%Y-%m-%d %H:%M:%S")
        _t.sleep(interval)


def start_auto_refresh():
    global _AUTO_REFRESH_STARTED
    if _AUTO_REFRESH_STARTED:
        return
    _AUTO_REFRESH_STARTED = True
    t = threading.Thread(target=_auto_refresh_loop, daemon=True)
    t.start()


if __name__ == "__main__":
    # 部署: 绑定 0.0.0.0 并读取环境变量 PORT(云平台注入, 如 Railway/Fly/CloudBase/轻量服务器)
    # 本地默认 8787。前端由本进程同源托管, 打开 http://<host>:<port>/ 即进入大厅。
    # 启动即开启后台自动刷新(REFRESH_HOURS 可调, 默认 6h); 访客无需任何操作即可看到最新真实数据。
    port = int(os.environ.get("PORT", 8787))
    start_auto_refresh()
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
