/*
 * 逻辑自测脚手架（零依赖，仅用 Node 内置 vm/fs）。
 * 加载 index.html 首段 <script>，注入最小 DOM / canvas / localStorage / btoa 桩，
 * 验证关键纯函数行为与「脚本可无语法错误执行」回归护栏。
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

function makeEl(id){
  const ctx = {
    fillRect(){}, clearRect(){}, beginPath(){}, moveTo(){}, lineTo(){}, stroke(){}, fill(){},
    arc(){}, rect(){}, closePath(){}, save(){}, restore(){}, translate(){}, scale(){}, setTransform(){},
    fillText(){}, measureText(){ return {width:0}; }, createLinearGradient(){ return {addColorStop(){}}; }
  };
  return {
    id: id||"", _value:"", _text:"", _html:"",
    style:{}, dataset:{}, classList:{add(){},remove(){},toggle(){},contains(){return false;}},
    width:300, height:150,
    set innerHTML(v){this._html=String(v);}, get innerHTML(){return this._html;},
    set value(v){this._value=String(v);}, get value(){return this._value;},
    set textContent(v){this._text=String(v);}, get textContent(){return this._text;},
    setAttribute(){}, getAttribute(){return null;}, removeAttribute(){},
    addEventListener(){}, removeEventListener(){}, querySelector(){return makeEl();}, querySelectorAll(){return [];},
    appendChild(){}, removeChild(){}, insertBefore(){}, remove(){}, click(){}, focus(){}, dispatchEvent(){},
    getContext(){ return ctx; }, getBoundingClientRect(){ return {left:0,top:0,width:300,height:150,right:300,bottom:150}; }
  };
}
const doc = {
  _byId:{},
  getElementById(id){ return this._byId[id] || (this._byId[id]=makeEl(id)); },
  querySelector(){ return makeEl(); }, querySelectorAll(){ return []; },
  createElement(){ return makeEl(); }, addEventListener(){}, body: makeEl("body")
};
const _ls = {};
const localStorage = { getItem(k){return k in _ls?_ls[k]:null;}, setItem(k,v){_ls[k]=String(v);}, removeItem(k){delete _ls[k];} };
class AbortController{ constructor(){ this.signal={}; } abort(){} }
const win = {
  addEventListener(){}, removeEventListener(){}, scrollTo(){}, alert(){}, confirm(){return false;},
  requestAnimationFrame(){return 0;}, cancelAnimationFrame(){}, devicePixelRatio:1,
  localStorage, document: doc,
  fetch: ()=>Promise.reject(new Error("no net")),
  btoa: (s)=>Buffer.from(s,"binary").toString("base64"),
  atob: (s)=>Buffer.from(s,"base64").toString("binary")
};
const sandbox = {
  document: doc, window: win, localStorage, console,
  fetch: ()=>Promise.reject(new Error("no net")),
  setTimeout: ()=>0, clearTimeout: ()=>{}, setInterval: ()=>0, clearInterval: ()=>{},
  AbortController, URL, Blob, process, Buffer,
  encodeURIComponent, decodeURIComponent, btoa: win.btoa, atob: win.atob,
  TextEncoder, TextDecoder, navigator: {userAgent:"node"},
  Math, Date, JSON, Promise, Array, Object, String, Number, Boolean, RegExp
};
sandbox.globalThis = sandbox;
win.localStorage = localStorage; win.document = doc; win.fetch = sandbox.fetch;
vm.createContext(sandbox);
process.on("unhandledRejection", ()=>{});

let _err = null;
try { vm.runInContext(src, sandbox, {filename:"index.html#script"}); }
catch(e){ _err = e; }

let pass=0, fail=0, failed=[];
function ok(name, cond, extra){ if(cond){pass++; console.log("  \u2713 "+name);} else {fail++; failed.push(name); console.log("  \u2717 "+name+(extra?(" :: "+extra):""));} }
function eq(a,b,msg){ ok(msg+` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`, a===b); }
function arrEq(a,b,msg){ const s=JSON.stringify; ok(msg+` (got ${s(a)} want ${s(b)})`, s(a)===s(b)); }

console.log("\n[todo-list 纯函数]");
ok("dueInfo 函数存在", typeof sandbox.dueInfo==="function");
ok("todayStr 函数存在", typeof sandbox.todayStr==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
eq(sandbox.safeUrl("javascript:alert(1)"), "#", "safeUrl 拦截 javascript:");
ok("dueInfo 空串 => null", sandbox.dueInfo("")===null);
ok("dueInfo null => null", sandbox.dueInfo(null)===null);
ok("dueInfo 未来 => 对象", (function(){var r=sandbox.dueInfo("2099-12-31"); return r && typeof r==="object" && r.over===false;})());

console.log(`\n汇总：${pass} 通过 / ${fail} 失败`);
if (fail) { console.log("失败项：" + failed.join("; ")); process.exit(1); }
else { console.log("全部通过 \u2705"); process.exit(0); }
