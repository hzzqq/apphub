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
]

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
  function renderRows(rows){{
    if(!rows || !rows.length){{ out.innerHTML = '<div class="empty">无数据</div>'; return; }}
    var cols = []; var seen = {{}};
    rows.forEach(function(r){{ if(r && typeof r==="object"){{ Object.keys(r).forEach(function(k){{ if(!seen[k]){{seen[k]=1;cols.push(k);}} }}); }} }});
    if(!cols.length) cols = Object.keys(rows[0]||{{}});
    var html = '<table class="tbl"><thead><tr>'+cols.map(function(c){{return "<th>"+esc(c)+"</th>";}}).join("")+'</tr></thead><tbody>';
    rows.forEach(function(r){{
      html += "<tr>"+cols.map(function(c){{ return "<td>"+cell(r?r[c]:null)+"</td>"; }}).join("")+"</tr>";
    }});
    html += "</tbody></table>";
    out.innerHTML = html;
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
      '<button id="goBtn">查询</button>';
    var controlIds = [{control_ids}];
    controlIds.forEach(function(id){{ inputs[id]=document.getElementById(id); }});
    var go = document.getElementById("goBtn");
    go.addEventListener("click", go_);
    (document.getElementById("{first_input}")||go).addEventListener("keydown", function(e){{ if(e.key==="Enter") go_(); }});
  }}
  function gatherInputs(){{
    var p = {{}}; Object.keys(inputs).forEach(function(id){{ p[id]=inputs[id].value; }}); return p;
  }}
  {loader_body}
  drawControls();
  setStatus(BASE?"wait":"bad", BASE?"就绪":"请以 http 方式经后端访问");
  go_();
}})();
</script>
</body>
</html>
'''

def controls_html(spec):
    h = []
    for inp in spec.get("inputs", []):
        # 注意: 必须输出成 JS 字符串拼接( html += '...' )，否则裸 HTML 会被当 JS 语法
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
    return TPL.format(
        name=spec["name"], ico=spec["ico"], tag=spec["tag"], dir=spec["dir"],
        endpoint=spec["endpoint"], mode=spec["mode"],
        controls_html=controls_html(spec),
        control_ids=control_ids,
        first_input=(spec.get("inputs") or [{}])[0].get("id","goBtn"),
        loader_body=loader_body(spec),
    )

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
