/*
 * tools/test-scaffold.js — App Hub 前端单测共享脚手架（单一真源）。
 *
 * 所有 test/run.js 通过 require 本文件来跑测试，杜绝 18+ 份重复的内联脚手架。
 * 负责：注入最小 DOM / canvas / localStorage / btoa·atob 桩，在 vm 沙箱加载
 * index.html 首段 <script>（若含缓存控制条 CACHE-WIDGET 标记则一并执行），
 * 暴露 {sandbox, window, doc, ok, eq, arrEq, src, err} 给各 App 的断言函数。
 *
 * 用法（见各 App 的 test/run.js）：
 *   const { runAppTest } = require("../../tools/test-scaffold.js");
 *   runAppTest(__dirname, (api) => { api.ok(...); api.eq(...); ... });
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

function makeEl(id) {
  const ctx = {
    fillRect(){}, clearRect(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){}, fill(){},
    arc(){}, rect(){}, closePath(){}, save(){}, restore(){}, translate(){}, scale(){}, setTransform(){},
    fillText(){}, measureText(){ return { width: 0 }; }, createLinearGradient(){ return { addColorStop(){} }; }
  };
  return {
    id: id || "", _value: "", _text: "", _html: "",
    style: {}, dataset: {},
    classList: { add(){}, remove(){}, toggle(){}, contains(){ return false; } },
    width: 300, height: 150,
    set innerHTML(v){ this._html = String(v); }, get innerHTML(){ return this._html; },
    set value(v){ this._value = String(v); }, get value(){ return this._value; },
    set textContent(v){ this._text = String(v); }, get textContent(){ return this._text; },
    setAttribute(){}, getAttribute(){ return null; }, removeAttribute(){},
    addEventListener(){}, removeEventListener(){}, querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
    appendChild(){}, removeChild(){}, insertBefore(){}, remove(){}, click(){}, focus(){}, dispatchEvent(){},
    getContext(){ return ctx; },
    getBoundingClientRect(){ return { left:0, top:0, width:300, height:150, right:300, bottom:150 }; }
  };
}

function makeDoc() {
  const _byId = {};
  return {
    _byId,
    getElementById(id){ return this._byId[id] || (this._byId[id] = makeEl(id)); },
    querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
    createElement(){ return makeEl(); }, addEventListener(){}, body: makeEl("body")
  };
}

function runAppTest(appDir, assertsFn) {
  const html = fs.readFileSync(path.resolve(appDir, "..", "index.html"), "utf8");
  const m = html.match(/<script>([\s\S]*?)<\/script>/);
  if (!m) throw new Error("index.html 中未找到 <script>");
  const src = m[1];

  const doc = makeDoc();
  const _ls = {};
  const localStorage = {
    getItem(k){ return k in _ls ? _ls[k] : null; },
    setItem(k, v){ _ls[k] = String(v); }, removeItem(k){ delete _ls[k]; }
  };
  class AbortController { constructor(){ this.signal = {}; } abort(){} }
  const win = {
    addEventListener(){}, removeEventListener(){}, scrollTo(){}, alert(){}, confirm(){ return false; },
    requestAnimationFrame(){ return 0; }, cancelAnimationFrame(){}, devicePixelRatio: 1,
    localStorage, document: doc,
    fetch: () => Promise.reject(new Error("no net")),
    btoa: (s) => Buffer.from(s, "binary").toString("base64"),
    atob: (s) => Buffer.from(s, "base64").toString("binary")
  };
  const sandbox = {
    document: doc, window: win, localStorage, console,
    fetch: () => Promise.reject(new Error("no net")),
    setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
    AbortController, URL, Blob, process, Buffer,
    encodeURIComponent, decodeURIComponent, btoa: win.btoa, atob: win.atob,
    TextEncoder, TextDecoder, navigator: { userAgent: "node" },
    Math, Date, JSON, Promise, Array, Object, String, Number, Boolean, RegExp
  };
  sandbox.globalThis = sandbox;
  win.localStorage = localStorage; win.document = doc; win.fetch = sandbox.fetch;
  vm.createContext(sandbox);
  process.on("unhandledRejection", () => {});

  let err = null;
  try { vm.runInContext(src, sandbox, { filename: "index.html#script" }); }
  catch (e) { err = e; }
  // 若 App 内联了缓存控制条（CACHE-WIDGET 标记），一并执行以定义 window.withCache 等
  const wm = html.match(/CACHE-WIDGET-START -->\s*<script[^>]*>([\s\S]*?)<\/script>/);
  if (wm) {
    try { vm.runInContext(wm[1], sandbox, { filename: "cache-widget#script" }); }
    catch (e) { if (!err) err = e; }
  }

  let pass = 0, fail = 0, failed = [];
  function ok(name, cond, extra) {
    if (cond) { pass++; console.log("  ✓ " + name); }
    else { fail++; failed.push(name); console.log("  ✗ " + name + (extra ? (" :: " + extra) : "")); }
  }
  function eq(a, b, msg) { ok(msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`, a === b); }
  function arrEq(a, b, msg) { const s = JSON.stringify; ok(msg + ` (got ${s(a)} want ${s(b)})`, s(a) === s(b)); }

  assertsFn({ sandbox, window: win, doc, ok, eq, arrEq, src, err });

  console.log(`\n汇总：${pass} 通过 / ${fail} 失败`);
  if (fail) { console.log("失败项：" + failed.join("; ")); process.exit(1); }
  else { console.log("全部通过 ✅"); process.exit(0); }
}

module.exports = { runAppTest, makeEl, makeDoc };
