# -*- coding: utf-8 -*-
"""生成 16 个消费真实后端端点的单文件微应用 (R3~R18)。
每个 App: 一致深色主题 + 加载/错误态 + 共享 test/run.js + 大厅注册。
用法: python tools/gen_microapps.py   (幂等: 仅写入不存在的文件; 用 --force 覆盖)
"""
import os, json, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 渲染模式:
#   rows -> 数组对象渲染为表格(自动探测 rows/data/items/list/result)
#   kv   -> 扁平对象渲染为键值卡片
#   auto -> 先试 rows 再试 kv
# loader:
#   single -> 单次 GET (可带 inputs 拼 query)
#   multi  -> 取某个 inputs 的多值(token 由 sep 切分)循环 GET 同一端点并合并 rows
SPECS = [
    dict(dir="data-status-dash", name="数据状态总览", ico="📊", cat="tool", tag="数据覆盖/质量",
         desc="消费 /api/data_status，总览各数据源覆盖、质量与新鲜度。",
         endpoint="/api/data_status", loader="single", mode="kv"),
    dict(dir="spread-viewer", name="期货跨期价差", ico="📐", cat="fin", tag="跨期价差",
         desc="消费 /api/futures_spread，展示各品种近月-远月跨期价差。",
         endpoint="/api/futures_spread", loader="single", mode="rows"),
    dict(dir="holdings-health", name="持仓体检", ico="💼", cat="fin", tag="持仓估值",
         desc="批量消费 /api/quote，输入一组代码展示实时价/涨跌/占比。",
         endpoint="/api/quote", loader="multi", multiInput="codes",
         inputs=[dict(id="codes", label="持仓代码", ph="600519, 000001, 300750", default="600519, 000001", sep=",")],
         mode="rows"),
    dict(dir="sector-heat", name="板块强弱热力", ico="🔥", cat="fin", tag="板块涨跌",
         desc="消费 /api/sector，按涨跌幅着色展示板块强弱热力。",
         endpoint="/api/sector", loader="single", mode="rows"),
    dict(dir="quote-board", name="实时报价板", ico="💹", cat="fin", tag="个股实时报价",
         desc="消费 /api/quote，输入代码查看实时价格/涨跌/量。",
         endpoint="/api/quote", loader="single",
         inputs=[dict(id="code", label="代码", ph="600519", default="600519")],
         mode="kv"),
    dict(dir="eia-watch", name="原油库存周报", ico="🛢️", cat="fin", tag="EIA 原油",
         desc="消费 /api/eia_crude，展示美国原油库存周度数据。",
         endpoint="/api/eia_crude", loader="single", mode="rows"),
    dict(dir="inventory-watch", name="库存概览", ico="📦", cat="fin", tag="期货库存",
         desc="消费 /api/inventory_overview，展示主要品种库存概览。",
         endpoint="/api/inventory_overview", loader="single", mode="rows"),
    dict(dir="variety-screener", name="期货品种筛选", ico="🧮", cat="fin", tag="品种列表",
         desc="消费 /api/futures_varieties，浏览/筛选期货品种。",
         endpoint="/api/futures_varieties", loader="single", mode="rows"),
    dict(dir="corr-explorer", name="相关性探测器", ico="🔗", cat="fin", tag="相关性",
         desc="消费 /api/corr_top，展示相关性最强的标的对。",
         endpoint="/api/corr_top", loader="single", mode="rows"),
    dict(dir="futures-events", name="期货事件台", ico="🗓️", cat="fin", tag="期货事件",
         desc="消费 /api/futures_events，展示期货品种事件。",
         endpoint="/api/futures_events", loader="single", mode="rows"),
    dict(dir="market-mood", name="市场情绪台", ico="🧭", cat="fin", tag="牧羊人指数",
         desc="消费 /api/shepherd，展示市场情绪/牧羊人指数。",
         endpoint="/api/shepherd", loader="single", mode="auto"),
    dict(dir="itinerary-view", name="行程规划台", ico="🧳", cat="tool", tag="行程生成",
         desc="消费 /api/itinerary/generate，展示行程规划结果。",
         endpoint="/api/itinerary/generate", loader="single",
         inputs=[dict(id="q", label="目的地/偏好", ph="上海 3 天 亲子", default="上海 3 天")],
         mode="auto"),
    dict(dir="futures-board", name="期货总览", ico="📈", cat="fin", tag="期货行情",
         desc="消费 /api/futures，展示期货品种总览行情。",
         endpoint="/api/futures", loader="single", mode="rows"),
    dict(dir="data-explorer", name="数据浏览器", ico="🗂️", cat="tool", tag="数据条目",
         desc="消费 /api/data，浏览后端数据条目。",
         endpoint="/api/data", loader="single", mode="auto"),
    dict(dir="search-box", name="智能搜索", ico="🔎", cat="tool", tag="全局搜索",
         desc="消费 /api/search，输入关键词搜索。",
         endpoint="/api/search", loader="single",
         inputs=[dict(id="q", label="关键词", ph="茅台 利润", default="茅台")],
         mode="rows"),
    # —— 本轮新增: 消费 POST 端点(统一 LLM 网关 / 库存刷新) ——
    dict(dir="market-qa", name="AI 投研问答", ico="💬", cat="tool", tag="LLM 多轮问答",
         desc="消费 /api/llm 统一大模型网关，支持多轮对话（保留历史上下文）、人设切换、停止、清空、复制与 Markdown 渲染（后端可接 Ollama / DeepSeek / OpenAI）。",
         endpoint="/api/llm", loader="post", postKind="llm-multi", goLabel="发送",
         system="你是一个专业的 A股与期货投研助手，回答简洁、用中文、给出可操作的信息；涉及具体标的时注明数据来源与不确定性。",
         models=[
           {"id":"general","label":"通用投研","system":"你是一个专业的 A股与期货投研助手，回答简洁、用中文、给出可操作的信息；涉及具体标的时注明数据来源与不确定性。"},
           {"id":"risk","label":"风控视角","system":"你是一名严谨的量化风控分析师，聚焦持仓风险、回撤与不确定性，指出关键风险点并给出对冲/止损思路。"},
           {"id":"trader","label":"交易员视角","system":"你是一名实战派交易员，侧重趋势、量价、情绪与择时，给出偏行动导向的短线/波段建议。"},
         ],
         inputs=[dict(id="q", label="你的问题", ph="最近市场情绪如何？白酒板块还能拿吗？",
                      default="最近 A股 市场情绪如何，后市怎么看？", area=True)],
         mode="kv"),
    dict(dir="inv-refresh", name="库存刷新台", ico="🔄", cat="fin", tag="库存刷新",
         desc="消费 /api/refresh，触发单个期货品种的真实库存刷新（东方财富），查看刷新结果与最新库存。",
         endpoint="/api/refresh", loader="post", postKind="args-batch", goLabel="刷新",
         batchSymbols=[{"symbol":"cu","exchange":"SHFE"},{"symbol":"rb","exchange":"SHFE"},
                      {"symbol":"au","exchange":"SHFE"},{"symbol":"i","exchange":"DCE"},
                      {"symbol":"TA","exchange":"CZCE"},{"symbol":"m","exchange":"DCE"}],
         inputs=[dict(id="symbol", label="品种代码", ph="cu", default="cu"),
                 dict(id="exchange", label="交易所", ph="SHFE", default="SHFE")],
         mode="kv"),
]

# 每个 App 的定制可视化:
#   render -> 注入 renderCustom(j)，处理整体 JSON（对象型数据）
#   rows   -> 注入 renderCustomRows(rows)，处理数组行（表格型数据）
# 约定: 命中并渲染就 return true；数据形状不符必须 return false，由通用表格/键值兜底。
# 注意: 这些 JS 体通过 .replace 注入（在 .format 之后），因此花括号无需转义。
CUSTOM = {
    "sector-heat": dict(rows=r'''
    var pk = pickKey(rows[0], ["涨跌幅", "pct", "change", "chg", "涨跌"]);
    if(!pk) return false;
    var nk = pickKey(rows[0], ["名称", "板块", "name", "行业", "sector"]);
    var vals = rows.map(function(r){ return numOf(r[pk]); }).filter(function(v){ return v != null; });
    if(!vals.length) return false;
    var mx = 0; vals.forEach(function(v){ mx = Math.max(mx, Math.abs(v)); }); if(!mx) mx = 1;
    var isPct = String(pk).indexOf("%") >= 0 || String(pk).indexOf("幅") >= 0 || String(pk).toLowerCase().indexOf("pct") >= 0;
    out.innerHTML = '<div class="heat">' + rows.map(function(r){
      var v = numOf(r[pk]); if(v == null) return "";
      var a = Math.min(1, Math.abs(v) / mx);
      var col = v > 0 ? "rgba(255,77,79," + (0.16 + 0.74 * a) + ")"
              : (v < 0 ? "rgba(0,212,134," + (0.16 + 0.74 * a) + ")" : "var(--panel2)");
      var nm = nk ? r[nk] : pk;
      return '<div class="tile" style="background:' + col + '" title="' + esc(nm) + ' ' + fmtNum(v) + '">' +
             '<div class="tn">' + esc(nm) + '</div><div class="tv">' + fmtNum(v) + (isPct ? "%" : "") + '</div></div>';
    }).join("") + '</div><div class="note">热力图：颜色深浅 = 涨跌强度（红涨绿跌），共 ' + rows.length + ' 个板块</div>';
    return true;'''),
    "market-mood": dict(render=r'''
    var obj = (j && j.ok && typeof j.data === "object" && !Array.isArray(j.data)) ? j.data : j;
    if(!obj || typeof obj !== "object" || Array.isArray(obj)) return false;
    var keys = Object.keys(obj).filter(function(k){ return k !== "ok" && typeof obj[k] === "number"; });
    if(keys.length < 2) return false;
    var mx = 0; keys.forEach(function(k){ mx = Math.max(mx, Math.abs(obj[k])); }); if(!mx) mx = 1;
    out.innerHTML = '<div class="kvg">' + keys.map(function(k){
      var v = obj[k], pct = Math.min(100, Math.abs(v) / mx * 100);
      var col = v > 0 ? "var(--red)" : (v < 0 ? "var(--green)" : "var(--accent)");
      return '<div class="kv"><div class="k">' + esc(k) + '</div>' +
             '<div class="v" style="color:' + col + '">' + fmtNum(v) + '</div>' +
             '<div class="track"><span style="width:' + pct + '%;background:' + col + '"></span></div></div>';
    }).join("") + '</div><div class="note">条形 = 相对最大绝对值的强度（红正向 / 绿负向）</div>';
    return true;'''),
    "eia-watch": dict(rows=r'''
    var dk = pickKey(rows[0], ["date", "日期", "周", "time", "period"]);
    var vk = pickKey(rows[0], ["库存", "stock", "crude", "value", "值", "amount", "数量"]);
    if(!vk) return false;
    var vs = rows.map(function(r){ return numOf(r[vk]); }).filter(function(v){ return v != null; });
    if(vs.length < 2) return false;
    var mx = Math.max.apply(null, vs), mn = Math.min.apply(null, vs), rg = (mx - mn) || 1;
    out.innerHTML = '<div class="chart">' + rows.map(function(r){
      var v = numOf(r[vk]); if(v == null) return "";
      var h = 6 + (v - mn) / rg * 94;
      var d = dk ? String(r[dk] == null ? "" : r[dk]) : "";
      return '<div class="cb" title="' + esc(d) + ' ' + fmtNum(v) + '">' +
             '<span style="height:' + h + '%"></span><i>' + esc(d.slice(-5)) + '</i></div>';
    }).join("") + '</div><div class="note">共 ' + vs.length + ' 期 · 最大 ' + fmtNum(mx) +
      ' · 最小 ' + fmtNum(mn) + '（柱高按区间归一化）</div>';
    return true;'''),
    "spread-viewer": dict(rows=r'''
    var vk = pickKey(rows[0], ["价差", "spread", "diff", "差"]);
    if(!vk) return false;
    var nk = pickKey(rows[0], ["品种", "symbol", "name", "合约", "名称"]);
    var vs = rows.map(function(r){ return numOf(r[vk]); }).filter(function(v){ return v != null; });
    if(!vs.length) return false;
    var mx = 0; vs.forEach(function(v){ mx = Math.max(mx, Math.abs(v)); }); if(!mx) mx = 1;
    out.innerHTML = '<div class="dv">' + rows.map(function(r){
      var v = numOf(r[vk]); if(v == null) return "";
      var w = Math.abs(v) / mx * 50, pos = v >= 0;
      var col = pos ? "var(--red)" : "var(--green)";
      return '<div class="dvr"><span class="dvn">' + esc(nk ? r[nk] : "") + '</span>' +
        '<span class="dvt"><i style="width:' + w + '%;background:' + col + ';' + (pos ? "left:50%" : "right:50%") + '"></i></span>' +
        '<span class="dvv ' + (pos ? "up" : "down") + '">' + fmtNum(v) + '</span></div>';
    }).join("") + '</div><div class="note">中线为 0；右侧红 = 正价差，左侧绿 = 负价差，长度按最大绝对值归一</div>';
    return true;'''),
    "corr-explorer": dict(rows=r'''
    var vk = pickKey(rows[0], ["corr", "相关", "coef", "r", "value", "值"]);
    if(!vk) return false;
    var nk = pickKey(rows[0], ["pair", "标的", "name", "名称", "symbol", "对"]);
    var vs = rows.map(function(r){ return numOf(r[vk]); }).filter(function(v){ return v != null; });
    if(!vs.length) return false;
    var mx = 0; vs.forEach(function(v){ mx = Math.max(mx, Math.abs(v)); });
    var denom = mx <= 1 ? 1 : mx;
    out.innerHTML = '<div class="dv">' + rows.map(function(r){
      var v = numOf(r[vk]); if(v == null) return "";
      var w = Math.abs(v) / denom * 50, pos = v >= 0;
      var col = pos ? "var(--red)" : "var(--green)";
      return '<div class="dvr"><span class="dvn">' + esc(nk ? r[nk] : "") + '</span>' +
        '<span class="dvt"><i style="width:' + w + '%;background:' + col + ';' + (pos ? "left:50%" : "right:50%") + '"></i></span>' +
        '<span class="dvv ' + (pos ? "up" : "down") + '">' + fmtNum(v) + '</span></div>';
    }).join("") + '</div><div class="note">中线为 0；右侧红 = 正相关，左侧绿 = 负相关' +
      (mx <= 1 ? '（相关系数已归一到 ±1）' : '（按最大绝对值归一）') + '</div>';
    return true;'''),
    "futures-events": dict(rows=r'''
    var tk = pickKey(rows[0], ["事件", "event", "title", "标题", "name", "名称"]);
    if(!tk) return false;
    var dk = pickKey(rows[0], ["date", "日期", "时间", "time", "day"]);
    out.innerHTML = '<div class="tl">' + rows.map(function(r){
      var d = dk ? String(r[dk] == null ? "" : r[dk]) : "";
      var t = String(r[tk] == null ? "" : r[tk]);
      var rest = Object.keys(r).filter(function(k){ return k !== dk && k !== tk; })
        .map(function(k){ return '<span class="tlm">' + esc(k) + ': ' + cell(r[k]) + '</span>'; }).join("");
      return '<div class="tli"><span class="tld">' + esc(d) + '</span><span class="tlc"></span>' +
             '<div class="tlb"><b>' + esc(t) + '</b><div>' + rest + '</div></div></div>';
    }).join("") + '</div>';
    return true;'''),
    "inventory-watch": dict(rows=r'''
    var vk = pickKey(rows[0], ["库存", "stock", "inv", "仓单", "量"]);
    if(!vk) return false;
    var nk = pickKey(rows[0], ["品种", "symbol", "name", "名称"]);
    var vs = rows.map(function(r){ return numOf(r[vk]); }).filter(function(v){ return v != null; });
    if(!vs.length) return false;
    var mx = Math.max.apply(null, vs) || 1;
    out.innerHTML = '<div class="dv">' + rows.map(function(r){
      var v = numOf(r[vk]); if(v == null) return "";
      return '<div class="dvr"><span class="dvn">' + esc(nk ? r[nk] : "") + '</span>' +
        '<span class="dvt"><i style="width:' + (v / mx * 100) + '%;left:0;background:var(--accent)"></i></span>' +
        '<span class="dvv">' + fmtNum(v) + '</span></div>';
    }).join("") + '</div><div class="note">条形 = 相对最大库存量（' + fmtNum(mx) + '）</div>';
    return true;'''),
    "variety-screener": dict(rows=r'''
    var kw = String(window.__vsFilter || "").trim().toLowerCase();
    var rs = rows.filter(function(r){
      if(!kw) return true;
      return JSON.stringify(r).toLowerCase().indexOf(kw) >= 0;
    });
    out.innerHTML = '<div class="flt"><input id="vsF" placeholder="筛选品种 / 代码 / 交易所…" value="' +
      esc(window.__vsFilter || "") + '"></div>' + tableHtml(rs) +
      '<div class="note">命中 ' + rs.length + ' / ' + rows.length + ' 个品种</div>';
    var el = document.getElementById("vsF");
    if(el) el.addEventListener("input", function(e){ window.__vsFilter = e.target.value; renderRows(rows); });
    return true;'''),
    "data-explorer": dict(rows=r'''
    var kw = String(window.__deFilter || "").trim().toLowerCase();
    var rs = rows.filter(function(r){
      if(!kw) return true;
      return JSON.stringify(r).toLowerCase().indexOf(kw) >= 0;
    });
    out.innerHTML = '<div class="flt"><input id="deF" placeholder="筛选数据条目…" value="' +
      esc(window.__deFilter || "") + '"></div>' + tableHtml(rs) +
      '<div class="note">命中 ' + rs.length + ' / ' + rows.length + ' 条</div>';
    var el = document.getElementById("deF");
    if(el) el.addEventListener("input", function(e){ window.__deFilter = e.target.value; renderRows(rows); });
    return true;'''),
    "search-box": dict(rows=r'''
    var tk = pickKey(rows[0], ["title", "标题", "name", "名称", "code", "代码"]);
    if(!tk) return false;
    var sk = pickKey(rows[0], ["snippet", "摘要", "content", "内容", "desc", "描述", "summary"]);
    out.innerHTML = '<div class="res">' + rows.map(function(r){
      var t = String(r[tk] == null ? "" : r[tk]);
      var s = sk ? String(r[sk] == null ? "" : r[sk]) : "";
      return '<div class="rc"><div class="rt">' + esc(t) + '</div>' +
             (s ? '<div class="rs">' + esc(s) + '</div>' : "") + '</div>';
    }).join("") + '</div><div class="note">共 ' + rows.length + ' 条结果</div>';
    return true;'''),
    "quote-board": dict(render=r'''
    var obj = (j && j.ok && typeof j.data === "object" && !Array.isArray(j.data)) ? j.data : j;
    if(!obj || typeof obj !== "object" || Array.isArray(obj)) return false;
    var pk = pickKey(obj, ["price", "价格", "现价", "last", "最新"]);
    if(pk == null || numOf(obj[pk]) == null) return false;
    var ck = pickKey(obj, ["pct", "涨跌幅", "幅", "change", "涨跌"]);
    var nmk = pickKey(obj, ["name", "名称", "code", "代码"]);
    var cv = ck ? numOf(obj[ck]) : null;
    var col = cv == null ? "var(--text)" : (cv > 0 ? "var(--red)" : (cv < 0 ? "var(--green)" : "var(--sub)"));
    var head = '<div class="big">' +
      (nmk ? '<div class="cn" style="color:var(--sub)">' + esc(obj[nmk]) + '</div>' : "") +
      '<div class="bp" style="color:' + col + '">' + fmtNum(numOf(obj[pk])) + '</div>' +
      (cv != null ? '<div class="bc" style="color:' + col + '">' + fmtNum(cv) +
        (String(ck).indexOf("幅") >= 0 ? "%" : "") + '</div>' : "") + '</div>';
    var keys = Object.keys(obj).filter(function(k){ return k !== "ok" && k !== pk; });
    var rest = keys.length ? '<div class="kvg">' + keys.map(function(k){
      var v = obj[k];
      var cls = (typeof v === "number" && v > 0) ? "up" : ((typeof v === "number" && v < 0) ? "down" : "");
      return '<div class="kv"><div class="k">' + esc(k) + '</div><div class="v ' + cls + '">' + cell(v) + '</div></div>';
    }).join("") + '</div>' : "";
    out.innerHTML = head + rest;
    return true;'''),
    "holdings-health": dict(rows=r'''
    var pk = pickKey(rows[0], ["price", "价格", "现价", "last"]);
    if(!pk) return false;
    var ck = pickKey(rows[0], ["pct", "涨跌幅", "幅", "change", "涨跌"]);
    var codeK = pickKey(rows[0], ["code", "代码", "symbol"]) || "__code";
    var mx = 0;
    rows.forEach(function(r){ var v = ck ? numOf(r[ck]) : null; if(v != null) mx = Math.max(mx, Math.abs(v)); });
    if(!mx) mx = 1;
    out.innerHTML = '<div class="dv">' + rows.map(function(r){
      var v = ck ? numOf(r[ck]) : null, px = numOf(r[pk]);
      var w = v == null ? 0 : Math.abs(v) / mx * 50, pos = (v == null ? true : v >= 0);
      var col = v == null ? "var(--panel2)" : (pos ? "var(--red)" : "var(--green)");
      var nm = r[codeK] != null ? r[codeK] : "";
      return '<div class="dvr"><span class="dvn">' + esc(nm) + '</span>' +
        '<span class="dvt"><i style="width:' + w + '%;background:' + col + ';' + (pos ? "left:50%" : "right:50%") + '"></i></span>' +
        '<span class="dvv ' + (pos ? "up" : "down") + '">' + (px != null ? fmtNum(px) + " " : "") +
        (v != null ? fmtNum(v) : "–") + '</span></div>';
    }).join("") + '</div>' + tableHtml(rows) +
      '<div class="note">条形 = 涨跌幅相对强度（红涨绿跌）；下方为完整字段</div>';
    return true;'''),
    "data-status-dash": dict(render=r'''
    var obj = (j && j.ok && typeof j.data === "object" && !Array.isArray(j.data)) ? j.data : j;
    if(!obj || typeof obj !== "object" || Array.isArray(obj)) return false;
    var keys = Object.keys(obj).filter(function(k){ return k !== "ok"; });
    if(!keys.length) return false;
    out.innerHTML = '<div class="cards">' + keys.map(function(k){
      var v = obj[k], col = "var(--text)";
      if(typeof v === "boolean") col = v ? "var(--green)" : "var(--red)";
      else if(typeof v === "number") col = v > 0 ? "var(--accent)" : (v < 0 ? "var(--red)" : "var(--sub)");
      var dot = (typeof v === "boolean")
        ? '<span class="dot ' + (v ? "ok" : "bad") + '" style="display:inline-block;margin-right:6px"></span>' : "";
      return '<div class="cd"><div class="cn">' + esc(k) + '</div>' +
             '<div class="cv" style="color:' + col + '">' + dot + cell(v) + '</div></div>';
    }).join("") + '</div>';
    return true;'''),
    "itinerary-view": dict(render=r'''
    var obj = (j && j.ok && typeof j.data === "object") ? j.data : j;
    if(!obj || typeof obj !== "object") return false;
    var arr = null;
    ["days", "plan", "itinerary", "steps", "items", "result"].forEach(function(k){
      if(!arr && Array.isArray(obj[k])) arr = obj[k];
    });
    if(!arr) return false;
    out.innerHTML = '<div class="tl">' + arr.map(function(it, i){
      var t = (it && typeof it === "object") ? (it.title || it.name || it.day || ("第 " + (i + 1) + " 天")) : String(it);
      var rest = (it && typeof it === "object")
        ? Object.keys(it).filter(function(k){ return ["title", "name", "day"].indexOf(k) < 0; })
            .map(function(k){ return '<span class="tlm">' + esc(k) + ': ' + cell(it[k]) + '</span>'; }).join("")
        : "";
      return '<div class="tli"><span class="tld">Day ' + (i + 1) + '</span><span class="tlc"></span>' +
             '<div class="tlb"><b>' + esc(t) + '</b><div>' + rest + '</div></div></div>';
    }).join("") + '</div>';
    return true;'''),
    "futures-board": dict(rows=r'''
    var nk = pickKey(rows[0], ["名称", "品种", "name", "symbol", "合约"]);
    var pk = pickKey(rows[0], ["price", "价格", "现价", "last", "收盘"]);
    if(!nk || !pk) return false;
    var ck = pickKey(rows[0], ["pct", "涨跌幅", "幅", "change", "涨跌"]);
    out.innerHTML = '<div class="cards">' + rows.map(function(r){
      var v = ck ? numOf(r[ck]) : null, px = numOf(r[pk]);
      var col = v == null ? "var(--text)" : (v > 0 ? "var(--red)" : (v < 0 ? "var(--green)" : "var(--sub)"));
      return '<div class="cd"><div class="cn">' + esc(r[nk]) + '</div>' +
        '<div class="cv" style="color:' + col + '">' + (px != null ? fmtNum(px) : "–") + '</div>' +
        '<div class="cc" style="color:' + col + '">' + (v != null ? fmtNum(v) : "") + '</div></div>';
    }).join("") + '</div>' + tableHtml(rows);
    return true;'''),
    "market-qa": dict(render=r'''
    var jj = (j && typeof j === "object") ? j : null;
    if(!jj || typeof jj.content !== "string") return false;
    var src = jj.source ? String(jj.source) : "";
    var cached = jj.cached ? "（缓存）" : "";
    out.innerHTML = '<div class="qa"><div class="qat"><div class="qaa">' + esc(jj.content) + '</div>' +
      (src ? '<div class="qas">来源: ' + esc(src) + cached + '</div>' : '') +
      '</div></div>';
    return true;''',
    css=r'''
    .qa{margin-top:8px;display:flex;flex-direction:column;gap:12px;max-height:62vh;overflow:auto}
    .qat{display:flex;flex-direction:column;gap:4px}
    .qaq{align-self:flex-end;background:var(--accent);color:#fff;padding:9px 13px;border-radius:14px 14px 4px 14px;max-width:85%;white-space:pre-wrap;line-height:1.6;font-size:14px;word-break:break-word}
    .qaa{align-self:flex-start;background:var(--panel);border:1px solid var(--line);color:var(--text);padding:11px 14px;border-radius:14px 14px 14px 4px;max-width:92%;white-space:pre-wrap;line-height:1.7;font-size:14px;word-break:break-word}
    .qaw{color:var(--amber);font-style:italic}
    .qas{margin-top:8px;color:var(--sub);font-size:12px;align-self:flex-start}
    .qaa code{background:rgba(124,140,255,.16);padding:1px 5px;border-radius:5px;font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
    .qaa.qaerr{border-color:var(--red);color:var(--red)}
    .qatools{margin-top:6px;display:flex;gap:6px}
    .mini{background:var(--panel2);color:var(--sub);border:1px solid var(--line);border-radius:7px;padding:2px 9px;font-size:11px;cursor:pointer}
    .mini:hover{color:var(--text)}'''),
    "inv-refresh": dict(render=r'''
    var jj = (j && typeof j === "object") ? j : null;
    if(!jj || typeof jj.ok !== "boolean") return false;
    var okc = jj.ok ? "var(--green)" : "var(--red)";
    var rows = (jj.rows && Array.isArray(jj.rows)) ? jj.rows : null;
    var html = '<div class="rb" style="border-left:4px solid ' + okc + '">' +
      '<div class="rbt" style="color:' + okc + '">' + (jj.ok ? "刷新成功" : "刷新失败") + '</div>' +
      '<div class="rbm">品种: ' + esc(jj.exchange || "") + ':' + esc(jj.symbol || "") + '</div>' +
      (jj.last_inventory != null ? '<div class="rbm">最新库存: ' + fmtNum(jj.last_inventory) + '</div>' : '') +
      (jj.filled != null ? '<div class="rbm">填充: ' + fmtNum(jj.filled) + '</div>' : '') +
      (jj.msg ? '<div class="rbm">消息: ' + esc(jj.msg) + '</div>' : '') +
      '</div>';
    if(rows) html += tableHtml(rows.slice(0, 12));
    out.innerHTML = html;
    return true;''',
    css=r'''
    .rb{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-top:8px}
    .rbt{font-weight:700;font-size:15px;margin-bottom:6px}
    .rbm{color:var(--sub);font-size:13px;margin:2px 0}'''),
}

TPL = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · AppHub</title>
<style>
  :root{{--bg:#0f1020;--panel:#1a1b2e;--panel2:#23243a;--line:#2e2f4a;--text:#e8e9f3;
    --sub:#9aa0c0;--accent:#7c8cff;--green:#00d486;--red:#ff6b6b;--amber:#ffb454;--chip:#2a2c46;}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--text);
    font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;padding:22px}}
  h1{{font-size:20px;margin:0 0 4px}}
  .sub{{color:var(--sub);margin:0 0 16px;font-size:13px}}
  a.hubhome{{position:fixed;left:12px;top:12px;z-index:50;text-decoration:none;
    background:var(--chip);color:var(--text);padding:5px 10px;border-radius:8px;font-size:12px}}
  .controls{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;align-items:flex-end}}
  .controls label{{display:flex;flex-direction:column;gap:4px;color:var(--sub);font-size:12px}}
  .controls input{{background:var(--panel);border:1px solid var(--line);color:var(--text);
    border-radius:8px;padding:8px 10px;font-size:13px;min-width:180px}}
  .controls textarea{{background:var(--panel);border:1px solid var(--line);color:var(--text);
    border-radius:8px;padding:8px 10px;font-size:13px;min-width:320px;min-height:64px;font-family:inherit;resize:vertical}}
  button{{background:var(--accent);color:#fff;border:0;border-radius:9px;padding:8px 16px;
    font-size:13px;cursor:pointer;font-weight:600}}
  button.ghost{{background:var(--panel2);color:var(--text);border:1px solid var(--line)}}
  .status{{display:inline-flex;align-items:center;gap:7px;font-size:13px;margin-bottom:14px;
    padding:6px 12px;border-radius:9px;background:var(--panel);border:1px solid var(--line)}}
  .dot{{width:9px;height:9px;border-radius:50%}}
  .dot.ok{{background:var(--green)}} .dot.bad{{background:var(--red)}} .dot.wait{{background:var(--amber)}}
  #out{{margin-top:6px}}
  .tbl{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
    border-radius:12px;overflow:hidden;margin-top:8px}}
  .tbl th,.tbl td{{padding:8px 11px;text-align:left;border-bottom:1px solid var(--line);font-size:13px;
    vertical-align:top}}
  .tbl th{{color:var(--sub);font-weight:600;background:var(--panel2);position:sticky;top:0}}
  .tbl tr:last-child td{{border-bottom:0}}
  .tbl td.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--accent)}}
  .kvg{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:8px}}
  .kv{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}}
  .kv .k{{color:var(--sub);font-size:12px}} .kv .v{{font-size:16px;margin-top:3px;word-break:break-all}}
  .v.up{{color:var(--red)}} .v.down{{color:var(--green)}}
  .empty{{color:var(--sub);padding:24px;text-align:center}}
  .err{{color:var(--red);padding:14px;border:1px solid var(--red);border-radius:10px;background:rgba(255,107,107,.08)}}
  .note{{margin-top:14px;color:var(--sub);font-size:12px}}
  .bar{{height:6px;border-radius:3px;display:inline-block}}
  /* ---- 定制可视化样式(各 App 按需注入) ---- */
  .heat{{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin-top:8px}}
  .tile{{border-radius:10px;padding:10px;border:1px solid var(--line);min-height:62px;
    display:flex;flex-direction:column;justify-content:space-between}}
  .tile .tn{{font-size:12px;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.45);word-break:break-all}}
  .tile .tv{{font-size:15px;font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.45)}}
  .track{{height:6px;background:var(--panel2);border-radius:3px;margin-top:8px;overflow:hidden}}
  .track span{{display:block;height:100%;border-radius:3px}}
  .chart{{display:flex;align-items:flex-end;gap:3px;height:190px;background:var(--panel);
    border:1px solid var(--line);border-radius:12px;padding:10px;margin-top:8px;overflow-x:auto}}
  .cb{{flex:1;min-width:9px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%}}
  .cb span{{width:100%;background:var(--accent);border-radius:3px 3px 0 0;display:block}}
  .cb i{{font-style:normal;font-size:9px;color:var(--sub);margin-top:4px;white-space:nowrap}}
  .dv{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;margin-top:8px}}
  .dvr{{display:grid;grid-template-columns:110px 1fr 92px;gap:8px;align-items:center;padding:4px 0}}
  .dvn{{font-size:12px;color:var(--sub);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  .dvt{{position:relative;height:12px;background:var(--panel2);border-radius:6px}}
  .dvt:after{{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--line)}}
  .dvt i{{position:absolute;top:0;bottom:0;display:block;border-radius:6px}}
  .dvv{{text-align:right;font-size:12px}}
  .tl{{margin-top:8px}}
  .tli{{display:grid;grid-template-columns:100px 14px 1fr;gap:8px;padding:6px 0}}
  .tld{{font-size:11px;color:var(--sub);font-family:ui-monospace,monospace;padding-top:3px}}
  .tlc{{position:relative;display:flex;justify-content:center}}
  .tlc:before{{content:"";position:absolute;top:14px;bottom:-14px;width:2px;background:var(--line)}}
  .tlc:after{{content:"";position:absolute;top:6px;width:8px;height:8px;border-radius:50%;background:var(--accent);z-index:1}}
  .tlb{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:13px}}
  .tlm{{display:inline-block;margin-right:10px;color:var(--sub);font-size:11px}}
  .flt{{display:flex;gap:8px;margin:8px 0 0}}
  .flt input{{background:var(--panel);border:1px solid var(--line);color:var(--text);
    border-radius:8px;padding:7px 10px;font-size:13px;min-width:220px}}
  .res{{display:grid;gap:8px;margin-top:8px}}
  .rc{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
  .rc .rt{{font-weight:600;margin-bottom:3px}} .rc .rs{{color:var(--sub);font-size:12px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px;margin-top:8px}}
  .cd{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px}}
  .cd .cn{{color:var(--sub);font-size:12px}} .cd .cv{{font-size:20px;font-weight:700;margin-top:4px}}
  .cd .cc{{font-size:12px;margin-top:2px}}
  .big{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px;margin-top:8px}}
  .big .bp{{font-size:34px;font-weight:800;line-height:1.1}} .big .bc{{font-size:15px;margin-top:4px}}
__CUSTOM_CSS__
</style>
</head>
<body>
<a class="hubhome" href="../index.html">🏠 大厅</a>
<h1>{ico} {name}</h1>
<p class="sub">{tag}</p>
<div class="controls" id="controls"></div>
<div class="status"><span id="dot" class="dot bad"></span><span id="statusTxt">未连接</span></div>
<div id="out"></div>
<div class="note">需经 <b>后端</b> 访问（http://&lt;host&gt;:8787/{dir}/）。以 file:// 打开则无法读取数据。</div>

<script>
(function(){{
  function apiBase(){{ return location.protocol === "file:" ? null : location.origin; }}
  var BASE = apiBase();
  var ENDPOINT = "{endpoint}";
  var out = document.getElementById("out");
  var dot = document.getElementById("dot");
  var statusTxt = document.getElementById("statusTxt");
  var inputs = {{}};   // id -> element

  function setStatus(kind, txt){{
    dot.className = "dot " + kind;
    statusTxt.textContent = txt;
  }}
  function esc(s){{
    return String(s==null?"":s).replace(/[&<>"']/g, function(c){{
      return {{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}}[c];
    }});
  }}
  function fmtNum(n){{
    if(n==null||n==="") return "–";
    var x = Number(n); if(isNaN(x)) return esc(n);
    return x.toLocaleString("en-US", {{maximumFractionDigits:4}});
  }}
  function cell(v){{
    if(v==null||v==="") return "–";
    if(typeof v === "number"){{ var cls = v>0?"up":(v<0?"down":""); return '<span class="'+(v>0?"up":(v<0?"down":""))+'">'+fmtNum(v)+'</span>'; }}
    if(typeof v === "object") return '<span class="mono">'+esc(JSON.stringify(v))+'</span>';
    return esc(v);
  }}
  function toRows(j){{
    if(Array.isArray(j)) return j;
    if(j && Array.isArray(j.rows)) return j.rows;
    if(j && Array.isArray(j.data)) return j.data;
    if(j && Array.isArray(j.items)) return j.items;
    if(j && Array.isArray(j.list)) return j.list;
    if(j && j.ok && Array.isArray(j.result)) return j.result;
    return null;
  }}
  function numOf(v){{
    if(typeof v==="number") return isFinite(v)? v : null;
    if(v==null||v==="") return null;
    var x = Number(v); return isNaN(x)? null : x;
  }}
  function pickKey(obj, subs){{
    if(!obj || typeof obj!=="object") return null;
    var ks = Object.keys(obj);
    for(var i=0;i<subs.length;i++){{
      for(var j=0;j<ks.length;j++){{
        if(ks[j].toLowerCase().indexOf(String(subs[i]).toLowerCase())>=0) return ks[j];
      }}
    }}
    return null;
  }}
  function tableHtml(rows){{
    if(!rows || !rows.length) return '<div class="empty">无数据</div>';
    var cols = []; var seen = {{}};
    rows.forEach(function(r){{ if(r && typeof r==="object"){{ Object.keys(r).forEach(function(k){{ if(!seen[k]){{seen[k]=1;cols.push(k);}} }}); }} }});
    if(!cols.length) cols = Object.keys(rows[0]||{{}});
    var html = '<table class="tbl"><thead><tr>'+cols.map(function(c){{return "<th>"+esc(c)+"</th>";}}).join("")+'</tr></thead><tbody>';
    rows.forEach(function(r){{
      html += "<tr>"+cols.map(function(c){{ return "<td>"+cell(r?r[c]:null)+"</td>"; }}).join("")+"</tr>";
    }});
    return html + "</tbody></table>";
  }}
  // 定制渲染钩子: 命中并渲染返回 true, 否则返回 false 由通用表格/键值兜底
  function renderCustom(j){{
__CUSTOM_RENDER__
    return false;
  }}
  function renderCustomRows(rows){{
__CUSTOM_ROWS__
    return false;
  }}
  function renderRows(rows){{
    if(!rows || !rows.length){{ out.innerHTML = '<div class="empty">无数据</div>'; return; }}
    if(renderCustomRows(rows)) return;
    out.innerHTML = tableHtml(rows);
  }}
  function renderKV(j){{
    var obj = (j && j.ok && typeof j.data==="object" && !Array.isArray(j.data)) ? j.data : j;
    if(Array.isArray(j)) obj = {{"items": j.length}};
    var keys = Object.keys(obj||{{}}).filter(function(k){{ return k!=="ok"; }});
    if(!keys.length){{ out.innerHTML = '<div class="empty">无数据</div>'; return; }}
    var html = '<div class="kvg">'+keys.map(function(k){{
      var v = obj[k]; var cls = (typeof v==="number"&&v>0)?"up":((typeof v==="number"&&v<0)?"down":"");
      return '<div class="kv"><div class="k">'+esc(k)+'</div><div class="v '+cls+'">'+cell(v)+'</div></div>';
    }}).join("")+'</div>';
    out.innerHTML = html;
  }}
  function render(mode, j){{
    if(renderCustom(j)) return;
    if("{mode}"==="kv"){{ renderKV(j); return; }}
    if("{mode}"==="rows"){{ var r=toRows(j); if(r){{renderRows(r);return;}} renderKV(j); return; }}
    // auto
    var r=toRows(j); if(r && r.length){{ renderRows(r); return; }} renderKV(j);
  }}
  function buildUrl(params){{
    var u = ENDPOINT; var qs = [];
    Object.keys(params||{{}}).forEach(function(k){{ var v=(params[k]||"").trim(); if(v) qs.push(encodeURIComponent(k)+"="+encodeURIComponent(v)); }});
    return qs.length ? u+"?"+qs.join("&") : u;
  }}
  function drawControls(){{
    var html = "";
    {controls_html}
    document.getElementById("controls").innerHTML = html +
      '<button id="goBtn">{go_label}</button>{extra_buttons}';
    var controlIds = [{control_ids}];
    controlIds.forEach(function(id){{ inputs[id]=document.getElementById(id); }});
    var go = document.getElementById("goBtn");
    go.addEventListener("click", go_);
    var batchBtn = document.getElementById("batchBtn");
    if(batchBtn && typeof batch_ === "function") batchBtn.addEventListener("click", batch_);
    var modelSel = document.getElementById("modelSel");
    if(modelSel && typeof QA_MODELS !== "undefined") modelSel.addEventListener("change", function(){{ QA_MODEL = (QA_MODELS[modelSel.selectedIndex] && QA_MODELS[modelSel.selectedIndex].system) || ""; }});
    var clearBtn = document.getElementById("clearBtn");
    if(clearBtn && typeof QA_HISTORY !== "undefined") clearBtn.addEventListener("click", function(){{ QA_HISTORY=[]; if(typeof saveQA==="function") saveQA(); renderQA(); setStatus("wait","已清空对话"); }});
    var stopBtn = document.getElementById("stopBtn");
    if(stopBtn && typeof QA_CTRL !== "undefined") stopBtn.addEventListener("click", function(){{ if(QA_CTRL && QA_CTRL.abort) QA_CTRL.abort(); }});
    (document.getElementById("{first_input}")||go).addEventListener("keydown", function(e){{ if(e.key==="Enter" && !e.shiftKey){{ e.preventDefault(); go_(); }} }});
  }}
  function gatherInputs(){{
    var p = {{}}; Object.keys(inputs).forEach(function(id){{ p[id]=inputs[id].value; }}); return p;
  }}
  {loader_body}
  drawControls();
  setStatus(BASE?"wait":"bad", BASE?"就绪":"请以 http 方式经后端访问");
  if(typeof QA_HISTORY !== "undefined" && QA_HISTORY.length){{ renderQA(); }} else {{ go_(); }}
}})();
</script>
</body>
</html>
'''

def controls_html(spec):
    h = []
    for inp in spec.get("inputs", []):
        # 注意: 必须输出成 JS 字符串拼接( html += '...' )，否则裸 HTML 会被当 JS 语法
        if inp.get("area"):
            h.append("html += '<label>{label}<br><textarea id=\"{id}\" placeholder=\"{ph}\">{default}</textarea></label>';"
                     .format(label=inp["label"], id=inp["id"], ph=inp["ph"], default=inp.get("default","")))
        else:
            h.append("html += '<label>{label}<input id=\"{id}\" placeholder=\"{ph}\" value=\"{default}\"></label>';"
                     .format(label=inp["label"], id=inp["id"], ph=inp["ph"], default=inp.get("default","")))
    return "\n    ".join(h)

def loader_body(spec):
    if spec.get("loader") == "multi":
        mi = spec["multiInput"]
        return '''
  function go_(){{
    if(!BASE){{ out.innerHTML='<div class="err">未连接到后端（file:// 模式）</div>'; return; }}
    setStatus("wait","加载中…");
    var raw = (inputs["{mi}"].value||"").split(/[,\\s，]+/).map(function(s){{return s.trim();}}).filter(Boolean);
    if(!raw.length){{ out.innerHTML='<div class="empty">请输入至少一个代码</div>'; return; }}
    var rows = []; var done = 0; var fail = 0;
    raw.forEach(function(code){{
      fetch(BASE+"/api/quote?code="+encodeURIComponent(code), {{cache:"no-store"}}).then(function(r){{return r.json();}})
        .then(function(j){{ if(j && (j.ok||j.price!=null)){{ var r=j; r.__code=code; rows.push(r); }} }})
        .catch(function(e){{ fail++; }})
        .then(function(){{ done++; if(done===raw.length) finish(rows, fail); }});
    }});
  }}
  function finish(rows, fail){{
    setStatus(fail? "bad":"ok", "已加载 "+rows.length+" 项"+(fail?(" · "+fail+" 项失败"):""));
    renderRows(rows);
  }}'''.format(mi=mi)
    # post: 提交到 POST 端点(支持 args / args-batch / llm / llm-multi 四种形态)
    if spec.get("loader") == "post":
        kind = spec.get("postKind", "llm")
        if kind == "args":
            return ('''
  function go_(){{
    if(!BASE){{ out.innerHTML='<div class="err">未连接到后端（file:// 模式）</div>'; return; }}
    setStatus("wait","提交中…");
    var url = buildUrl(gatherInputs());
    fetch(BASE+url, {{method:"POST",cache:"no-store"}})
      .then(function(r){{ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); }})
      .then(function(j){{ setStatus(j.ok?"ok":"bad", j.ok?"完成":"失败"); render("{mode}", j); }})
      .catch(function(e){{ setStatus("bad","失败: "+e.message); out.innerHTML='<div class="err">失败: '+esc(e.message)+'</div>'; }});
  }}''').format(mode=spec["mode"])
        if kind == "args-batch":
            body = ('''
  function go_(){{
    if(!BASE){{ out.innerHTML='<div class="err">未连接到后端（file:// 模式）</div>'; return; }}
    setStatus("wait","提交中…");
    var url = buildUrl(gatherInputs());
    fetch(BASE+url, {{method:"POST",cache:"no-store"}})
      .then(function(r){{ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); }})
      .then(function(j){{ setStatus(j.ok?"ok":"bad", j.ok?"完成":"失败"); render("{mode}", j); }})
      .catch(function(e){{ setStatus("bad","失败: "+e.message); out.innerHTML='<div class="err">失败: '+esc(e.message)+'</div>'; }});
  }}
  function batch_(){{
    if(!BASE){{ out.innerHTML='<div class="err">未连接到后端</div>'; return; }}
    setStatus("wait","批量刷新中…");
    var syms = __MAJOR__;
    var done = 0, rows = [];
    syms.forEach(function(s){{
      fetch(BASE+"/api/refresh?symbol="+encodeURIComponent(s.symbol)+"&exchange="+encodeURIComponent(s.exchange), {{method:"POST",cache:"no-store"}})
        .then(function(r){{ return r.json().catch(function(){{ return {{ok:false,symbol:s.symbol,exchange:s.exchange,msg:"解析失败"}}; }}); }})
        .then(function(j){{ rows.push(j); }})
        .catch(function(e){{ rows.push({{ok:false,symbol:s.symbol,exchange:s.exchange,msg:String(e.message||e)}}); }})
        .then(function(){{ done++; if(done===syms.length) finishBatch(rows); }});
    }});
  }}
  function finishBatch(rows){{
    setStatus("ok","已刷新 "+rows.length+" 个品种");
    out.innerHTML = '<div class="note">批量刷新结果（'+rows.length+' 个品种）</div>' + tableHtml(rows);
  }}''').format(mode=spec["mode"])
            body = body.replace("__MAJOR__", json.dumps(spec.get("batchSymbols", []), ensure_ascii=False))
            return body
        if kind == "llm-multi":
            qid = (spec.get("inputs") or [{}])[0].get("id", "q")
            models = spec.get("models") or [{"id":"default","label":"默认","system":spec.get("system","")}]
            return ('''
  var QA_MODELS = __MODELS__;
  var QA_MODEL = (QA_MODELS[0] && QA_MODELS[0].system) || "";
  var QA_HISTORY = [];
  try {{ var _qs = localStorage.getItem("qa_history_" + ENDPOINT); if(_qs) QA_HISTORY = JSON.parse(_qs) || []; }} catch(e) {{}}
  function saveQA(){{ try {{ localStorage.setItem("qa_history_" + ENDPOINT, JSON.stringify(QA_HISTORY)); }} catch(e) {{}} }}
  function mdLite(s){{
    return esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\\*\\*([^*]+)\\*\\*/g, "<b>$1</b>")
      .replace(/^\\s*[-*]\\s+(.+)$/gm, "• $1");
  }}
  function packContext(){{
    var parts = [];
    QA_HISTORY.forEach(function(h){{ if(h.a!=null && h.a.indexOf("（请求失败")!==0) parts.push("用户: "+h.q+"\\n助手: "+h.a); }});
    return parts.join("\\n\\n");
  }}
  var QA_CTRL = null;
  function renderQA(){{
    if(!QA_HISTORY.length){{ out.innerHTML = '<div class="empty">还没有对话，输入问题开始。</div>'; return; }}
    var htm = '<div class="qa">';
    QA_HISTORY.forEach(function(h, idx){{
      var failed = (h.a && h.a.indexOf("（请求失败")===0);
      var acls = failed ? "qaa qaerr" : "qaa";
      var abody = (h.a!=null) ? mdLite(h.a) : '<span class="qaw">思考中…</span>';
      htm += '<div class="qat"><div class="qaq">'+esc(h.q)+'</div>'+
             '<div class="'+acls+'">'+abody+
             '<div class="qatools"><button class="mini" data-act="copy" data-i="'+idx+'">复制</button>'+
             (failed ? '<button class="mini" data-act="retry" data-i="'+idx+'">重试</button>' : '')+'</div></div></div>';
    }});
    htm += '</div>';
    out.innerHTML = htm;
    out.scrollTop = out.scrollHeight;
    Array.prototype.forEach.call(out.querySelectorAll(".mini"), function(b){{
      b.addEventListener("click", function(){{
        var i = +b.getAttribute("data-i");
        if(b.getAttribute("data-act")==="copy"){{
          copyText(QA_HISTORY[i].a||""); var _t=b; b.textContent="已复制"; setTimeout(function(){{ _t.textContent="复制"; }},1200);
        }} else if(b.getAttribute("data-act")==="retry"){{
          var q = QA_HISTORY[i].q; QA_HISTORY.splice(i,1); saveQA(); sendQ(q);
        }}
      }});
    }});
  }}
  function copyText(t){{
    try {{ if(navigator.clipboard) navigator.clipboard.writeText(t); }}
    catch(e){{ var ta=document.createElement("textarea"); ta.value=t; document.body.appendChild(ta); ta.select(); try{{document.execCommand("copy");}}catch(e2){{}} document.body.removeChild(ta); }}
  }}
  function sendQ(q){{
    if(!q) return;
    setStatus("wait","思考中…");
    QA_HISTORY.push({{q:q, a:null}}); saveQA(); renderQA();
    if(QA_CTRL && QA_CTRL.abort) {{ try{{ QA_CTRL.abort(); }}catch(e){{}} }}
    QA_CTRL = (window.AbortController ? new AbortController() : null);
    var ctx = packContext();
    var prompt = (ctx ? ctx+"\\n\\n" : "")+"新问题: "+q;
    fetch(BASE+ENDPOINT, {{method:"POST",headers:{{"Content-Type":"application/json"}},cache:"no-store",
      signal: (QA_CTRL ? QA_CTRL.signal : undefined),
      body:JSON.stringify({{system:QA_MODEL, user:prompt}})}})
      .then(function(r){{ if(!r.ok) return r.json().then(function(e){{ throw new Error(e.error||("HTTP "+r.status)); }}); return r.json(); }})
      .then(function(j){{
        var ans = (j && typeof j.content==="string") ? j.content : "(无回答)";
        QA_HISTORY[QA_HISTORY.length-1].a = ans; saveQA(); renderQA(); setStatus("ok","已回答");
      }})
      .catch(function(e){{
        if(e.name==="AbortError"){{ QA_HISTORY.pop(); saveQA(); renderQA(); setStatus("wait","已停止"); return; }}
        QA_HISTORY[QA_HISTORY.length-1].a = "（请求失败: "+e.message+"）"; saveQA(); renderQA();
        setStatus("bad","请求失败: "+e.message);
      }});
  }}
  function go_(){{
    if(!BASE){{ out.innerHTML='<div class="err">未连接到后端（file:// 模式）</div>'; return; }}
    var q = (inputs["{qid}"].value||"").trim();
    if(!q){{ out.innerHTML='<div class="empty">请输入你的问题</div>'; return; }}
    inputs["{qid}"].value = "";
    sendQ(q);
  }}
''').format(qid=qid).replace("__MODELS__", json.dumps(models, ensure_ascii=False))
        # default llm: POST JSON body {{system, user}}
        qid = (spec.get("inputs") or [{}])[0].get("id", "q")
        system = spec.get("system", "")
        return ('''
  function go_(){{
    if(!BASE){{ out.innerHTML='<div class="err">未连接到后端（file:// 模式）</div>'; return; }}
    setStatus("wait","思考中…");
    var q = (inputs["{qid}"].value||"").trim();
    if(!q){{ out.innerHTML='<div class="empty">请输入你的问题</div>'; return; }}
    fetch(BASE+ENDPOINT, {{method:"POST",headers:{{"Content-Type":"application/json"}},cache:"no-store",
      body:JSON.stringify({{system:"{system}", user:q}})}})
      .then(function(r){{ if(!r.ok) return r.json().then(function(e){{ throw new Error(e.error||("HTTP "+r.status)); }}); return r.json(); }})
      .then(function(j){{ setStatus("ok","已回答"); render("{mode}", j); }})
      .catch(function(e){{ setStatus("bad","请求失败: "+e.message); out.innerHTML='<div class="err">请求失败: '+esc(e.message)+'</div>'; }});
  }}''').format(qid=qid, system=system, mode=spec["mode"])
    # single
    return '''
  function go_(){{
    if(!BASE){{ out.innerHTML='<div class="err">未连接到后端（file:// 模式）</div>'; return; }}
    setStatus("wait","加载中…");
    var url = buildUrl(gatherInputs());
    fetch(BASE+url, {{cache:"no-store"}}).then(function(r){{ if(!r.ok) throw new Error("HTTP "+r.status); return r.json(); }})
      .then(function(j){{ setStatus("ok","已加载"); render("{mode}", j); }})
      .catch(function(e){{ setStatus("bad","加载失败: "+e.message); out.innerHTML='<div class="err">加载失败: '+esc(e.message)+'</div>'; }});
  }}'''.format(mode=spec["mode"])

def make_html(spec):
    ids = [i["id"] for i in spec.get("inputs", [])]
    control_ids = "[" + ", ".join('"%s"' % i for i in ids) + "]" if ids else "[]"
    extra_buttons = ""
    if spec.get("postKind") == "args-batch":
        extra_buttons = '<button id="batchBtn" class="ghost">批量刷新全品种</button>'
    elif spec.get("postKind") == "llm-multi":
        models = spec.get("models") or [{"id":"default","label":"默认","system":spec.get("system","")}]
        opts = "".join('<option value="%s">%s</option>' % (m["id"], m["label"]) for m in models)
        extra_buttons = ('<select id="modelSel" class="ghost">' + opts + '</select>' +
                         '<button id="stopBtn" class="ghost">停止</button>' +
                         '<button id="clearBtn" class="ghost">清空对话</button>')
    html = TPL.format(
        name=spec["name"], ico=spec["ico"], tag=spec["tag"], dir=spec["dir"],
        endpoint=spec["endpoint"], mode=spec["mode"],
        controls_html=controls_html(spec),
        control_ids=control_ids,
        first_input=(spec.get("inputs") or [{}])[0].get("id","goBtn"),
        loader_body=loader_body(spec),
        extra_buttons=extra_buttons,
        go_label=spec.get("goLabel", "查询"),
    )
    # 定制渲染体在 .format 之后注入 → 花括号无需转义
    cust = CUSTOM.get(spec["dir"], {})
    return (html
            .replace("__CUSTOM_CSS__", cust.get("css", ""))
            .replace("__CUSTOM_RENDER__", cust.get("render", "    // 通用渲染"))
            .replace("__CUSTOM_ROWS__", cust.get("rows", "    // 通用渲染")))

def make_test(spec):
    ep = spec["endpoint"]
    extra = ""
    if spec.get("loader") == "multi":
        extra = 'ok("批量加载逻辑存在", src.indexOf("fetch(BASE+\\"/api/quote")>=0);'
    return '''// 自动生成 (tools/gen_microapps.py) — {name}
const {{ runAppTest }} = require("../../tools/test-scaffold.js");
runAppTest(__dirname, ({{ sandbox, ok, eq, arrEq, src, err }}) => {{
  ok("脚本无语法错误", !err || !(err instanceof SyntaxError), err ? err.message : "");
  ok("fetch 调用存在", src.indexOf("fetch(") >= 0);
  ok("端点已配置 ({ep})", src.indexOf("{ep}") >= 0);
  ok("渲染函数存在", src.indexOf("function render") >= 0);
  ok("定制渲染钩子存在", src.indexOf("function renderCustom") >= 0);
  ok("模板占位符已替换", src.indexOf("__CUSTOM") < 0);
  {extra}
}});
'''.format(name=spec["name"], ep=ep, extra=extra)

def main():
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--force", action="store_true"); a = ap.parse_args()
    created = 0
    for spec in SPECS:
        d = os.path.join(ROOT, spec["dir"])
        os.makedirs(os.path.join(d, "test"), exist_ok=True)
        html_path = os.path.join(d, "index.html")
        test_path = os.path.join(d, "test", "run.js")
        if a.force or not os.path.exists(html_path):
            with open(html_path, "w", encoding="utf-8") as f: f.write(make_html(spec)); created += 1
        if a.force or not os.path.exists(test_path):
            with open(test_path, "w", encoding="utf-8") as f: f.write(make_test(spec)); created += 1
    print("generated files:", created)

if __name__ == "__main__":
    main()
