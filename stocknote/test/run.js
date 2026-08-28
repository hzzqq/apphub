/*
 * StockNote 逻辑自测脚手架（零依赖，仅用 Node 内置 vm/fs）。
 * 加载 index.html 内联脚本，注入最小 DOM / localStorage 桩，
 * 把内部函数（sanitize/csvCell/esc/load/render 等）暴露为 vm 全局后断言。
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
let src = m[1];
// 去掉 IIFE 包裹，使内部 var/function 成为 vm 全局，便于断言
src = src.replace(/^\s*\(function\(\)\s*\{/, "");
src = src.replace(/\}\)\(\)\s*;?\s*$/, "");

// ---------- 最小 DOM 桩 ----------
let lastBlob = null;
let lastClipboard = null;

function makeEl(id) {
  const el = {
    id: id || "",
    _html: "", _value: "", _text: "", _attrs: {}, _listeners: {},
    style: {},
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
    querySelector(sel) { return doc.querySelector(sel); },
    click() { (this._listeners.click || []).forEach((fn) => fn({ target: this })); },
    onclick: null
  };
  return el;
}

const toastMsg = makeEl("toast-msg");
const toastUndo = makeEl("toast-undo");

const radios = {};
const labels = {};
["up", "down", "memo"].forEach((t) => {
  const input = { value: t, checked: t === "up" };
  const label = makeEl("l-" + t);
  label.querySelector = (sel) => (sel === "input" ? input : makeEl());
  labels[t] = label;
  radios[t] = input;
});
function checkedRadio() {
  for (const t of ["up", "down", "memo"]) if (radios[t].checked) return radios[t];
  return radios.up;
}

const alerts = [];
const doc = {
  _byId: {},
  getElementById(id) { return this._byId[id] || (this._byId[id] = makeEl(id)); },
  querySelector(sel) {
    if (sel === ".l-up") return labels.up;
    if (sel === ".l-down") return labels.down;
    if (sel === ".l-memo") return labels.memo;
    if (sel === "input[name=ftype]:checked") return checkedRadio();
    if (sel === ".toast-msg") return toastMsg;
    if (sel === ".toast-undo") return toastUndo;
    return makeEl();
  },
  addEventListener(t, fn) { (this._listeners = this._listeners || {})[t] = (this._listeners[t] || []).concat(fn); },
  _listeners: {},
  createElement() { return makeEl(); }
};

const _ls = {};
const localStorage = {
  getItem(k) { return k in _ls ? _ls[k] : null; },
  setItem(k, v) { _ls[k] = String(v); },
  removeItem(k) { delete _ls[k]; }
};

function Blob(parts) { this.parts = parts; this.content = parts.join(""); lastBlob = this; }
function FileReader() {}
FileReader.prototype.readAsText = function (file) {
  this.result = file._text;
  if (this.onload) this.onload();
};

const ctx = {
  document: doc,
  localStorage,
  window: { scrollTo() {} },
  URL: { createObjectURL: () => "blob:mock", revokeObjectURL() {} },
  Blob,
  FileReader,
  alert: (msg) => alerts.push(msg),
  console,
  setTimeout: () => 0,
  clearTimeout: () => {}
};
vm.createContext(ctx);
vm.runInContext(src, ctx);

// ---------- 断言工具 ----------
let pass = 0, fail = 0;
const fails = [];
function ok(cond, msg) { if (cond) pass++; else { fail++; fails.push(msg); } }
function eq(a, b, msg) {
  ok(a === b, msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`);
}

// ---------- 1. sanitize ----------
const s1 = ctx.sanitize({ id: "x", code: "600519", name: "茅台", date: "2024-01-01", type: "up", content: "c", createdAt: 1 });
eq(s1.id, "x", "sanitize 保留 id");
eq(s1.type, "up", "sanitize 保留 type");
eq(s1.content, "c", "sanitize 保留 content");
eq(ctx.sanitize(null), null, "sanitize(null) => null");
eq(ctx.sanitize(undefined), null, "sanitize(undefined) => null");
eq(ctx.sanitize({ type: "bogus" }).type, "memo", "sanitize 非法 type 归为 memo");
eq(ctx.sanitize({}).type, "memo", "sanitize 缺字段 type=memo");
ok(ctx.sanitize({}).id && typeof ctx.sanitize({}).id === "string", "sanitize 缺 id 自动生成");
eq(ctx.sanitize({ content: 123 }).content, "123", "sanitize content 转字符串");
eq(ctx.sanitize({ code: null }).code, "", "sanitize null code => ''");

// ---------- 2. csvCell ----------
eq(ctx.csvCell("hello"), "hello", "csvCell 普通文本透传");
eq(ctx.csvCell("=cmd"), "'=cmd", "csvCell 防 = 注入");
eq(ctx.csvCell("+x"), "'+x", "csvCell 防 + 注入");
eq(ctx.csvCell("-x"), "'-x", "csvCell 防 - 注入");
eq(ctx.csvCell("@x"), "'@x", "csvCell 防 @ 注入");
eq(ctx.csvCell('a"b'), '"a""b"', "csvCell 引号翻倍");
eq(ctx.csvCell("a,b"), '"a,b"', "csvCell 含逗号加引号");
eq(ctx.csvCell("a\nb"), '"a\nb"', "csvCell 含换行加引号");
eq(ctx.csvCell(null), "", "csvCell null => ''");
eq(ctx.csvCell("中文"), "中文", "csvCell 中文透传");

// ---------- 3. esc ----------
eq(ctx.esc("<b>"), "&lt;b&gt;", "esc 转义 < >");
eq(ctx.esc("&"), "&amp;", "esc 转义 &");
eq(ctx.esc('"'), "&quot;", "esc 转义 双引号");

// ---------- 4. load ----------
const KEY = ctx.KEY;
localStorage.setItem(KEY, JSON.stringify([{ id: "i1", code: "1", name: "n", date: "2024-01-01", type: "up", content: "c", createdAt: 1 }]));
let loaded = ctx.load();
eq(loaded.length, 1, "load 正常数组");
eq(loaded[0].id, "i1", "load 解析出记录");
localStorage.setItem(KEY, "{not json");
eq(ctx.load().length, 0, "load 非法 JSON => []");
localStorage.setItem(KEY, JSON.stringify({ a: 1 }));
eq(ctx.load().length, 0, "load 非数组 JSON => []");

// ---------- 5. render（转义 / 空态 / 筛选 / 分组）----------
const sample = [
  { id: "1", code: "600519", name: "茅台", date: "2024-03-01", type: "up", content: '<script>x</script>', createdAt: 1 },
  { id: "2", code: "300750", name: "宁德", date: "2024-02-01", type: "down", content: "利空内容", createdAt: 2 },
  { id: "3", code: "600519", name: "茅台", date: "2024-01-01", type: "memo", content: "备忘", createdAt: 3 }
];
ctx.state.records = sample.slice();
ctx.state.filter = ""; ctx.state.typeFilter = ""; ctx.state.group = false;
ctx.render();
let cardsHtml = doc.getElementById("cards").innerHTML;
ok(cardsHtml.includes("&lt;script&gt;"), "render 转义 XSS 内容");
ok(cardsHtml.includes("茅台") && cardsHtml.includes("宁德"), "render 渲染多条");
// 空态
ctx.state.records = [];
ctx.render();
ok(doc.getElementById("cards").innerHTML.includes("还没有速记卡"), "render 空态提示");
// 内容搜索
ctx.state.records = sample.slice();
ctx.state.filter = "利空"; ctx.state.typeFilter = "";
ctx.render();
ok(doc.getElementById("cards").innerHTML.includes("宁德") && !doc.getElementById("cards").innerHTML.includes("茅台"), "render 内容搜索过滤");
// 类型筛选
ctx.state.filter = ""; ctx.state.typeFilter = "up";
ctx.render();
ok(doc.getElementById("cards").innerHTML.includes("茅台") && !doc.getElementById("cards").innerHTML.includes("宁德"), "render 类型筛选");
// 分组
ctx.state.typeFilter = ""; ctx.state.group = true;
ctx.render();
ok(doc.getElementById("cards").innerHTML.includes("group-title"), "render 分组标题");
ctx.state.group = false;

// ---------- 6. renderStats ----------
ctx.state.records = sample.slice();
ctx.renderStats();
let statsHtml = doc.getElementById("stats").innerHTML;
ok(statsHtml.includes("共") && statsHtml.includes("3"), "renderStats 计数");

// ---------- 7. 保存流程（新增）----------
ctx.state.records = [];
doc.getElementById("editId").value = "";
doc.getElementById("fCode").value = "600519";
doc.getElementById("fName").value = "茅台";
doc.getElementById("fDate").value = "2024-05-01";
radios.up.checked = true; radios.down.checked = false; radios.memo.checked = false;
doc.getElementById("fContent").value = "新高";
doc.getElementById("btnSave")._listeners.click[0]();
eq(ctx.state.records.length, 1, "保存后新增 1 条");
eq(ctx.state.records[0].code, "600519", "保存写入 code");
ok(localStorage.getItem(KEY) && JSON.parse(localStorage.getItem(KEY)).length === 1, "保存后持久化");

// ---------- 8. 保存校验（缺代码和名称）----------
alerts.length = 0;
doc.getElementById("editId").value = "";
doc.getElementById("fCode").value = "";
doc.getElementById("fName").value = "";
ctx.state.records = [];
doc.getElementById("btnSave")._listeners.click[0]();
eq(ctx.state.records.length, 0, "缺代码/名称不保存");
ok(alerts.some((a) => a.includes("代码或名称")), "缺字段给出提示");

// ---------- 9. 编辑流程 ----------
const target = { id: "e1", code: "OLD", name: "旧", date: "2024-01-01", type: "memo", content: "旧内容", createdAt: 9 };
ctx.state.records = [target];
doc.getElementById("cards")._listeners.click[0]({ target: { getAttribute: (n) => (n === "data-edit" ? "e1" : null) } });
eq(doc.getElementById("editId").value, "e1", "编辑回填 editId");
eq(doc.getElementById("fCode").value, "OLD", "编辑回填 code");
// 修改后保存
doc.getElementById("fCode").value = "NEW";
radios.up.checked = true; radios.down.checked = false; radios.memo.checked = false;
doc.getElementById("fContent").value = "新内容";
doc.getElementById("btnSave")._listeners.click[0]();
eq(ctx.state.records[0].code, "NEW", "编辑更新 code");
eq(ctx.state.records[0].type, "up", "编辑更新 type");

// ---------- 10. 删除 + 撤销 ----------
ctx.state.records = [{ id: "d1", code: "1", name: "n", date: "2024-01-01", type: "up", content: "c", createdAt: 1 }];
doc.getElementById("cards")._listeners.click[0]({ target: { getAttribute: (n) => (n === "data-del" ? "d1" : null) } });
eq(ctx.state.records.length, 0, "删除软移除记录");
ok(toastUndo.onclick && typeof toastUndo.onclick === "function", "删除后挂载撤销处理器");
toastUndo.onclick();
eq(ctx.state.records.length, 1, "撤销恢复记录");

// ---------- 10b. 连续删除 + 一次性撤销（防前序卡片丢失）----------
ctx.state.records = [
  { id: "m1", code: "1", name: "n", date: "2024-01-01", type: "up", content: "c", createdAt: 1 },
  { id: "m2", code: "2", name: "n", date: "2024-01-01", type: "down", content: "c", createdAt: 2 },
  { id: "m3", code: "3", name: "n", date: "2024-01-01", type: "memo", content: "c", createdAt: 3 }
];
var cardsClick = doc.getElementById("cards")._listeners.click[0];
cardsClick({ target: { getAttribute: (n) => (n === "data-del" ? "m1" : null) } });
cardsClick({ target: { getAttribute: (n) => (n === "data-del" ? "m2" : null) } });
cardsClick({ target: { getAttribute: (n) => (n === "data-del" ? "m3" : null) } });
eq(ctx.state.records.length, 0, "连续删除 3 条后列表为空");
toastUndo.onclick();
eq(ctx.state.records.length, 3, "一次性撤销恢复全部 3 条");
ok(ctx.state.records.every((r) => ["m1", "m2", "m3"].includes(r.id)), "撤销恢复了原始 id 集合");

// ---------- 11. 导出 CSV（BOM + 注入防护）----------
lastBlob = null;
ctx.state.records = [
  { id: "1", code: "600519", name: "茅台", date: "2024-01-01", type: "up", content: "=cmd", createdAt: 1 },
  { id: "2", code: "300750", name: "宁德", date: "2024-01-01", type: "down", content: 'a"b,c', createdAt: 1 }
];
doc.getElementById("btnExportCsv")._listeners.click[0]();
ok(lastBlob && lastBlob.content.startsWith("﻿"), "CSV 带 BOM");
ok(lastBlob.content.includes("'="), "CSV 防公式注入");
ok(lastBlob.content.includes('"a""b,c"'), "CSV 引号/逗号转义");
ok(lastBlob.content.includes("茅台"), "CSV 含中文");

// ---------- 12. 导出 JSON ----------
lastBlob = null;
doc.getElementById("btnExport")._listeners.click[0]();
ok(lastBlob && JSON.parse(lastBlob.content).length === 2, "导出 JSON 含全部记录");

// ---------- 13. 导入 JSON（合并去重）----------
alerts.length = 0;
const before = ctx.state.records.length;
const fileInput = doc.getElementById("fileInput");
const importJson = JSON.stringify([
  { id: "1", code: "600519", name: "茅台", date: "2024-01-01", type: "up", content: "更新", createdAt: 1 },
  { id: "new", code: "000001", name: "平安", date: "2024-02-02", type: "memo", content: "新", createdAt: 2 }
]);
fileInput._listeners.change[0]({ target: { files: [{ _text: importJson }], value: "x" } });
const byId = {};
ctx.state.records.forEach((r) => (byId[r.id] = r));
eq(byId["1"].content, "更新", "导入按 id 覆盖本地");
ok(byId["new"], "导入新增记录");
alerts.some((a) => a.includes("导入成功"));

// ---------- 14. 导入非法 JSON ----------
alerts.length = 0;
fileInput._listeners.change[0]({ target: { files: [{ _text: "not json" }], value: "x" } });
ok(alerts.some((a) => a.includes("导入失败")), "导入非法 JSON 提示失败");

// ---------- 15. 持久化失败兜底（配额满 / 隐私模式）----------
var origSet = localStorage.setItem;
var persistThrew = false;
localStorage.setItem = function () { persistThrew = true; throw new Error("QuotaExceeded"); };
alerts.length = 0;
ctx.state.records = [];
doc.getElementById("editId").value = "";
doc.getElementById("fCode").value = "600000";
doc.getElementById("fName").value = "浦发";
doc.getElementById("fDate").value = "2024-06-01";
radios.up.checked = true; radios.down.checked = false; radios.memo.checked = false;
doc.getElementById("fContent").value = "x";
doc.getElementById("btnSave")._listeners.click[0]();
ok(persistThrew, "持久化确实被触发");
eq(ctx.state.records.length, 1, "存储失败时内存状态仍保留（未丢失）");
ok(alerts.some((a) => a.includes("保存失败")), "存储失败给出提示");
localStorage.setItem = origSet;

// ---------- 16. 复用卡片（预填表单为新建）----------
ctx.state.records = [{ id: "dup1", code: "600519", name: "茅台", date: "2024-04-01", type: "up", content: "原内容", createdAt: 1 }];
doc.getElementById("cards")._listeners.click[0]({ target: { getAttribute: (n) => (n === "data-dup" ? "dup1" : null) } });
eq(doc.getElementById("editId").value, "", "复用时 editId 为空（新建而非覆盖）");
eq(doc.getElementById("fCode").value, "600519", "复用预填代码");
eq(doc.getElementById("fContent").value, "原内容", "复用预填内容");
eq(doc.getElementById("btnSave").textContent, "保存速记卡", "复用按钮文案为新建");
// 复用后修改并保存 => 新增一条，不覆盖原卡片
doc.getElementById("fContent").value = "复用内容";
radios.down.checked = true; radios.up.checked = false; radios.memo.checked = false;
doc.getElementById("btnSave")._listeners.click[0]();
eq(ctx.state.records.length, 2, "复用保存后新增一条");
var orig = ctx.state.records.find((r) => r.id === "dup1");
eq(orig.content, "原内容", "原卡片未被覆盖");
ok(ctx.state.records.some((r) => r.content === "复用内容" && r.type === "down"), "新卡片按复用表单写入");

// ---------- 17. 键盘快捷键（Ctrl/Cmd+Enter 保存，Esc 取消编辑）----------
ctx.state.records = [];
doc.getElementById("editId").value = "";
doc.getElementById("fCode").value = "000001";
doc.getElementById("fName").value = "平安";
doc.getElementById("fDate").value = "2024-07-01";
radios.memo.checked = true; radios.up.checked = false; radios.down.checked = false;
doc.getElementById("fContent").value = "快捷";
var kd = doc.getElementById("fContent")._listeners.keydown[0];
kd({ ctrlKey: true, key: "Enter", preventDefault() {} });
eq(ctx.state.records.length, 1, "Ctrl+Enter 保存新增一条");
// Esc 取消编辑
ctx.state.records = [{ id: "e2", code: "X", name: "Y", date: "2024-01-01", type: "up", content: "z", createdAt: 1 }];
doc.getElementById("cards")._listeners.click[0]({ target: { getAttribute: (n) => (n === "data-edit" ? "e2" : null) } });
eq(doc.getElementById("editId").value, "e2", "先进入编辑态");
kd({ key: "Escape", preventDefault() {} });
eq(doc.getElementById("editId").value, "", "Esc 取消编辑清空 editId");

// ---------- 18. formatNote / formatNotes / visibleList / 复制为文本 ----------
eq(ctx.formatNote({ code: "600519", name: "茅台", date: "2024-01-01", type: "up", content: "新高" }),
  "【600519 茅台】2024-01-01 利好：新高", "formatNote 格式化单条");
var fnotes = ctx.formatNotes([
  { code: "600519", name: "茅台", date: "2024-01-01", type: "up", content: "a" },
  { code: "300750", name: "宁德", date: "2024-02-01", type: "down", content: "b" }
]);
eq(fnotes, "【600519 茅台】2024-01-01 利好：a\n【300750 宁德】2024-02-01 利空：b", "formatNotes 多行连接");
// visibleList 复用筛选逻辑（render 重构后行为一致）
ctx.state.records = sample.slice();
ctx.state.filter = "利空"; ctx.state.typeFilter = "";
eq(ctx.visibleList().length, 1, "visibleList 关键字筛选");
ctx.state.filter = ""; ctx.state.typeFilter = "up";
eq(ctx.visibleList().length, 1, "visibleList 类型筛选");
ctx.state.filter = ""; ctx.state.typeFilter = "";
eq(ctx.visibleList().length, sample.length, "visibleList 全量");
// 复制为文本：模拟 navigator.clipboard
lastClipboard = null;
ctx.navigator = { clipboard: { writeText: function (t) { lastClipboard = t; return { then: function (res) { res(); return this; }, catch: function () { return this; } }; } } };
ctx.state.records = sample.slice(); ctx.state.filter = ""; ctx.state.typeFilter = ""; ctx.state.group = false;
doc.getElementById("btnCopyText")._listeners.click[0]();
ok(lastClipboard && lastClipboard.includes("【600519 茅台】"), "复制为文本写入剪贴板");
ok(doc.getElementById("toast").classList.contains("show"), "复制成功后弹出 toast");

// ---------- 结果 ----------
console.log(`\n通过 ${pass} 项，失败 ${fail} 项`);
if (fail) {
  console.log("失败明细：");
  fails.forEach((f) => console.log("  - " + f));
  process.exit(1);
} else {
  console.log("全部逻辑自测通过 ✅");
}
