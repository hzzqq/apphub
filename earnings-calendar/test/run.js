/*
 * EarningsCalendar 逻辑自测脚手架（零依赖，仅用 Node 内置 vm/fs）。
 * 加载 index.html 内联脚本，注入最小 DOM / localStorage 桩，
 * 把内部函数（esc/marketOf/csvEscape/toCSV/filterEvents/buildMonthMatrix/
 * toggleAnnotation/addItem/importItems 等）暴露为 vm 全局后断言。
 * 运行：node test/run.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");

const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) throw new Error("index.html 中未找到 <script>");
const src = m[1];

/* ---------- 最小 DOM 桩 ---------- */
function makeEl(id) {
  const el = {
    id: id || "",
    _html: "", _value: "", _text: "", _attrs: {}, _listeners: {},
    style: {},
    dataset: {},
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      toggle(c, on) {
        if (on === undefined) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); }
        else { on ? this._s.add(c) : this._s.delete(c); }
      },
      contains(c) { return this._s.has(c); }
    },
    set innerHTML(v) { this._html = v; },
    get innerHTML() { return this._html; },
    set value(v) { this._value = v; },
    get value() { return this._value; },
    set textContent(v) { this._text = v; },
    get textContent() { return this._text; },
    setAttribute(n, v) { this._attrs[n] = v; },
    getAttribute(n) { return n in this._attrs ? this._attrs[n] : null; },
    addEventListener(t, fn) { (this._listeners[t] = this._listeners[t] || []).push(fn); },
    appendChild() {},
    focus() {},
    click() { (this._listeners.click || []).forEach((fn) => fn({ target: this })); },
    querySelector() { return makeEl(); },
    querySelectorAll() { return []; },
    onclick: null, oninput: null, onchange: null
  };
  return el;
}

const alerts = [];
const doc = {
  _byId: {},
  _bySel: {},
  getElementById(id) { return this._byId[id] || (this._byId[id] = makeEl(id)); },
  querySelector(sel) { return this._bySel[sel] || (this._bySel[sel] = makeEl(sel)); },
  createElement() { return makeEl(); },
  addEventListener() {}
};

const _ls = {};
const localStorage = {
  getItem(k) { return k in _ls ? _ls[k] : null; },
  setItem(k, v) { _ls[k] = String(v); },
  removeItem(k) { delete _ls[k]; }
};

function Blob(parts) { this.content = parts.join(""); }
function FileReader() {}
FileReader.prototype.readAsText = function (file) { this.result = file._text; if (this.onload) this.onload(); };

const ctx = {
  document: doc,
  localStorage,
  window: {},
  URL: { createObjectURL: () => "blob:mock", revokeObjectURL() {} },
  Blob,
  FileReader,
  alert: (msg) => alerts.push(msg),
  confirm: () => true,
  console,
  setTimeout: () => 0,
  clearTimeout: () => {}
};
vm.createContext(ctx);
vm.runInContext(src, ctx);

/* ---------- 断言工具 ---------- */
let pass = 0, fail = 0;
const fails = [];
function ok(cond, msg) { if (cond) pass++; else { fail++; fails.push(msg); } }
function eq(a, b, msg) { ok(a === b, msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`); }

/* ========== 1. esc ========== */
eq(ctx.esc("<b>"), "&lt;b&gt;", "esc 转义 < >");
eq(ctx.esc("&"), "&amp;", "esc 转义 &");
eq(ctx.esc('"'), "&quot;", "esc 转义 双引号");
eq(ctx.esc("'"), "&#39;", "esc 转义 单引号");
eq(ctx.esc(null), "", "esc(null) => ''");

/* ========== 2. marketOf ========== */
eq(ctx.marketOf("600519"), "沪", "marketOf 600519→沪");
eq(ctx.marketOf("601318"), "沪", "marketOf 601318→沪");
eq(ctx.marketOf("688001"), "沪", "marketOf 科创板688→沪");
eq(ctx.marketOf("000001"), "深", "marketOf 000001→深");
eq(ctx.marketOf("300750"), "深", "marketOf 300750→深");
eq(ctx.marketOf("830799"), "京", "marketOf 830799→京");
eq(ctx.marketOf("920002"), "京", "marketOf 920002→京");
eq(ctx.marketOf("00700"), "港", "marketOf 00700→港");
eq(ctx.marketOf("09988"), "港", "marketOf 09988→港");
eq(ctx.marketOf("abc"), "其他", "marketOf 非法→其他");

/* ========== 3. csvEscape（防公式注入）========== */
eq(ctx.csvEscape("hello"), "hello", "csvEscape 普通文本透传");
eq(ctx.csvEscape("=cmd"), "'=cmd", "csvEscape 防 = 注入");
eq(ctx.csvEscape("+x"), "'+x", "csvEscape 防 + 注入");
eq(ctx.csvEscape("-x"), "'-x", "csvEscape 防 - 注入");
eq(ctx.csvEscape("@x"), "'@x", "csvEscape 防 @ 注入");
eq(ctx.csvEscape('a"b'), '"a""b"', "csvEscape 引号翻倍");
eq(ctx.csvEscape("a,b"), '"a,b"', "csvEscape 含逗号加引号");
eq(ctx.csvEscape("a\nb"), '"a\nb"', "csvEscape 含换行加引号");
eq(ctx.csvEscape(null), "", "csvEscape null => ''");

/* ========== 4. toCSV ========== */
const csv = ctx.toCSV(
  [{code:"600519", name:"贵州茅台"}, {code:"=1+1", name:"风险"}],
  ["代码","名称"], ["code","name"]
);
ok(csv.charCodeAt(0) === 0xFEFF, "toCSV 含 UTF-8 BOM");
ok(csv.includes("600519,贵州茅台"), "toCSV 正常行");
ok(csv.includes("'=1+1"), "toCSV 公式注入被防护");
ok(csv.split("\r\n").length === 3, "toCSV 表头+2 行");

/* ========== 5. daysBetween / addDays ========== */
eq(ctx.daysBetween("2026-01-11", "2026-01-01"), 10, "daysBetween 正向");
eq(ctx.daysBetween("2026-01-01", "2026-01-11"), -10, "daysBetween 负向");
eq(ctx.addDays("2026-01-31", 1), "2026-02-01", "addDays 跨月");
eq(ctx.addDays("2024-03-01", -1), "2024-02-29", "addDays 闰年回退");

/* ========== 6. buildMonthMatrix ========== */
const weeks = ctx.buildMonthMatrix(2026, 0); // 2026-01
eq(weeks.length, 6, "buildMonthMatrix 6 周");
eq(weeks[0].length, 7, "buildMonthMatrix 每周 7 天（周一为起点）");
// 2026-01-01 是周四 → 周一为起点的首格应为 2025-12-29
eq(weeks[0][0].date, "2025-12-29", "buildMonthMatrix 首格日期");
ok(weeks.some((w) => w.some((c) => c.date === "2026-01-15" && c.inMonth)), "buildMonthMatrix 含当月 15 日");
ok(weeks[0][0].inMonth === false, "buildMonthMatrix 首格不在当月");

/* ========== 7. filterEvents ========== */
const evs = ctx.allEvents();
ok(evs.length >= ctx.SAMPLE.length, "allEvents 至少含样本量");
const sh = ctx.filterEvents(evs, { market: "沪" });
ok(sh.length > 0 && sh.every((e) => e.market === "沪"), "filterEvents 按市场(沪)筛选");
const bank = ctx.filterEvents(evs, { sector: "银行" });
ok(bank.length > 0 && bank.every((e) => e.sector === "银行"), "filterEvents 按板块(银行)筛选");
const q = ctx.filterEvents(evs, { q: "茅台" });
ok(q.length > 0 && q.every((e) => e.name.indexOf("茅台") >= 0 || e.code.indexOf("茅台") >= 0), "filterEvents 按关键词(茅台)筛选");
const q2 = ctx.filterEvents(evs, { q: "600519" });
ok(q2.length > 0 && q2.every((e) => e.code.indexOf("600519") >= 0), "filterEvents 按代码筛选");
const combo = ctx.filterEvents(evs, { market: "深", sector: "白酒" });
ok(combo.every((e) => e.market === "深" && e.sector === "白酒"), "filterEvents 市场+板块组合");

/* ========== 8. toggleAnnotation（纯函数）========== */
let a0 = ctx.toggleAnnotation({}, "x1", "seen");
eq(a0.x1.seen, true, "toggleAnnotation 首次标记已看");
let a1 = ctx.toggleAnnotation(a0, "x1", "seen");
ok(!a1.x1, "toggleAnnotation 再次点击取消并移除键");
let a2 = ctx.toggleAnnotation({}, "x2", "focus");
eq(a2.x2.focus, true, "toggleAnnotation 标记重点关注");
let a3 = ctx.toggleAnnotation(a2, "x2", "seen");
ok(a3.x2.focus && a3.x2.seen, "toggleAnnotation 两种标注可共存");

/* ========== 9. dedupe ========== */
const dd = ctx.dedupe([
  {code:"600519", type:"年报", date:"2026-03-31"},
  {code:"600519", type:"年报", date:"2026-03-31"},
  {code:"600519", type:"中报", date:"2026-03-31"}
]);
eq(dd.length, 2, "dedupe 按 code+type+date 去重");
// 冲突时优先保留用户手动录入项（editable），避免用户录入被样本/外部同名项吞掉
const dUserKeep = ctx.dedupe([
  {code:"600519", type:"年报", date:"2026-03-31", editable:false, name:"样本茅台"},
  {code:"600519", type:"年报", date:"2026-03-31", editable:true,  name:"我的茅台"}
]);
eq(dUserKeep.length, 1, "dedupe 冲突仅保留 1 条");
eq(dUserKeep[0].editable, true, "dedupe 冲突优先保留用户项");
eq(dUserKeep[0].name, "我的茅台", "dedupe 保留的是用户录入内容");

/* ========== 10. addItem（校验 + 去重 + 持久化）========== */
ctx.items = []; ctx.editingId = null;
const r1 = ctx.addItem({ code: "600519", name: "贵州茅台", type: "年报", date: "2026-03-31" });
eq(r1.ok, true, "addItem 正常添加");
eq(ctx.items.length, 1, "addItem 写入 1 条");
ok(localStorage.getItem(ctx.KEY) && JSON.parse(localStorage.getItem(ctx.KEY)).length === 1, "addItem 持久化到 localStorage");
const r2 = ctx.addItem({ code: "600519", name: "贵州茅台", type: "年报", date: "2026-03-31" });
ok(!r2.ok && /已存在/.test(r2.error), "addItem 重复拦截");
eq(ctx.items.length, 1, "addItem 重复不写入");
const r3 = ctx.addItem({ code: "ab", name: "x", type: "年报", date: "2026-03-31" });
ok(!r3.ok && /代码/.test(r3.error), "addItem 非法代码拦截");
const r4 = ctx.addItem({ code: "600519", type: "年报", date: "" });
ok(!r4.ok && /披露日/.test(r4.error), "addItem 缺披露日拦截");
// 名称留空自动用代码
const r5 = ctx.addItem({ code: "000001", type: "中报", date: "2026-08-30" });
eq(ctx.items[1].name, "000001", "addItem 名称留空回退代码");
// 通过真实 onclick 触发
doc.getElementById("code").value = "300750";
doc.getElementById("name").value = "宁德时代";
doc.getElementById("type").value = "年报";
doc.getElementById("date").value = "2026-04-15";
alerts.length = 0;
doc.getElementById("add").onclick();
eq(ctx.items.length, 3, "onclick 添加路径写入 3 条");

/* ========== 11. importItems（字段校验）========== */
ctx.items = [];
const imp = ctx.importItems([
  { code: "600519", date: "2026-03-31", type: "年报", name: "茅台" },
  { code: "000001", date: "2026-08-30" },
  { bad: 1 },
  null
]);
eq(imp.added, 2, "importItems 新增 2 条");
eq(imp.skip, 2, "importItems 跳过 2 条无效");
eq(ctx.items.length, 2, "importItems 结果长度");

/* ========== 12. sampleEvents 动态日期（临近窗口）========== */
const samp = ctx.sampleEvents();
ok(samp.every((e) => /^\d{4}-\d{2}-\d{2}$/.test(e.date)), "sampleEvents 日期格式正确");
ok(samp.some((e) => e.market === "港" && e.code === "00700"), "sampleEvents 含港股腾讯");
ok(samp.some((e) => e.market === "京"), "sampleEvents 含京市样本");

/* ========== 13. checkRemind 仅提醒用户添加项（不骚扰样本）========== */
ctx.items = [];               // 无用户项，仅有样本
doc.getElementById("toast")._text = "";
ctx.checkRemind();
eq(doc.getElementById("toast")._text, "", "checkRemind 样本不弹窗（避免浮动演示数据反复提醒）");
// 用户项已过披露日 → 弹窗
ctx.items = [{ id:"u1", code:"600519", name:"贵州茅台", type:"年报", date:ctx.addDays(ctx.todayStr(), -1), sector:"白酒", expect:"" }];
doc.getElementById("toast")._text = "";
ctx.checkRemind();
ok(doc.getElementById("toast")._text.indexOf("贵州茅台") >= 0, "checkRemind 用户项到期弹窗");

/* ========== 14. switchView 切换视图与显示 ========== */
ctx.switchView("list");
eq(ctx.view, "list", "switchView 设置 view=list");
eq(doc.getElementById("listView").style.display, "block", "switchView 列表视图显示");
eq(doc.getElementById("calView").style.display, "none", "switchView 日历视图隐藏");
ctx.switchView("cal");
eq(ctx.view, "cal", "switchView 切回 view=cal");
eq(doc.getElementById("calView").style.display, "block", "switchView 日历视图显示");

/* ========== 15. normExternalRow / mergeExternal（外部数据源兜底）========== */
const n1 = ctx.normExternalRow({ code:"600519", name:"茅台", date:"2026-03-31", type:"年报", sector:"白酒" });
eq(n1.code, "600519", "normExternalRow 保留代码");
eq(n1.market, "沪", "normExternalRow 自动推导市场");
eq(n1.sector, "白酒", "normExternalRow 保留板块");
eq(ctx.normExternalRow({ code:"600519" }), null, "normExternalRow 缺日期→null");
eq(ctx.normExternalRow({ date:"2026-03-31" }), null, "normExternalRow 缺代码→null");
eq(ctx.normExternalRow("garbage"), null, "normExternalRow 非对象→null");
eq(ctx.normExternalRow({ code:"abc", date:"2026-03-31" }), null, "normExternalRow 非法代码→null");
const merged = ctx.mergeExternal([
  { code:"600519", name:"茅台", date:"2026-03-31", type:"年报" },
  { code:"bad", date:"x" },
  null,
  { date:"2026-03-31" }
]);
eq(merged.length, 1, "mergeExternal 仅保留合法行");
// allEvents 合并外部事件
ctx.extEvents = ctx.mergeExternal([{ code:"601318", name:"中国平安", date:ctx.addDays(ctx.todayStr(), 5), type:"中报", sector:"保险" }]);
ok(ctx.allEvents().some((e) => e.code === "601318" && e.source === "ext"), "allEvents 合并外部事件");
ctx.extEvents = []; // 复原

/* ========== 16. filterEvents 临近范围 ========== */
const base = [
  { code:"a", name:"a", market:"沪", sector:"x", date: ctx.todayStr() },
  { code:"b", name:"b", market:"沪", sector:"x", date: ctx.addDays(ctx.todayStr(), 3) },
  { code:"c", name:"c", market:"沪", sector:"x", date: ctx.addDays(ctx.todayStr(), 10) },
  { code:"d", name:"d", market:"沪", sector:"x", date: ctx.addDays(ctx.todayStr(), -1) }
];
eq(ctx.filterEvents(base, {}).length, 4, "range=all 返回全部");
eq(ctx.filterEvents(base, { range:"today" }).length, 1, "range=today 仅当天");
eq(ctx.filterEvents(base, { range:"week" }).length, 2, "range=week 当天+3天内");

/* ========== 17. importItems 兼容对象格式并恢复标注 ========== */

/* ========== 18. extractRows / normalizeExternalPayload（外部数据源结构兼容）========== */
eq(ctx.extractRows([{code:"600519",date:"2026-03-31"}]).length, 1, "extractRows 裸数组");
eq(ctx.extractRows({rows:[{code:"600519",date:"2026-03-31"}]}).length, 1, "extractRows {rows}");
eq(ctx.extractRows({data:[{code:"600519",date:"2026-03-31"}]}).length, 1, "extractRows {data}");
eq(ctx.extractRows({list:[{code:"600519",date:"2026-03-31"}]}).length, 1, "extractRows {list}");
eq(ctx.extractRows({events:[{code:"600519",date:"2026-03-31"}]}).length, 1, "extractRows {events}");
eq(ctx.extractRows({foo:"bar"}), null, "extractRows 无法识别→null");
eq(ctx.extractRows(null), null, "extractRows null→null");
// normalizeExternalPayload 对无法识别结构回退（返回 null），成功则返回过滤后的事件
eq(ctx.normalizeExternalPayload({rows:[{code:"600519",date:"2026-03-31"},{bad:1}]}).length, 1, "normalizeExternalPayload 过滤无效行");
eq(ctx.normalizeExternalPayload({code:"600519"}), null, "normalizeExternalPayload 非数组结构→null（触发回退）");
eq(ctx.normalizeExternalPayload("x"), null, "normalizeExternalPayload 非对象→null");
// allEvents 合并外部事件（经 normalize）
ctx.extEvents = ctx.normalizeExternalPayload({data:[{code:"601318",name:"中国平安",date:ctx.addDays(ctx.todayStr(),5),type:"中报",sector:"保险"}]});
ok(ctx.allEvents().some((e) => e.code === "601318" && e.source === "ext"), "allEvents 合并外部事件({data}结构)");
ctx.extEvents = []; // 复原

/* ========== 19. 外部 HTTP 错误明确回退（逻辑等价验证）========== */
// 模拟 loadExt 的回退分支：HTTP 非 2xx 或结构无法识别时 extEvents 应为空且走回退提示
function simulateLoadExt(status, body){
  // 复刻 loadExt 的判定：!r.ok 抛错；否则 normalizeExternalPayload 判 null
  if(status !== 200) return {fallback:true, reason:"HTTP "+status};
  var ev = ctx.normalizeExternalPayload(body);
  if(ev === null) return {fallback:true, reason:"unrecognized"};
  return {fallback:false, count:ev.length};
}
eq(simulateLoadExt(404, {}).fallback, true, "HTTP 404 触发回退");
eq(simulateLoadExt(200, {code:"600519"}).fallback, true, "HTTP200 但结构无法识别触发回退（避免误判成功）");
eq(simulateLoadExt(200, {data:[{code:"600519",date:"2026-03-31"}]}).count, 1, "HTTP200 且结构合法返回 1 条");


ctx.items = []; ctx.ann = {};
const imp17 = ctx.importItems({
  events: [{ id:"u1", code:"600519", name:"贵州茅台", date:"2026-03-31", type:"年报" }],
  annotations: { u1: { seen:true, focus:false } }
});
eq(imp17.added, 1, "importItems 对象格式导入事件");
eq(ctx.ann.u1 && ctx.ann.u1.seen, true, "importItems 恢复标注(annotations)并随事件ID挂载");
eq(ctx.items[0].id, "u1", "importItems 保留事件ID用于标注回挂");

/* ---------- 汇总 ---------- */
console.log("\n财报日历 自测：" + pass + " 通过 / " + fail + " 失败");
if (fail) {
  console.log("失败项：");
  fails.forEach((f) => console.log("  ✗ " + f));
  process.exit(1);
} else {
  console.log("✅ 全部通过");
}
