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
function makeCtx() {
  const c = {};
  ["clearRect","scale","beginPath","moveTo","lineTo","stroke","fill","arc",
   "fillText","fillRect","save","restore","setTransform","closePath","rect",
   "strokeRect","quadraticCurveTo","bezierCurveTo"].forEach(fn => c[fn] = () => {});
  c.measureText = () => ({ width: 0 });
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
ok("SHFE:sp 有 9 条真实样本", RD && Array.isArray(RD["SHFE:sp"]) && RD["SHFE:sp"].length === 9);
if (RD && RD["SHFE:sp"]) {
  const sp = RD["SHFE:sp"];
  const by = d => sp.find(x => x.date === d);
  ok("2026-06-25 库存 2335200 吨(真实)", by("2026-06-25").inventory_total === 2335200);
  ok("2026-08-13 收盘价 4538(真实)", by("2026-08-13").close === 4538);
  ok("2026-06-26 库存为 null(未编造)", by("2026-06-26").inventory_total === null);
  ok("2026-08-25 收盘价 4828(真实)", by("2026-08-25").close === 4828);
  // 映射后字段口径与后端一致
  const mapped = sp.map(x => ({
    date: x.date,
    close: x.close == null ? null : +x.close,
    inventory_total: x.inventory_total == null ? null : +x.inventory_total
  }));
  ok("映射后 2026-06-25 inventory_total 仍为真实值", mapped.find(m=>m.date==="2026-06-25").inventory_total === 2335200);
  ok("映射后 null 不被转成 0", mapped.find(m=>m.date==="2026-06-26").inventory_total === null);
}

/* ---------- 汇总 ---------- */
console.log(`\n汇总：通过 ${pass} / 失败 ${fail}`);
if (fail) { console.log("失败项：" + failed.join("; ")); process.exit(1); }
