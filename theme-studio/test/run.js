/*
 * Theme Studio 逻辑自测脚手架（零依赖，仅用 Node 内置 vm/fs）。
 * 加载 index.html 内联脚本，注入最小 DOM 桩，把内部纯函数暴露为 vm 全局后断言。
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

// ---------- 最小 DOM 桩（宽容：任意 id 返回 makeEl） ----------
function makeEl(id) {
  const el = {
    id: id || "",
    _html: "", _value: "", _text: "", _attrs: {}, _listeners: {},
    dataset: {}, style: {},
    classList: {
      _s: new Set(),
      add(c) { this._s.add(c); },
      remove(c) { this._s.delete(c); },
      toggle(c, on) { if (on === undefined) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); } else { on ? this._s.add(c) : this._s.delete(c); } },
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
    querySelector() { return makeEl(); },
    querySelectorAll() { return []; },
    appendChild() {},
    click() { (this._listeners.click || []).forEach((fn) => fn({ target: this })); }
  };
  return el;
}
const _byId = {};
const doc = {
  _byId,
  readyState: "complete",
  getElementById(id) { return _byId[id] || (_byId[id] = makeEl(id)); },
  querySelector() { return makeEl(); },
  querySelectorAll() { return []; },
  addEventListener() {},
  createElement() { return makeEl(); },
  body: makeEl("body")
};
const localStorage = { _d: {}, getItem(k) { return k in this._d ? this._d[k] : null; }, setItem(k, v) { this._d[k] = String(v); }, removeItem(k) { delete this._d[k]; } };
const ctx = {
  document: doc,
  localStorage,
  navigator: {},
  window: {},
  console,
  Object, Array, Math, JSON, String, Number, Date, Boolean, RegExp, isNaN, isFinite, parseFloat, parseInt, Infinity, NaN,
  Promise
};
vm.createContext(ctx);
try {
  vm.runInContext(src, ctx);
} catch (e) {
  console.error("脚本加载即抛错（不可接受）：", e);
  process.exit(1);
}

// ---------- 断言工具 ----------
let pass = 0, fail = 0;
const fails = [];
function ok(cond, msg) { if (cond) pass++; else { fail++; fails.push(msg); } }
function eq(a, b, msg) { ok(a === b, msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`); }

// ============================================================
// 1. esc 转义
// ============================================================
eq(ctx.esc("<b>&'\""), "&lt;b&gt;&amp;&#39;&quot;", "esc 转义 < > & ' \"");
eq(ctx.esc(null), "", "esc(null) => ''");
eq(ctx.esc(123), "123", "esc(数字) => 字符串");
eq(ctx.esc("<script>alert(1)</script>"), "&lt;script&gt;alert(1)&lt;/script&gt;", "esc 阻断 script 注入");

// ============================================================
// 2. sanitizeUserText 白名单 + 转义（属性一律去除）
// ============================================================
eq(ctx.sanitizeUserText("<b>hi</b>"), "<b>hi</b>", "sanitize 保留 <b>");
eq(ctx.sanitizeUserText("<i>x</i>"), "<i>x</i>", "sanitize 保留 <i>");
eq(ctx.sanitizeUserText("<strong>a</strong>"), "<strong>a</strong>", "sanitize 保留 <strong>");
eq(ctx.sanitizeUserText("<script>alert(1)</script>"), "&lt;script&gt;alert(1)&lt;/script&gt;", "sanitize 拦截 script");
eq(ctx.sanitizeUserText("<img src=x onerror=alert(1)>"), "&lt;img src=x onerror=alert(1)&gt;", "sanitize 拦截 img");
eq(ctx.sanitizeUserText('<b onclick="x">hi</b>'), "&lt;b onclick=&quot;x&quot;&gt;hi&lt;/b&gt;", "sanitize 去除属性（变纯文本）");
eq(ctx.sanitizeUserText("<unknown>tag</unknown>"), "&lt;unknown&gt;tag&lt;/unknown&gt;", "sanitize 非白名单标签被转义");

// ============================================================
// 3. hex 校验 / 归一化 / rgb 互转
// ============================================================
ok(ctx.isValidHex("#abc") === true, "isValidHex(#abc)=true");
ok(ctx.isValidHex("#abcdef") === true, "isValidHex(#abcdef)=true");
ok(ctx.isValidHex("abc") === false, "isValidHex(abc)=false(无#)");
ok(ctx.isValidHex("#xyz") === false, "isValidHex(#xyz)=false");
ok(ctx.isValidHex("#12345") === false, "isValidHex(#12345)=false(长度错)");
eq(ctx.normalizeHex("#ABC"), "#aabbcc", "normalizeHex(#ABC 3位)=#aabbcc");
eq(ctx.normalizeHex("#abcdef"), "#abcdef", "normalizeHex 6位保持");
eq(ctx.normalizeHex("bad"), null, "normalizeHex(bad)=null");
eq(JSON.stringify(ctx.hexToRgb("#667eea")), JSON.stringify({ r: 102, g: 126, b: 234 }), "hexToRgb(#667eea)");
eq(ctx.rgbToHex(102, 126, 234), "#667eea", "rgbToHex 往返");

// ============================================================
// 4. shade 明暗（带钳制）
// ============================================================
eq(ctx.shade("#ffffff", -100), "#000000", "shade(#fff,-100)=#000");
eq(ctx.shade("#000000", 100), "#ffffff", "shade(#000,+100)=#fff");
eq(ctx.shade("#808080", 0), "#808080", "shade 0 不变");
eq(ctx.shade("#ffffff", 50), "#ffffff", "shade 上溢钳制到 #fff");
eq(ctx.shade("#000000", -50), "#000000", "shade 下溢钳制到 #000");
eq(ctx.shade("bad", 10), "#000000", "shade 非法输入回退 #000");

// ============================================================
// 5. 相对亮度 / 对比文字色
// ============================================================
eq(ctx.relativeLuminance("#000000"), 0, "relativeLuminance(#000)=0");
ok(ctx.relativeLuminance("#ffffff") > 0.9, "relativeLuminance(#fff)≈1");
eq(ctx.contrastText("#0f0f23"), "#f5f5fa", "contrastText 深色背景→浅色字");
eq(ctx.contrastText("#ffffff"), "#111111", "contrastText 浅色背景→深色字");

// ============================================================
// 6. 智能生成 generateTheme（确定性 + 协调）
// ============================================================
const g1 = ctx.generateTheme("#667eea", "dark");
const g2 = ctx.generateTheme("#667eea", "dark");
eq(JSON.stringify(g1), JSON.stringify(g2), "generateTheme 同输入完全可复现");
const g3 = ctx.generateTheme("#ff0000", "dark");
ok(JSON.stringify(g1) !== JSON.stringify(g3), "generateTheme 不同种子→不同结果");
["bg","card","card2","accent","accent2","up","down","txt","sub","line"].forEach((k) =>
  ok(ctx.isValidHex(g1[k]), "generateTheme 输出字段 " + k + " 为合法 hex"));
eq(g1.accent, "#667eea", "generateTheme accent=归一化种子");
const gDark = ctx.generateTheme("#3399ff", "dark");
const gLight = ctx.generateTheme("#3399ff", "light");
ok(ctx.relativeLuminance(gDark.bg) < ctx.relativeLuminance(gLight.bg), "深色模式背景比浅色模式更暗");
const gDef = ctx.generateTheme("#667eea", "weird");
eq(gDef.bg, ctx.generateTheme("#667eea", "dark").bg, "generateTheme 非法模式回退 dark");
// 生成结果可通过校验，闭环自洽
let genOk = true; try { ctx.validateTheme(g1); } catch (e) { genOk = false; }
ok(genOk, "generateTheme 产物可被 validateTheme 接受（闭环自洽）");

// ============================================================
// 7. validateTheme 校验 / 补全 / 截断
// ============================================================
const vMin = ctx.validateTheme({ bg: "#0f0f23", accent: "#667eea" });
ok(ctx.isValidHex(vMin.card) && ctx.isValidHex(vMin.card2) && ctx.isValidHex(vMin.txt) && ctx.isValidHex(vMin.sub) && ctx.isValidHex(vMin.line), "validateTheme 缺省字段已用合理默认值补齐");
eq(vMin.up, "#ff4d4f", "validateTheme 默认 up");
let threw = false; try { ctx.validateTheme({ accent: "#667eea" }); } catch (e) { threw = true; }
ok(threw, "validateTheme 缺 bg 抛错");
threw = false; try { ctx.validateTheme({ bg: "red", accent: "#667eea" }); } catch (e) { threw = true; }
ok(threw, "validateTheme 非法 bg 抛错");
const vShort = ctx.validateTheme({ bg: "#abc", accent: "#def" });
eq(vShort.bg, "#aabbcc", "validateTheme 3位hex归一化");
const vName = ctx.validateTheme({ bg: "#0f0f23", accent: "#667eea", name: "x".repeat(100) });
eq(vName.name.length, 40, "validateTheme name 截断到40");
const vKeep = ctx.validateTheme({ bg: "#0f0f23", accent: "#667eea", up: "#123456", down: "#654321" });
eq(vKeep.up, "#123456", "validateTheme 保留提供的 up");
eq(vKeep.down, "#654321", "validateTheme 保留提供的 down");

// ============================================================
// 8. themeToCssVars / exportCss / themeToJson（含 CSS 注入防护）
// ============================================================
const cssVars = ctx.themeToCssVars({ bg: "#0f0f23", accent: "#667eea" });
ok(cssVars.indexOf(":root{") === 0, "themeToCssVars 以 :root{ 开头");
ok(cssVars.indexOf("--bg: #0f0f23;") >= 0, "themeToCssVars 含 --bg");
ok(/\}$/.test(cssVars.trim()), "themeToCssVars 以 } 结尾");
ok(ctx.themeToCssVars({ bg: "bad" }).indexOf("--bg: #000000;") >= 0, "themeToCssVars 非法色回退 #000000（防注入）");
const ex = ctx.exportCss({ name: "<b>主题</b>", bg: "#0f0f23", accent: "#667eea" });
ok(ex.indexOf("/*") === 0, "exportCss 含注释头");
ok(ex.indexOf(":root{") >= 0, "exportCss 含 :root");
ok(ex.indexOf("<b>主题</b>") >= 0, "exportCss 白名单 <b> 在注释内保留（符合规范）");
const exMal = ctx.exportCss({ name: "<script>alert(1)</script>", bg: "#0f0f23", accent: "#667eea" });
ok(exMal.indexOf("<script") < 0, "exportCss 恶意 <script> 在注释内被转义（防 XSS）");
ok(exMal.indexOf("&lt;script&gt;") >= 0, "exportCss 恶意标签以转义形式存在（不执行）");
const js = ctx.themeToJson({ bg: "#111", card: "#222", foo: "bar" });
ok(!("foo" in js), "themeToJson 不含无关字段");

// ============================================================
// 9. 内置主题库合法性 + 全局函数存在
// ============================================================
ok(Array.isArray(ctx.THEMES) && ctx.THEMES.length >= 6, "THEMES 存在且不少于6个");
let allValid = true;
ctx.THEMES.forEach((t) => {
  ["bg","card","card2","accent","accent2","up","down"].forEach((k) => { if (!ctx.isValidHex(t[k])) allValid = false; });
});
ok(allValid, "THEMES 全部必备颜色字段均为合法 hex");
["esc","sanitizeUserText","isValidHex","normalizeHex","shade","generateTheme","randomSeed","validateTheme","themeToCssVars","exportCss","themeToJson","applyTheme","renderGrid","switchTab"].forEach((fn) =>
  ok(typeof ctx[fn] === "function", "全局函数 " + fn + " 存在（可被测试/UIR复用）"));

// ============================================================
// 10. 随机惊喜生成（真实用户功能）
// ============================================================
ok(ctx.isValidHex(ctx.randomSeed()), "randomSeed 返回合法 hex");
const rndTheme = ctx.generateTheme(ctx.randomSeed(), "dark");
ok(rndTheme && ctx.isValidHex(rndTheme.accent) && ctx.isValidHex(rndTheme.bg), "randomSeed+generateTheme 产出可用主题");

// ============================================================
// 汇总
// ============================================================
console.log(`\nTheme Studio 自测: ${pass} 通过 / ${fail} 失败`);
if (fail) { console.log("失败项:\n - " + fails.join("\n - ")); process.exit(1); }
else console.log("全部通过 ✅");
