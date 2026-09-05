/*
 * FuturesChain 逻辑自测脚手架（零依赖，仅用 Node 内置 vm/fs）。
 * 验证：① 缓存控制条契约 ② esc / _isoDate 行为。
 * 运行：node test/run.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const html = fs.readFileSync(path.resolve(__dirname, "..", "index.html"), "utf8");
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) throw new Error("index.html 中未找到 <script>");
const src = m[1];

function makeEl(id) {
  return {
    id: id || "", _value: "", _text: "", _html: "", checked: false, style: {},
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    set innerHTML(v){ this._html = String(v); }, get innerHTML(){ return this._html; },
    set value(v){ this._value = String(v); }, get value(){ return this._value; },
    set textContent(v){ this._text = String(v); }, get textContent(){ return this._text; },
    setAttribute(){}, getAttribute(){ return null; },
    addEventListener(){}, querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
    appendChild(){}, click(){}, focus(){}, dispatchEvent(){}, onchange: null, onclick: null
  };
}
const doc = {
  _byId: {},
  getElementById(id){ return this._byId[id] || (this._byId[id] = makeEl(id)); },
  querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
  createElement(){ return makeEl(); }, addEventListener(){}, body: makeEl("body")
};
const _ls = {};
const localStorage = {
  getItem(k){ return k in _ls ? _ls[k] : null; },
  setItem(k, v){ _ls[k] = String(v); }, removeItem(k){ delete _ls[k]; }
};
class AbortController { constructor(){ this.signal = {}; } abort(){} }
const sandbox = {
  document: doc,
  window: { addEventListener(){}, removeEventListener(){}, scrollTo(){}, __data: null },
  localStorage, console,
  fetch: () => Promise.reject(new Error("no net in test")),
  setTimeout: () => 0, clearTimeout: () => {},
  AbortController, URL, Blob, process, encodeURIComponent, decodeURIComponent
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
process.on("unhandledRejection", () => {});
try { vm.runInContext(src, sandbox, { filename: "index.html#script" }); }
catch (e) { console.warn("（脚本运行期提示，已忽略）:", e.message); }
// 同时执行缓存控制条 widget（内联在 index.html 的 CACHE-WIDGET 标记内），以验证 window.withCache 契约
const _wm = html.match(/CACHE-WIDGET-START -->\s*<script[^>]*>([\s\S]*?)<\/script>/);
if (_wm) { try { vm.runInContext(_wm[1], sandbox, { filename: "cache-widget#script" }); } catch (e) { console.warn("（widget 运行期提示，已忽略）:", e.message); } }

let pass = 0, fail = 0, failed = [];
function ok(name, cond, extra){ if (cond){ pass++; console.log("  ✓ " + name); } else { fail++; failed.push(name); console.log("  ✗ " + name + (extra ? " :: " + extra : "")); } }
const eq = (a, b, msg) => ok(msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`, a === b);

// ---------- ① 缓存控制条契约 ----------
console.log("\n[缓存控制条契约]");
const withCache = sandbox.window.withCache;
ok("window.withCache 已注入", typeof withCache === "function");
if (typeof withCache === "function") {
  doc.getElementById("ttlSel").value = ""; doc.getElementById("refreshChk").checked = false;
  eq(withCache("http://x/api/foo"), "http://x/api/foo", "默认无参数返回原 URL");
  doc.getElementById("ttlSel").value = "60";
  eq(withCache("http://x/api/foo"), "http://x/api/foo?ttl=60", "ttl=60 追加 ?ttl=60");
  doc.getElementById("ttlSel").value = "300"; doc.getElementById("refreshChk").checked = true;
  eq(withCache("http://x/api/foo"), "http://x/api/foo?refresh=1", "绕过缓存优先于 ttl");
  doc.getElementById("refreshChk").checked = false; doc.getElementById("ttlSel").value = "15";
  eq(withCache("http://x/api/foo?a=1"), "http://x/api/foo?a=1&ttl=15", "已有 ? 时以 & 连接");
}

// ---------- ② 纯函数 ----------
console.log("\n[futures-chain 纯函数]");
ok("esc 中和标签", sandbox.esc("<b>") === "&lt;b&gt;");
ok("esc null=>空串", sandbox.esc(null) === "");
ok("_isoDate 格式化", sandbox._isoDate(new Date(2026, 0, 5)) === "2026-01-05");

console.log(`\n汇总：${pass} 通过 / ${fail} 失败`);
if (fail) { console.log("失败项：" + failed.join("; ")); process.exit(1); }
else { console.log("全部通过 ✅"); process.exit(0); }
