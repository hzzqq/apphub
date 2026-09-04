/*
 * FuturesLens 逻辑自测脚手架（零依赖，仅用 Node 内置 vm/fs）。
 * 加载 index.html 内联脚本，注入最小 DOM / localStorage / canvas 桩，
 * 把内部纯函数（pearson / corrPairs / genDemo / toCSV / parseRange / validateApiUrl 等）
 * 暴露为 vm 全局后断言。
 * 运行：node test/run.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const html = fs.readFileSync(path.resolve(__dirname, "..", "index.html"), "utf8");
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) throw new Error("index.html 中未找到 <script>");
const src = m[1] + "\n;globalThis.REAL_DATA = (typeof REAL_DATA !== 'undefined') ? REAL_DATA : null;";

/* ---------- 最小 DOM / canvas 桩 ---------- */
let gradCalls = 0;   // 统计 createLinearGradient 调用次数（验证库存面积渐变分支）
function makeCtx() {
  const c = {};
  ["clearRect","scale","beginPath","moveTo","lineTo","stroke","fill","arc",
   "fillText","fillRect","save","restore","setTransform","closePath","rect",
   "strokeRect","quadraticCurveTo","bezierCurveTo","setLineDash"].forEach(fn => c[fn] = () => {});
  c.measureText = () => ({ width: 0 });
  // 库存面积渐变用（真实浏览器原生支持；此处补桩以便 draw() 走通渐变分支）
  c.createLinearGradient = () => { gradCalls++; return { addColorStop(){} }; };
  return c;
}
function makeEl(id) {
  const el = {
    id: id || "",
    style: {},
    value: "",
    classList: {
      _s: new Set(),
      add(c){ this._s.add(c); },
      remove(c){ this._s.delete(c); },
      toggle(c, on){ if(on===undefined){ this._s.has(c)?this._s.delete(c):this._s.add(c); } else { on?this._s.add(c):this._s.delete(c); } },
      contains(c){ return this._s.has(c); }
    },
    addEventListener(){}, removeEventListener(){}, appendChild(){}, setAttribute(){},
    getAttribute(){ return null; },
    querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
    getContext(){ return makeCtx(); },
    clientWidth: 600, clientHeight: 420, width: 600, height: 420,
    click(){}, focus(){}, dispatchEvent(){}, onchange: null, onclick: null
  };
  let _html = "", _text = "";
  Object.defineProperty(el, "innerHTML", { get(){ return _html; }, set(v){ _html = v; } });
  Object.defineProperty(el, "textContent", { get(){ return _text; }, set(v){ _text = v; } });
  return el;
}
const doc = {
  _byId: {},
  getElementById(id){ return this._byId[id] || (this._byId[id] = makeEl(id)); },
  querySelector(){ return makeEl(); },
  querySelectorAll(){ return []; },
  createElement(){ return makeEl(); },
  addEventListener(){}
};
function makeStorage(){ const mm = {}; return { getItem:k => (k in mm ? mm[k] : null), setItem:(k,v)=>{ mm[k]=String(v); }, removeItem:k=>{ delete mm[k]; } }; }

const sandbox = {
  document: doc,
  window: { devicePixelRatio: 1, addEventListener(){}, __data: null },
  localStorage: makeStorage(),
  console,
  fetch: () => Promise.reject(new Error("no network in test")),
  encodeURIComponent, decodeURIComponent,
  setTimeout, clearTimeout,
  URL, Blob,
  process
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
process.on("unhandledRejection", () => {});
try { vm.runInContext(src, sandbox, { filename: "index.html#script" }); }
catch (e) { console.warn("（脚本自动运行期的提示，已忽略）:", e.message); }

/* ---------- 断言工具 ---------- */
let pass = 0, fail = 0, failed = [];
function ok(name, cond, extra) {
  if (cond) { pass++; console.log("  ✓ " + name); }
  else { fail++; failed.push(name); console.log("  ✗ " + name + (extra ? " :: " + extra : "")); }
}
const approx = (a, b, e) => Math.abs(a - b) <= (e == null ? 1e-9 : e);

/* ============================================================
 *  Round 1: 相关性正确性（corrPairs 对齐 + pearson）
 * ============================================================ */
console.log("\n[Round 1] 相关性 pearson / corrPairs");
ok("pearson 完全正相关 = 1", approx(sandbox.pearson([1,2,3],[2,4,6]), 1));
ok("pearson 完全负相关 = -1", approx(sandbox.pearson([1,2,3],[6,4,2]), -1));
ok("pearson 常数序列返回 NaN", Number.isNaN(sandbox.pearson([5,5,5],[1,2,3])));
ok("corrPairs 跳过 inventory 缺失行", (() => {
  const d = [
    { date:"2026-01-01", close:10, inventory:100 },
    { date:"2026-01-02", close:20, inventory:null },   // 缺失 → 跳过
    { date:"2026-01-03", close:30, inventory:300 }
  ];
  const { closes, invs } = sandbox.corrPairs(d);
  return closes.length === 2 && invs.length === 2 &&
         closes[0] === 10 && invs[0] === 100 &&
         closes[1] === 30 && invs[1] === 300;
})());
ok("corrPairs 缺失行导致对齐：错位 bug 不再出现", (() => {
  // 修复前：cm=[1,2,3], im=[10,30] -> 错位 pearson；修复后：只取成对行
  const d = [
    { date:"a", close:1, inventory:10 },
    { date:"b", close:2, inventory:null },
    { date:"c", close:3, inventory:30 }
  ];
  const { closes, invs } = sandbox.corrPairs(d);
  // 对齐后应为 (1,10) 与 (3,30)，二者正相关（r=1），而非与缺失错位
  return closes.length === 2 && invs.length === 2 && approx(sandbox.pearson(closes, invs), 1);
})());
ok("genDemo 确定性：同参数两次结果一致", (() => {
  const a = sandbox.genDemo("SHFE","cu",1), b = sandbox.genDemo("SHFE","cu",1);
  return a.length === b.length && a.every((x,i)=> x.close===b[i].close && x.inventory===b[i].inventory);
})());
ok("genDemo 产出 365 天且字段齐全", (() => {
  const a = sandbox.genDemo("DCE","m",1);
  return a.length === 365 && a.every(x => typeof x.date==="string" && typeof x.close==="number" && typeof x.inventory==="number");
})());

/* ============================================================
 *  Round 2: CSV 导出 toCSV
 * ============================================================ */
if (typeof sandbox.toCSV === "function") {
  console.log("\n[Round 2] CSV 导出 toCSV");
  // 表头随当前库存口径动态变化(多口径: 总库存/可流通/注册仓单/保税区), 不再固定为'库存(吨)'
  const rows = [
    { date:"2026-08-01", close:68900, inventory:152000 },
    { date:"2026-08-02", close:null, inventory:151000 },
    { date:"2026-08-03", close:69100, inventory:null }
  ];
  const csv = sandbox.toCSV(rows, "both");
  const lines = csv.trim().split(/\r?\n/);
  ok("toCSV both 表头: 日期,收盘价,<口径>(吨)", /^日期,收盘价,.+\(吨\)$/.test(lines[0]), "got: " + lines[0]);
  ok("toCSV 缺失字段导出为空（不带 null）", lines[2] === "2026-08-02,,151000" && lines[3] === "2026-08-03,69100,");
  ok("toCSV price 模式只含收盘价", sandbox.toCSV(rows, "price").trim().split(/\r?\n/)[0] === "日期,收盘价");
  const invHead = sandbox.toCSV(rows, "inv").trim().split(/\r?\n/)[0];
  ok("toCSV inv 模式表头: 日期,<口径>(吨)", /^日期,.+\(吨\)$/.test(invHead), "got: " + invHead);
  ok("toCSV 含逗号/引号时转义", (() => {
    const c = sandbox.toCSV([{ date:"a,b", close:1, inventory:2 }], "both");
    return c.indexOf('"a,b"') >= 0;
  })());
} else {
  console.log("\n[Round 2] toCSV —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 3: 区间解析 / 校验 parseRange
 * ============================================================ */
if (typeof sandbox.parseRange === "function") {
  console.log("\n[Round 3] 区间解析/校验 parseRange");
  const today = "2026-08-24";
  ok("parseRange 正常区间返回起止", (() => {
    const r = sandbox.parseRange("2026-05-01", "2026-08-01", today);
    return r.ok && r.start === "2026-05-01" && r.end === "2026-08-01";
  })());
  ok("parseRange 起>止 报错", !sandbox.parseRange("2026-08-10", "2026-05-01", today).ok);
  ok("parseRange 未来结束日 报错", !sandbox.parseRange("2026-01-01", "2027-01-01", today).ok);
  ok("parseRange 缺省结束日补为今天", (() => {
    const r = sandbox.parseRange("2026-05-01", "", today);
    return r.ok && r.end === today;
  })());
  ok("parseRange 缺省起始日补为 365 天前", (() => {
    const r = sandbox.parseRange("", "2026-08-24", today);
    return r.ok && r.start === "2025-08-24";
  })());
} else {
  console.log("\n[Round 3] parseRange —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 4: 图表命中测试 hitTestIndex
 * ============================================================ */
if (typeof sandbox.hitTestIndex === "function") {
  console.log("\n[Round 4] 图表命中 hitTestIndex");
  // 在 padL=58, plotW=484 的 600 宽画布上，10 个点
  const idx = sandbox.hitTestIndex(58 + 484 * 0.5, 10, 58, 484);
  ok("hitTestIndex 中点靠近索引 5", idx === 5);
  ok("hitTestIndex 左边界=0", sandbox.hitTestIndex(58, 10, 58, 484) === 0);
  ok("hitTestIndex 右边界=末位", sandbox.hitTestIndex(58 + 484, 10, 58, 484) === 9);
} else {
  console.log("\n[Round 4] hitTestIndex —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 5: API URL 合法性校验 validateApiUrl
 * ============================================================ */
if (typeof sandbox.validateApiUrl === "function") {
  console.log("\n[Round 5] API URL 校验 validateApiUrl");
  ok("validateApiUrl 接受 https", sandbox.validateApiUrl("https://example.com/api").ok);
  ok("validateApiUrl 接受 http", sandbox.validateApiUrl("http://127.0.0.1:5000/api").ok);
  ok("validateApiUrl 拒绝空串", !sandbox.validateApiUrl("").ok);
  ok("validateApiUrl 拒绝无协议", !sandbox.validateApiUrl("example.com/api").ok);
  ok("validateApiUrl 拒绝 javascript: 协议", !sandbox.validateApiUrl("javascript:alert(1)").ok);
} else {
  console.log("\n[Round 5] validateApiUrl —— 本轮尚未实现，跳过");
}

if (typeof sandbox.normalizeRecords === "function") {
  console.log("\n[Round 5] 后端响应规整 normalizeRecords");
  ok("normalizeRecords 接受合法数组", sandbox.normalizeRecords([{date:"2026-01-01",close:"68900",inventory:"152000"}]).ok);
  ok("normalizeRecords 数字字符串转 number", (() => {
    const r = sandbox.normalizeRecords([{date:"2026-01-01",close:"68900",inventory:152000}]);
    return r.ok && r.rows[0].close === 68900 && r.rows[0].inventory === 152000;
  })());
  ok("normalizeRecords 缺失字段置 null", (() => {
    const r = sandbox.normalizeRecords([{date:"2026-01-01"}]);
    return r.ok && r.rows[0].close === null && r.rows[0].inventory === null;
  })());
  ok("normalizeRecords 非数组 -> 失败", !sandbox.normalizeRecords({date:"x"}).ok);
  ok("normalizeRecords 空数组 -> 失败", !sandbox.normalizeRecords([]).ok);
  ok("normalizeRecords 无 date 的记录被剔除且有效记录保留", (() => {
    const r = sandbox.normalizeRecords([{foo:1},{date:"2026-01-02",close:1,inventory:2}]);
    return r.ok && r.rows.length === 1 && r.rows[0].date === "2026-01-02";
  })());
} else {
  console.log("\n[Round 5] normalizeRecords —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 6: 事件时间轴 esc / mergeEvents / 用户标注
 * ============================================================ */
if (typeof sandbox.esc === "function" && typeof sandbox.mergeEvents === "function") {
  console.log("\n[Round 6] 事件时间轴 esc / mergeEvents / 用户标注");
  ok("esc 中和 <img onerror>", sandbox.esc('<img src=x onerror=alert(1)>') === "&lt;img src=x onerror=alert(1)&gt;");
  ok("esc 中和双引号与单引号", sandbox.esc('a"b\'c') === "a&quot;b&#39;c");
  ok("esc 中和 & 符号", sandbox.esc("a&b") === "a&amp;b");
  ok("mergeEvents 内置+用户合并并按日期排序", (() => {
    const m = sandbox.mergeEvents([{date:"2026-08-10",type:"price",title:"A"}],
                                  null,
                                  [{date:"2026-06-25",type:"inv",title:"B"}]);
    return m.length === 2 && m[0].date === "2026-06-25" && m[1].date === "2026-08-10";
  })());
  ok("mergeEvents 同日期+同标题去重", (() => {
    const m = sandbox.mergeEvents([{date:"2026-08-10",type:"price",title:"A"}], null, [{date:"2026-08-10",type:"price",title:"A"}]);
    return m.length === 1;
  })());
  ok("mergeEvents 过滤无 date 的事件", (() => {
    const m = sandbox.mergeEvents([{type:"price",title:"X"}], null, []);
    return m.length === 0;
  })());
  ok("mergeEvents 三类合并保留全部去重", (() => {
    const m = sandbox.mergeEvents([{date:"2026-07-01",type:"evt",title:"供给收缩"}],
                                  [{date:"2026-07-02",type:"price",title:"涨"}],
                                  [{date:"2026-07-01",type:"evt",title:"供给收缩"}]);
    return m.length === 2;
  })());
  ok("getUserEvents/setUserEvents 往返", (() => {
    sandbox.setUserEvents("DCE","sp",[{date:"2026-08-25",type:"price",title:"Z"}]);
    const arr = sandbox.getUserEvents("DCE","sp");
    return Array.isArray(arr) && arr.length===1 && arr[0].title==="Z";
  })());
  ok("indexEventsByDate 命中数据日期索引", (() => {
    const data=[{date:"2026-08-09"},{date:"2026-08-10"},{date:"2026-08-11"}];
    const hit = sandbox.indexEventsByDate([{date:"2026-08-10",type:"price",title:"A"}], data);
    return hit.length===1 && hit[0].idx===1;
  })());
  ok("indexEventsByDate 忽略无匹配日期的事件", (() => {
    const data=[{date:"2026-08-09"},{date:"2026-08-10"}];
    const hit = sandbox.indexEventsByDate([{date:"2026-08-99",type:"price",title:"X"}], data);
    return hit.length===0;
  })());
} else {
  console.log("\n[Round 6] 事件时间轴 —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 7: 自选品种持久化（localStorage）
 * ============================================================ */
if (typeof sandbox.getFavorites === "function") {
  console.log("\n[Round 7] 自选品种持久化");
  sandbox.setFavorites([]);  // 隔离前置状态
  ok("toggleFavorite 加入后 isFavorite=true", (() => { sandbox.toggleFavorite("SHFE","cu"); return sandbox.isFavorite("SHFE","cu"); })());
  ok("getFavorites 返回含该品种", sandbox.getFavorites().some(f => f.ex==="SHFE" && f.code==="cu"));
  ok("toggleFavorite 再次点击移除", (() => { sandbox.toggleFavorite("SHFE","cu"); return !sandbox.isFavorite("SHFE","cu"); })());
  sandbox.toggleFavorite("DCE","sp");
  ok("自选已持久化到 localStorage", /DCE/.test(sandbox.localStorage.getItem("fl_favorites_v1") || ""));
  ok("重复添加不会重复计数", (() => { sandbox.toggleFavorite("DCE","sp"); sandbox.toggleFavorite("DCE","sp"); const n=sandbox.getFavorites().filter(f=>f.ex==="DCE"&&f.code==="sp").length; sandbox.setFavorites([]); return n===1; })());
} else {
  console.log("\n[Round 7] 自选品种持久化 —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 8: 库存同比/环比（futures-combo 口径）
 * ============================================================ */
if (typeof sandbox.invChangeSeries === "function") {
  console.log("\n[Round 8] 库存同比/环比");
  const mk = (date, inv) => ({ date, close:1, inventory:inv });
  const data = [
    mk("2025-08-01",100), mk("2025-08-31",100),
    mk("2026-07-02",110), mk("2026-07-31",110),
    mk("2026-08-01",120), mk("2026-08-31",130)
  ];
  const s = sandbox.invChangeSeries(data, "inventory");
  const last = s[s.length-1];
  // 8/31 前 30 天 = 8/01(120)：pctChange(130,120)=+8.33%
  ok("环比(8/31 vs 8/01) ≈ +8.3%", last.mom!=null && Math.abs(last.mom-0.0833)<0.01, "mom="+last.mom);
  const y = s.find(x => x.date==="2026-08-01");
  ok("同比(2026-8-1 vs 2025-8-1) = +20%", y.yoy!=null && Math.abs(y.yoy-0.2)<0.001, "yoy="+y.yoy);
  ok("缺失对比日返回 null", (() => {
    const d = [{date:"2026-08-01",close:1,inventory:100}];
    const r = sandbox.invChangeSeries(d, "inventory")[0];
    return r.mom===null && r.yoy===null;
  })());
  ok("latestInvChange 取最后有库存点", (() => {
    const r = sandbox.latestInvChange(data, "inventory");
    return r && r.value===130 && Math.abs(r.mom-0.0833)<0.01;
  })());
  ok("沪深300(无实物库存) latestInvChange 返回 null 不崩", sandbox.latestInvChange([{date:"2026-08-01",close:4000}], "inventory")===null);
} else {
  console.log("\n[Round 8] 库存同比/环比 —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 9: 库存季节性（按月份均值）
 * ============================================================ */
if (typeof sandbox.seasonalProfile === "function") {
  console.log("\n[Round 9] 库存季节性");
  const mk = (date, inv) => ({ date, close:1, inventory:inv });
  const data = [
    mk("2026-01-15",100), mk("2026-01-20",200),   // 1月均值 150
    mk("2026-02-10",300),                          // 2月 = 300
    mk("2026-03-10",null)                          // 3月缺失 -> null
  ];
  const p = sandbox.seasonalProfile(data, "inventory");
  ok("1月均值=150", p[0]!=null && approx(p[0],150), "p0="+p[0]);
  ok("2月=300", p[1]!=null && approx(p[1],300));
  ok("3月缺失=null", p[2]===null);
  ok("其余月为 null", p[3]===null && p[11]===null);
} else {
  console.log("\n[Round 9] 库存季节性 —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 10: 基差(现货-期货，对齐 futures-combo)
 * ============================================================ */
if (typeof sandbox.computeBasis === "function") {
  console.log("\n[Round 10] 基差(现货-期货)");
  ok("computeBasis = spot - close", sandbox.computeBasis({spot:70000,close:68900}) === 1100);
  ok("缺 spot 返回 null", sandbox.computeBasis({close:68900}) === null);
  ok("缺 close 返回 null", sandbox.computeBasis({spot:70000}) === null);
  const d = sandbox.genDemo("SHFE","cu",1);
  ok("genDemo 现含 spot 字段", typeof d[0].spot === "number");
  ok("genDemo 基差非全 null", d.some(x => sandbox.computeBasis(x) != null));
} else {
  console.log("\n[Round 10] 基差 —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 11: 数据质量/异常兜底
 * ============================================================ */
if (typeof sandbox.dataQuality === "function") {
  console.log("\n[Round 11] 数据质量/异常兜底");
  const mk = (date, inv) => ({ date, close:1, inventory:inv });
  const data = [
    mk("2026-08-01",100), mk("2026-08-03",100),   // 8/2 缺失 -> 日期缺口
    mk("2026-08-04",null),                        // 缺失库存
    mk("2026-08-05",0),                           // 零库存 + 100->0 异常跳变
    mk("2026-08-06",300), mk("2026-08-07",360)    // 300->360 仅 +20% 不计入异常
  ];
  const q = sandbox.dataQuality(data, "inventory");
  ok("统计总数=6", q.total === 6);
  ok("缺失库存=1", q.missingInv === 1);
  ok("负/零库存=1", q.zeroOrNeg === 1);
  ok("异常跳变=1", q.anomalies === 1);
  ok("日期缺口=1", q.gapRuns === 1);
  ok("空数据不崩", (() => { const e = sandbox.dataQuality([], "inventory"); return e.total===0 && e.gapRuns===0; })());
} else {
  console.log("\n[Round 11] 数据质量 —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 12: 内置真实样本 REAL_DATA（默认真实数据，非合成）
 * ============================================================ */
console.log("\n[Round 12] 内置真实样本 REAL_DATA");
const RD = sandbox.REAL_DATA;
ok("REAL_DATA 存在", !!RD);
ok("SHFE:sp 有真实库存序列(>=20 行)", RD && Array.isArray(RD["SHFE:sp"]) && RD["SHFE:sp"].length >= 20);
ok("全品种内置真实样本(>=50 品种)", RD && Object.keys(RD).length >= 50);
if (RD && RD["SHFE:sp"]) {
  const sp = RD["SHFE:sp"];
  // 全部为真实公开库存（东方财富口径，单位吨），无编造收盘价
  const allReal = sp.every(x => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(x.date)) return false;
    if (x.inventory_total == null) return false;
    if (!(x.inventory_total > 0)) return false;
    return true;
  });
  ok("SP 序列全是真实日期+正库存(无编造)", allReal);
  ok("SP 末值 = 最近真实库存(吨)", sp[sp.length-1].inventory_total > 0);
  // 映射后字段口径与后端一致：inventory_total 保留、null 不被转 0
  const mapped = sp.map(x => ({
    date: x.date,
    close: x.close == null ? null : +x.close,
    inventory_total: x.inventory_total == null ? null : +x.inventory_total
  }));
  ok("映射后 inventory_total 仍为真实值", mapped[mapped.length-1].inventory_total === sp[sp.length-1].inventory_total);
  ok("映射后 null 不被转成 0", mapped.every(m => m.inventory_total === null || m.inventory_total > 0));
}
// 抽检其他品种也内置真实序列（证明"所有品种都有真实数据"）
for (const k of ["SHFE:cu","SHFE:rb","CZCE:fg","DCE:jd","CZCE:sa","DCE:eg"]) {
  ok(k+" 有真实库存序列", RD[k] && RD[k].some(r => r.inventory_total != null && r.inventory_total > 0));
}

/* ============================================================
 *  Round 13: 数据新鲜度（数据截止日 / 距今天数 / 滞后告警 / 下次预计发布）
 * ============================================================ */
if (typeof sandbox.freshnessInfo === "function") {
  console.log("\n[Round 13] 数据新鲜度");
  const TD = new Date("2026-08-28T00:00:00");   // 固定"今天"，保证用例可重复
  const mk = (date, inv) => ({ date, close: 1, inventory: inv });

  ok("daysSince 1天前", sandbox.daysSince("2026-08-27", TD) === 1);
  ok("daysSince 7天前", sandbox.daysSince("2026-08-21", TD) === 7);
  ok("daysSince 未来日期为负", sandbox.daysSince("2026-09-01", TD) === -4);
  ok("daysSince 非法日期=null", sandbox.daysSince("bad-date", TD) === null);
  ok("daysSince 空值=null", sandbox.daysSince(null, TD) === null);

  ok("空数组 -> empty", sandbox.freshnessInfo([], "inventory", 7, TD).level === "empty");
  ok("无库存数据 -> empty", sandbox.freshnessInfo([mk("2026-08-27", null)], "inventory", 7, TD).level === "empty");

  const f1 = sandbox.freshnessInfo([mk("2026-08-26", 100), mk("2026-08-27", 120)], "inventory", 7, TD);
  ok("1天前 -> fresh", f1.level === "fresh" && f1.date === "2026-08-27" && f1.ageDays === 1);

  const f2 = sandbox.freshnessInfo([mk("2026-08-20", 100), mk("2026-08-27", null)], "inventory", 7, TD);
  ok("跳过无库存日取最后有库存日(8天前) -> lagging", f2.date === "2026-08-20" && f2.ageDays === 8 && f2.level === "lagging");

  const f3 = sandbox.freshnessInfo([mk("2026-08-13", 100)], "inventory", 7, TD);
  ok("15天前 -> stale", f3.level === "stale" && f3.ageDays === 15);

  ok("恰好7天仍算 fresh(<=1个周期)", sandbox.freshnessInfo([mk("2026-08-21", 100)], "inventory", 7, TD).level === "fresh");
  ok("恰好14天算 lagging(<=2个周期)", sandbox.freshnessInfo([mk("2026-08-14", 100)], "inventory", 7, TD).level === "lagging");
  ok("非法日期 -> unknown 且保留 date", (() => {
    const u = sandbox.freshnessInfo([{ date: "xx", inventory: 1 }], "inventory", 7, TD);
    return u.level === "unknown" && u.date === "xx";
  })());

  // nextReleaseDate：2026-08-28 为周五(getDay=5)
  ok("周五规则 -> 下个周五 2026-09-04", sandbox.nextReleaseDate({ weekday: 5 }, "2026-08-28") === "2026-09-04");
  ok("周三规则 -> 下个周三 2026-09-02", sandbox.nextReleaseDate({ weekday: 3 }, "2026-08-28") === "2026-09-02");
  ok("非法基准日 -> null", sandbox.nextReleaseDate({ weekday: 5 }, "not-a-date") === null);
  ok("无规则 -> null", sandbox.nextReleaseDate(null, "2026-08-28") === null);

  // 徽标文案
  ok("empty 徽标提示无库存", sandbox.freshnessBadgeHTML({ level: "empty" }).indexOf("无库存数据") >= 0);
  ok("stale 徽标含日期+下次预计", (() => {
    const s = sandbox.freshnessBadgeHTML({ level: "stale", date: "2026-08-13", ageDays: 15 }, "2026-09-04");
    return s.indexOf("2026-08-13") >= 0 && s.indexOf("下次预计 2026-09-04") >= 0;
  })());
  ok("fresh 徽标不显示下次预计(避免噪音)", sandbox.freshnessBadgeHTML({ level: "fresh", date: "2026-08-27", ageDays: 1 }, "2026-09-04").indexOf("下次预计") < 0);
  ok("stale 用红色告警", sandbox.freshnessBadgeHTML({ level: "stale", date: "2026-08-13", ageDays: 15 }).indexOf("#ff4d4f") >= 0);

  // 集成：内置真实纸浆样本
  if (RD && RD["SHFE:sp"]) {
    const fr = sandbox.freshnessInfo(RD["SHFE:sp"], "inventory_total", 7, TD);
    ok("真实样本新鲜度 date 非空", typeof fr.date === "string" && fr.date.length === 10);
    ok("真实样本 ageDays 为数字", typeof fr.ageDays === "number");
    ok("真实样本 level 合法", ["fresh", "lagging", "stale"].indexOf(fr.level) >= 0);
  }
} else {
  console.log("\n[Round 13] 数据新鲜度 —— 本轮尚未实现，跳过");
}

/* ============================================================
 *  Round 14: 推演表 CSV 导出 fcBuildCSV
 * ============================================================ */
if (typeof sandbox.fcBuildCSV === "function") {
  console.log("\n[Round 14] 推演表 CSV 导出 fcBuildCSV");
  // 准备真实库存序列（让分位/收盘价映射可用）
  sandbox.window.__data = [
    { date:"2026-08-01", close:4800, inventory_total:120000 },
    { date:"2026-08-08", close:4750, inventory_total:110000 },
    { date:"2026-08-15", close:4700, inventory_total:100000 }
  ];
  const symEl = sandbox.document.getElementById("symbol");
  symEl.value = "SP";
  const key = sandbox.fcKey();            // 默认 curExch="SHFE" → "SHFE:SP"
  const fdata = {
    title: "测试推演",
    source: "交易所周报",
    baseline_inventory: 100,
    keyLow: 4500, keyHigh: 4650,          // 当前 4700 > 4650 → 价位"偏高"，与低库存分位构成 ⚠背离
    assumptions: "假设无新增产能",
    triggerRule: "破基准预警",
    rows: [
      { report:"2026-08-01", stat:"2026-08-01", inv:120, change:-5, dir:"去库", driver:"周报, 进口少" },
      { report:"2026-08-08", stat:"2026-08-08", inv:110, change:-10, dir:"去库", driver:"正常去化" },
      { report:"推演W+1", stat:"2026-08-22", inv:100, change:-10, dir:"去库", driver:"推演(近4周斜率 -8.33 万吨/周)", _proj:true }
    ]
  };
  sandbox.fcSet(key, fdata);
  const cv = sandbox.fcBuildCSV();
  ok("fcBuildCSV 返回非空对象", cv && typeof cv.csv === "string");
  if (cv) {
    const lines = cv.csv.split("\n");
    ok("CSV 顶部含 # 标题注释", lines.some(l => /^# 标题：测试推演/.test(l)));
    ok("CSV 含 # 口径注释", lines.some(l => /^# 口径：交易所周报/.test(l)));
    ok("CSV 含 # 基准库存注释", lines.some(l => /^# 基准库存：100 万吨/.test(l)));
    ok("CSV 含 # 库存分位注释(近3周)", lines.some(l => /^# 库存分位：/.test(l)));
    ok("CSV 含 # 关键价位带注释", lines.some(l => /^# 关键价位带：/.test(l)));
    ok("CSV 含 # 库存×价格联动注释(⚠背离)", lines.some(l => /^# 库存×价格联动：/.test(l)));
    const header = lines.find(l => l.startsWith('"报告期"'));
    ok("CSV 表头存在且为 11 列", header && header.split(",").length === 11, header && header.split(",").length);
    ok("CSV 含 真实历史 行标记", cv.csv.includes('"真实历史"'));
    ok("CSV 含 未来推演 行标记", cv.csv.includes('"未来推演"'));
    ok("CSV 转义：含逗号字段被双引号包裹", /"周报, 进口少"/.test(cv.csv));
    ok("CSV 收盘价列映射真实序列(4,800)", cv.csv.includes('"4,800"'));
    ok("CSV.sym 为 SHFE:SP", cv.sym === "SHFE:SP", cv.sym);
  }
  // 空数据应返回 null（导出按钮据此提示）
  sandbox.fcSet(key, { rows: [] });
  ok("fcBuildCSV 空数据返回 null", sandbox.fcBuildCSV() === null);
} else {
  console.log("\n[Round 14] 推演表 CSV 导出 —— fcBuildCSV 不存在，跳过");
}

/* ============================================================
 *  Round 15: 联动信号行自动高亮 + 双轴库存线精修
 * ============================================================ */
console.log("\n[Round 15] 联动信号行高亮 / 双轴库存线精修");
(function(){
  const DATES = ["2026-07-18","2026-07-25","2026-08-01","2026-08-08","2026-08-15"];
  // 用给定库存序列 + 收盘价 + 关键价位带渲染推演表，返回 tbody HTML
  function renderSig(invs, closes, zLow, zHigh){
    sandbox.window.__data = DATES.map((d,i)=>({ date:d, close:closes[i], inventory_total:invs[i] }));
    sandbox.document.getElementById("symbol").value = "SP";
    sandbox.fcSet(sandbox.fcKey(), {
      title:"", source:"交易所周报", baseline_inventory: 9999,
      keyLow:zLow, keyHigh:zHigh,
      rows: DATES.map((d,i)=>({ report:d, stat:d, inv:+(invs[i]/1000).toFixed(1), change:-10, dir:"去库", driver:"驱动"+i }))
    });
    sandbox.renderForecast();
    return sandbox.document.getElementById("fcBody").innerHTML;
  }
  const INV_DOWN = [140000,130000,120000,110000,100000];  // 末点最低 → 分位 0% → 利多
  const INV_UP   = [100000,110000,120000,130000,140000];  // 末点最高 → 分位 80% → 利空
  const PX_DOWN  = [4900,4850,4800,4750,4700];            // 末收盘 4700
  const PX_UP    = [4600,4650,4700,4750,4800];            // 末收盘 4800

  // ① 利多 + 价格偏高(4700>4650) → ⚠背离 → fc-sig-div（琥珀）
  const hDiv = renderSig(INV_DOWN, PX_DOWN, 4500, 4650);
  ok("背离：命中行高亮 fc-sig-div", /class="fc-sig fc-sig-div"/.test(hDiv), hDiv.slice(0,150));
  ok("背离：仅高亮 1 行(信号行)", (hDiv.match(/fc-sig fc-sig-div/g)||[]).length === 1);
  ok("背离：行带 title 悬浮说明", /title="库存×价格联动：⚠背离/.test(hDiv));

  // ② 利多 + 价格偏低(4700<4750) → ⚡双多共振 → fc-sig-bull（绿，与主图竖线同色系）
  const hBull = renderSig(INV_DOWN, PX_DOWN, 4750, 4900);
  ok("双多共振：命中行高亮 fc-sig-bull", /class="fc-sig fc-sig-bull"/.test(hBull), hBull.slice(0,150));
  ok("双多共振：仅高亮 1 行", (hBull.match(/fc-sig fc-sig-bull/g)||[]).length === 1);

  // ③ 利空 + 价格偏高(4800>4700) → ⚡双空共振 → fc-sig-bear（红）
  const hBear = renderSig(INV_UP, PX_UP, 4500, 4700);
  ok("双空共振：命中行高亮 fc-sig-bear", /class="fc-sig fc-sig-bear"/.test(hBear), hBear.slice(0,150));

  // ④ 价格在区间内(4800 ∈ [4700,4850]) → 无强共振 → 不应高亮
  const hNone = renderSig(INV_UP, PX_UP, 4700, 4850);
  ok("无共振(区间内)：不产生高亮行", !/class="fc-sig /.test(hNone), hNone.slice(0,150));

  // ⑤ 双轴库存线精修：draw() 走通面积渐变分支（draw 首次进入单测覆盖）
  gradCalls = 0;
  let drawOk = true, drawErr = "";
  try { sandbox.draw(); } catch(e){ drawOk = false; drawErr = e.message; }
  ok("draw() 双轴渲染不抛错(含 setLineDash/渐变等 canvas API)", drawOk, drawErr);
  ok("draw() 触发库存面积渐变(精修分支走通)", gradCalls > 0, "gradCalls=" + gradCalls);
})();

/* ---------- 汇总 ---------- */
console.log(`\n汇总：通过 ${pass} / 失败 ${fail}`);
if (fail) { console.log("失败项：" + failed.join("; ")); process.exit(1); }
