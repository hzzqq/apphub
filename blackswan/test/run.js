/*
 * BlackSwan Archive 逻辑自测脚手架（零依赖，仅用 Node 内置 vm/fs）。
 * 加载 index.html 内联脚本，注入最小 DOM / localStorage 桩，
 * 通过 globalThis.__BS_TEST__ 暴露的纯函数断言（筛选/排序/校验/导入导出）。
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

// ---------- 最小 DOM 桩 ----------
function makeEl() {
  const el = {
    _html: "", _value: "", _text: "", _attrs: {}, _listeners: {}, style: {},
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      toggle(c, on) { on ? this._s.add(c) : this._s.delete(c); },
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
    appendChild() {}, click() {},
    querySelector() { return makeEl(); },
    querySelectorAll() { return []; },
    onclick: null
  };
  return el;
}
const alerts = [];
const doc = {
  _byId: {},
  getElementById(id) { return this._byId[id] || (this._byId[id] = makeEl()); },
  querySelector() { return makeEl(); },
  querySelectorAll() { return []; },
  addEventListener() {},
  createElement() { return makeEl(); }
};
const _ls = {};
const localStorage = {
  getItem(k) { return k in _ls ? _ls[k] : null; },
  setItem(k, v) { _ls[k] = String(v); },
  removeItem(k) { delete _ls[k]; }
};
function Blob(parts) { this.content = parts.join(""); }

const ctx = {
  document: doc,
  localStorage,
  Blob,
  URL: { createObjectURL: () => "blob:mock", revokeObjectURL() {} },
  alert: (msg) => alerts.push(msg),
  navigator: { clipboard: null },
  console,
  setTimeout: () => 0,
  clearTimeout: () => {},
  Date,
  Math,
  JSON,
  Array,
  Object,
  Set,
  isFinite,
  parseFloat
};
ctx.window = ctx;
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(src, ctx);

const T = ctx.__BS_TEST__;
if (!T) throw new Error("脚本未暴露 __BS_TEST__，请检查 globalThis 钩子");

// ---------- 断言工具 ----------
let pass = 0, fail = 0;
const fails = [];
function ok(cond, msg) { if (cond) pass++; else { fail++; fails.push(msg); } }
function eq(a, b, msg) { ok(a === b, msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`); }

// ---------- 1. 内置库完整性 ----------
ok(Array.isArray(T.EVENTS) && T.EVENTS.length >= 28, "内置事件库 >=28 条 (" + T.EVENTS.length + ")");
ok(T.EVENTS.every(e => T.validateEvent(e).ok), "全部内置事件通过校验");
eq(new Set(T.EVENTS.map(e => e.id)).size, T.EVENTS.length, "内置事件 id 唯一");
["e1982-latam", "e1992-blackweds", "e1994-bond", "e1998-russia", "e1998-ltcm", "e2008-iceland", "e2022-ukgilt", "e2023-svb"].forEach(id => {
  ok(T.EVENTS.some(e => e.id === id), "新增事件存在: " + id);
});

// ---------- 2. 筛选 ----------
ok(T.filterEvents(T.EVENTS, { market: "cn" }).every(e => (e.markets || []).includes("cn")), "按市场(A股)筛选正确");
ok(T.filterEvents(T.EVENTS, { market: "us" }).every(e => (e.markets || []).includes("us")), "按市场(美股)筛选正确");
ok(T.filterEvents(T.EVENTS, { sev: "high" }).every(e => e.sev === "high"), "按高危筛选正确");
ok(T.filterEvents(T.EVENTS, { cat: "company" }).every(e => e.cat === "company"), "按公司类别筛选正确");
ok(T.filterEvents(T.EVENTS, { cat: "macro" }).every(e => e.cat === "macro"), "按系统性类别筛选正确");
ok(T.filterEvents(T.EVENTS, { q: "原油" }).length > 0, "关键词“原油”可命中");
ok(T.filterEvents(T.EVENTS, { q: "雷曼" }).length > 0, "关键词“雷曼”可命中");
{
  const r = T.filterEvents(T.EVENTS, { dateFrom: "2015-01-01", dateTo: "2016-12-31" });
  ok(r.every(e => e.date === "-" || (e.date >= "2015-01-01" && e.date <= "2016-12-31")), "日期区间筛选正确");
}
{
  const r = T.filterEvents(T.EVENTS, { q: "不存在的关键词xyz" });
  eq(r.length, 0, "无命中关键词返回空");
}

// ---------- 2b. 多关键词 AND + 按年份检索 ----------
{
  // 多关键词 AND：同时包含“原油”与“负价”才算命中
  const and = T.filterEvents(T.EVENTS, { q: "原油 负价" });
  ok(and.length > 0 && and.every(e => (e.title + e.impact + e.desc + (e.sectors || []).join(" ")).includes("原油") && (e.title + e.impact + e.desc + (e.sectors || []).join(" ")).includes("负价")), "多关键词 AND 全部命中");
  // 矛盾关键词应返回空
  const contradiction = T.filterEvents(T.EVENTS, { q: "原油 不存在词zzz" });
  eq(contradiction.length, 0, "矛盾多关键词返回空");
  // 按年份检索：2015 应命中 2015 年股灾
  const yr = T.filterEvents(T.EVENTS, { q: "2015" });
  ok(yr.some(e => (e.date || "").startsWith("2015")), "按年份 2015 命中当年事件");
  // 单关键词仍兼容
  const single = T.filterEvents(T.EVENTS, { q: "雷曼" });
  ok(single.length > 0, "单关键词“雷曼”仍命中");
}

// ---------- 3. 排序 ----------
{
  const byImpact = T.sortEvents(T.EVENTS, "impact");
  const idxNull = byImpact.findIndex(e => e.drop == null);
  const idxNum = byImpact.findIndex(e => e.drop != null);
  ok(idxNum === -1 || idxNull === -1 || idxNum < idxNull, "按冲击幅度排序：有数值在前");
  const bySev = T.sortEvents(T.EVENTS, "sev");
  ok((T.SEV_W[bySev[0].sev] || 0) >= (T.SEV_W[bySev[bySev.length - 1].sev] || 0), "按等级排序降序");
  const byDate = T.sortEvents(T.EVENTS, "date");
  let mono = true;
  for (let i = 1; i < byDate.length; i++) { if ((byDate[i - 1].date || "") < (byDate[i].date || "")) { mono = false; break; } }
  ok(mono, "按日期排序：新→旧单调");
}

// ---------- 4. 校验 ----------
ok(!T.validateEvent({ title: "", sev: "high", markets: ["cn"] }).ok, "空标题被拒");
ok(!T.validateEvent({ title: "x", sev: "x", markets: ["cn"] }).ok, "非法等级被拒");
ok(!T.validateEvent({ title: "x", sev: "high", markets: [] }).ok, "空市场被拒");
ok(!T.validateEvent({ title: "x", sev: "high", markets: ["cn"], date: "2021/01/01" }).ok, "非法日期被拒");
ok(T.validateEvent({ title: "x", sev: "high", markets: ["cn"] }).ok, "合法事件通过");

// ---------- 5. normalizeEvent ----------
{
  const n = T.normalizeEvent({ title: "测试", sev: "mid", markets: ["us", "bad"], sectors: "a,b,c", drop: "45" }, true);
  ok(n.markets.length === 1 && n.markets[0] === "us", "normalize 过滤非法市场");
  eq(n.sectors.length, 3, "normalize 拆分 sectors");
  eq(n.drop, 45, "normalize 解析数值 drop");
  ok(n._custom === true, "normalize 标记 custom");
}

// ---------- 6. 导入导出往返 ----------
{
  const before = T.CUSTOM.length;
  const r = T.importData([{ id: "t1", title: "测试事件", sev: "mid", markets: ["us"], date: "2021-01-01", impact: "x", sectors: "测试" }, { id: "bad", title: "", sev: "high", markets: ["cn"] }]);
  eq(r.added, 1, "导入新增 1 条合法事件");
  eq(r.skipped, 1, "导入跳过 1 条非法事件");
  eq(T.CUSTOM.length, before + 1, "导入后 custom 长度 +1");
  const exp = T.buildExport();
  ok(exp.events.some(e => e.id === "t1"), "导出包含刚导入事件");
  ok(exp.app === "blackswan-archive" && exp.version === 1, "导出结构含 app/version");
  // 按 id 覆盖
  T.importData([{ id: "t1", title: "测试事件(改)", sev: "high", markets: ["us"], date: "2021-01-01" }]);
  const upd = T.CUSTOM.find(e => e.id === "t1");
  eq(upd.title, "测试事件(改)", "再次导入按 id 覆盖");
  eq(upd.sev, "high", "覆盖更新 sev");
  // 清理
  T.CUSTOM = T.CUSTOM.filter(e => e.id !== "t1"); localStorage.setItem("bs_custom", JSON.stringify(T.CUSTOM));
  eq(T.CUSTOM.length, before, "清理测试数据");
}

// ---------- 7. 浏览器内自检函数一致性 ----------
{
  const sr = T.runSelfTest(false);
  ok(sr.fail === 0 && sr.total > 0, "runSelfTest 内置断言全通过 (" + sr.pass + "/" + sr.total + ")");
}

// ---------- 8. 时间快捷预设 ----------
{
  const all = T.presetToDate("all");
  eq(all, "", "预设“不限”=> 空串");
  const y2000 = T.presetToDate("2000");
  eq(y2000, "2000-01-01", "预设“2000年后”=> 2000-01-01");
  const d5 = T.presetToDate("5y");
  ok(/^\d{4}-\d{2}-\d{2}$/.test(d5) && parseInt(d5.slice(0,4),10) === (new Date().getFullYear() - 5), "预设“近5年”≈ 当前-5年");
  const d10 = T.presetToDate("10y");
  ok(parseInt(d10.slice(0,4),10) === (new Date().getFullYear() - 10), "预设“近10年”≈ 当前-10年");
  // 预设与筛选联动
  const r = T.filterEvents(T.EVENTS, { dateFrom: "2000-01-01" });
  ok(r.every(e => e.date === "-" || e.date >= "2000-01-01"), "“2000年后”预设筛选正确");
}

// ---------- 9. 文本摘要（复制分享）----------
{
  const txt = T.buildText(T.EVENTS.slice(0, 2));
  ok(txt.includes("黑天鹅档案"), "文本摘要含标题头");
  ok(txt.includes("共 2 条"), "文本摘要含计数");
  ok(/1\.\s*\[/.test(txt), "文本摘要含编号条目");
  ok(!txt.includes("<b>"), "文本摘要剔除 HTML 标签");
  const big = T.buildText(T.EVENTS);
  ok(big.split("\n").length >= T.EVENTS.length + 1, "文本摘要覆盖全部事件");
}

// ---------- 10. 用户记录新增/编辑（upsertCustom）----------
{
  const before = T.CUSTOM.length;
  const r1 = T.upsertCustom({ id: "u1", title: "我的事件", sev: "mid", markets: ["cn"], date: "2022-03-01", impact: "x", sectors: "测试" });
  ok(r1.ok && T.CUSTOM.length === before + 1, "upsertCustom 新增一条");
  ok(T.CUSTOM.some(e => e.id === "u1"), "新增记录含 id=u1");
  // 同 id 更新（编辑）
  const r2 = T.upsertCustom({ id: "u1", title: "我的事件(改)", sev: "high", markets: ["cn"], date: "2022-03-01" });
  ok(r2.ok && T.CUSTOM.length === before + 1, "同 id 更新不新增");
  eq(T.CUSTOM.find(e => e.id === "u1").title, "我的事件(改)", "更新写入新标题");
  eq(T.CUSTOM.find(e => e.id === "u1").sev, "high", "更新写入新等级");
  // 非法被拒
  const r3 = T.upsertCustom({ id: "u2", title: "", sev: "high", markets: ["cn"] });
  ok(!r3.ok, "upsertCustom 非法输入被拒");
  // 清理
  T.CUSTOM = T.CUSTOM.filter(e => e.id !== "u1"); localStorage.setItem("bs_custom", JSON.stringify(T.CUSTOM));
  eq(T.CUSTOM.length, before, "清理测试数据");
}

// ---------- 11. CSV 导出（BOM + 防公式注入）----------
{
  const csv = T.buildCsv(T.EVENTS.slice(0, 3));
  ok(csv.charCodeAt(0) === 0xFEFF, "CSV 带 BOM（Excel 中文不乱码）");
  ok(csv.includes("日期") && csv.includes("标题"), "CSV 含表头");
  const guarded = T.csvCell("=cmd");
  ok(guarded === "'=cmd", "csvCell 防 = 注入");
  const quoted = T.csvCell('a"b,c');
  ok(quoted === '"a""b,c"', "csvCell 引号/逗号转义");
  const pure = T.csvCell(null);
  ok(pure === "", "csvCell(null) => 空串");
  // 冲击描述中的 HTML 标签应在 CSV 中被剔除
  const ev = [{ date: "2020-01-01", cat: "macro", sev: "high", markets: ["cn"], title: "X", drop: 5, impact: "下跌 <b>5%</b>", sectors: ["A"], desc: "<p>d</p>", source: "s" }];
  ok(!T.buildCsv(ev).includes("<b>"), "CSV 剔除 HTML 标签");
}

// ---------- 12. 冲击描述 XSS 加固（sanitizeImpact）----------
{
  const clean = T.sanitizeImpact('下跌 <b>5%</b>');
  ok(clean === "下跌 <b>5%</b>", "sanitizeImpact 保留合法 <b> 高亮");
  const xss = T.sanitizeImpact('<img src=x onerror=alert(1)> 暴跌');
  ok(!/<img/i.test(xss) && !/onerror/i.test(xss), "sanitizeImpact 剥离 <img onerror> 注入");
  ok(!/[<>]/.test(xss), "sanitizeImpact 结果不含任何原始尖括号");
  const script = T.sanitizeImpact('<script>alert(1)</script>');
  ok(!/<script/i.test(script), "sanitizeImpact 剥离 <script>");
  // 大小写/空格变体的 <b>
  eq(T.sanitizeImpact('<B>高</B>'), "<b>高</b>", "sanitizeImpact 归一化 <B> 标签");
  // 内置事件的 <b> 高亮在渲染后仍合法保留
  const builtinWithB = T.EVENTS.find(e => /<b>/.test(e.impact || ""));
  ok(builtinWithB && T.sanitizeImpact(builtinWithB.impact).includes("<b>"), "内置事件 <b> 高亮经加固仍保留");
}

// ---------- 13. 筛选状态持久化（刷新后保留）----------
{
  T.setState({ q: "原油", market: "cn", sev: "high", cat: "macro", dateFrom: "2015-01-01", dateTo: "", sort: "impact" });
  T.saveFilterState();
  const saved = JSON.parse(localStorage.getItem("bs_filter"));
  ok(saved.q === "原油" && saved.market === "cn" && saved.dateFrom === "2015-01-01", "saveFilterState 持久化筛选");
  // 模拟刷新：清空内存态后 load
  T.setState({ q: "", market: "all", sev: "all", cat: "all", dateFrom: "", dateTo: "", sort: "date" });
  T.loadFilterState();
  const st = T.getState();
  ok(st.q === "原油" && st.market === "cn" && st.dateFrom === "2015-01-01" && st.sort === "impact", "loadFilterState 恢复筛选");
  // 损坏数据兜底
  localStorage.setItem("bs_filter", "{bad json");
  T.setState({ q: "x" });
  T.loadFilterState();
  eq(T.getState().q, "x", "loadFilterState 损坏数据不污染内存态");
  localStorage.removeItem("bs_filter");
}

// ---------- 14. 检索命中高亮（highlight）----------
{
  const h = T.highlight("原油价格暴跌", ["原油"]);
  ok(/<mark>原油<\/mark>/.test(h), "highlight 包裹命中关键词生成 <mark>");
  const h2 = T.highlight("<script>x</script> 原油", ["原油"]);
  ok(h2.includes("&lt;script&gt;") && /<mark>原油<\/mark>/.test(h2) && !/<script/i.test(h2), "highlight 先转义后高亮，无注入");
  eq(T.highlight("普通文本", []), "普通文本", "highlight 无关键词原样转义返回");
  eq(T.highlight("a&b", []), "a&amp;b", "highlight 无关键词仍转义");
  // 多关键词 OR 高亮
  const h3 = T.highlight("原油与黄金", ["原油", "黄金"]);
  ok((h3.match(/<mark>/g) || []).length === 2, "highlight 多关键词分别高亮");
}

// ---------- 结果 ----------
console.log(`\n通过 ${pass} 项，失败 ${fail} 项`);
if (fail) {
  console.log("失败明细：");
  fails.forEach(f => console.log("  - " + f));
  process.exit(1);
} else {
  console.log("全部逻辑自测通过 ✅");
}
