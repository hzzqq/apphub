// _fe_smoke.js — 通用前端运行时冒烟 harness（App Hub 门禁）
// 入参: node _fe_smoke.js <appdir> [node路径]
// 行为: 鲁棒 DOM/Canvas 桩 → eval 全部 <script> → 触发初始化 → 抓崩溃
// 判定: 异常 → FE_RUNTIME_FAIL + exit(1); 否则 FE_RUNTIME_OK + exit(0)
// 来源: fe-runtime-check skill 规格（避免覆盖 global.URL/Blob；el() 必须含 value/style/getContext 等）
'use strict';
const fs = require('fs');
const path = require('path');

const appDir = process.argv[2];
const appName = appDir ? path.basename(appDir) : 'unknown';

function fail(msg) {
  console.log('FE_RUNTIME_FAIL ' + appName + ': ' + (msg || ''));
  process.exit(1);
}

// 绝不能覆盖 global.URL / Blob（Node brokered fs 依赖真实 URL，覆盖即崩）
if (!global.URL.createObjectURL) global.URL.createObjectURL = () => 'blob:test';
if (!global.URL.revokeObjectURL) global.URL.revokeObjectURL = () => {};

// ---- 最小 DOM 桩 ----
const store = {};
function makeCanvasCtx() {
  return new Proxy({}, {
    get(t, prop) {
      if (prop === 'measureText') return (s) => ({ width: String(s ? s.length : 0) * 6 });
      if (prop === 'createLinearGradient' || prop === 'createRadialGradient' || prop === 'createPattern' || prop === 'createImageData')
        return () => ({ addColorStop() {}, data: [] });
      if (prop === 'getImageData') return () => ({ data: [] });
      if (prop === 'canvas') return { width: 300, height: 150 };
      if (prop === 'getContext') return () => makeCanvasCtx();
      return () => {};
    },
    set() { return true; }
  });
}
function el() {
  const e = {
    _html: '',
    _text: '',
    style: {},
    value: '',
    dataset: {},
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    addEventListener() {}, removeEventListener() {},
    setAttribute() {}, getAttribute() { return null; }, removeAttribute() {},
    appendChild() {}, removeChild() {},
    insertAdjacentHTML(p, h) { this._html += h; },
    click() {}, focus() {}, blur() {},
    getContext() { return makeCanvasCtx(); },
    getBoundingClientRect() { return { top: 0, left: 0, width: 300, height: 150, right: 300, bottom: 150 }; },
    querySelector() { return el(); },
    querySelectorAll() { return []; },
  };
  Object.defineProperty(e, 'innerHTML', {
    get() { return this._html; },
    set(v) { this._html = String(v == null ? '' : v); },
  });
  Object.defineProperty(e, 'textContent', {
    get() { return this._text; },
    set(v) { this._text = String(v == null ? '' : v); },
  });
  return e;
}
const cache = {};
function getById(id) { return cache[id] || (cache[id] = el()); }
function getBySel(sel) { return cache[sel] || (cache[sel] = el()); }

const domListeners = [];
global.window = global;
global.document = {
  getElementById: getById,
  querySelector: getBySel,
  querySelectorAll() { return []; },
  createElement() { return el(); },
  createElementNS() { return el(); },
  body: el(),
  documentElement: el(),
  readyState: 'complete',
  addEventListener(type, cb) {
    if (type === 'DOMContentLoaded' || type === 'load') domListeners.push({ type, cb });
  },
  removeEventListener() {},
};
// 全局 addEventListener（部分 App 用 window.addEventListener('DOMContentLoaded')）
global.addEventListener = function (type, cb) {
  if (type === 'DOMContentLoaded' || type === 'load') domListeners.push({ type, cb });
};
global.removeEventListener = function () {};

// navigator/location 在 Node 22 为只读 getter，存在则沿用，缺失才补（否则赋值抛 TypeError）
if (!global.navigator) { try { Object.defineProperty(globalThis, 'navigator', { value: { userAgent: 'node', platform: 'node' }, configurable: true }); } catch (e) {} }
if (!global.location) { try { Object.defineProperty(globalThis, 'location', { value: { protocol: 'http:', origin: 'http://localhost:8787', href: 'http://localhost:8787/' }, configurable: true }); } catch (e) {} }
global.alert = () => {};
global.confirm = () => false;
global.prompt = () => null;
global.requestAnimationFrame = (cb) => { try { cb(0); } catch (e) {} return 0; };
global.cancelAnimationFrame = () => {};
global.localStorage = {
  getItem(k) { return k in store ? store[k] : null; },
  setItem(k, v) { store[k] = String(v); },
  removeItem(k) { delete store[k]; },
  clear() { for (const k in store) delete store[k]; },
};
// fetch 一律 reject（网络失败由 .catch 接，不应崩）；冒烟只验证加载/初始化不崩
global.fetch = () => Promise.reject(new Error('smoke: offline'));

process.on('unhandledRejection', () => {});
process.on('uncaughtException', (e) => fail('uncaught: ' + (e && e.stack ? e.stack : e)));

// ---- 抽脚本 + sloppy eval ----
let html;
try {
  html = fs.readFileSync(path.join(appDir, 'index.html'), 'utf8');
} catch (e) {
  fail('无法读取 index.html: ' + e.message);
}
const scripts = [];
const re = /<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g;
let mm;
while ((mm = re.exec(html)) !== null) {
  if (mm[1] && mm[1].trim()) scripts.push(mm[1]);
}
if (!scripts.length) {
  console.log('FE_RUNTIME_OK ' + appName + ' (no inline script)');
  process.exit(0);
}
try {
  for (const code of scripts) {
    (0, eval)(code); // sloppy 模式：顶层 function/var 泄漏到全局作用域
  }
} catch (e) {
  fail('eval 抛异常: ' + (e && e.stack ? e.stack : e));
}

// ---- 触发初始化入口 ----
// 1) 派发 DOMContentLoaded / load（addEventListener 收集到的）
for (const L of domListeners) {
  try { L.cb(); } catch (e) { fail('事件 ' + L.type + ' 抛异常: ' + (e && e.stack ? e.stack : e)); }
}
// 2) 常见显式入口（多数为 IIFE 内已触发，这里兜底）
for (const name of ['init', 'render', 'main']) {
  try { if (typeof global[name] === 'function') global[name](); } catch (e) { fail('初始化 ' + name + ' 抛异常: ' + (e && e.stack ? e.stack : e)); }
}
try { if (typeof global.onload === 'function') global.onload(); } catch (e) { fail('onload 抛异常: ' + (e && e.stack ? e.stack : e)); }

console.log('FE_RUNTIME_OK ' + appName);
process.exit(0);
