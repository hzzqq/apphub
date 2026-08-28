/*
 * bookmark-manager XSS 防护回归测试（零依赖，仅 Node 内置 vm/fs）。
 * 直接从 index.html 内联脚本中「按花括号配平」抽取 esc() / safeUrl() 真实实现,
 * 断言其正确转义 HTML 注入字符, 并锁定渲染层确实调用了 esc/safeUrl（防回归）。
 * 运行：node test/run.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const html = fs.readFileSync(path.resolve(__dirname, "..", "index.html"), "utf8");

function extractFn(src, name) {
  const sig = "function " + name + "(";
  const start = src.indexOf(sig);
  if (start < 0) return null;
  const brace = src.indexOf("{", start);
  let depth = 0;
  for (let j = brace; j < src.length; j++) {
    if (src[j] === "{") depth++;
    else if (src[j] === "}") {
      depth--;
      if (depth === 0) return src.slice(start, j + 1);
    }
  }
  return null;
}

const ctx = { String, RegExp, console };
vm.createContext(ctx);
const escSrc = extractFn(html, "esc");
const safeSrc = extractFn(html, "safeUrl");
if (!escSrc) throw new Error("index.html 中未找到 esc() 实现");
if (!safeSrc) throw new Error("index.html 中未找到 safeUrl() 实现");
vm.runInContext(escSrc + "\nthis.__esc=esc;", ctx);
vm.runInContext(safeSrc + "\nthis.__safeUrl=safeUrl;", ctx);
const esc = ctx.__esc;
const safeUrl = ctx.__safeUrl;

let pass = 0, fail = 0;
function ok(name, cond) {
  if (cond) { pass++; console.log("  ✓ " + name); }
  else { fail++; console.log("  ✗ " + name); }
}

/* ---------- esc 行为 ---------- */
ok("空值 -> 空串", esc(null) === "" && esc(undefined) === "");
ok("基本字符串不变", esc("hello") === "hello");
ok("转义 < >", esc("<img>") === "&lt;img&gt;");
const xss = '<img src=x onerror=alert(1)>';
ok("中和 onerror 注入", esc(xss) === "&lt;img src=x onerror=alert(1)&gt;");
ok("转义双引号", esc('a"b') === "a&quot;b");
ok("转义单引号", esc("a'b") === "a&#39;b");
ok("转义 &", esc("a&b") === "a&amp;b");
ok("全字符组合", esc(`a&b<c>d"e'f`) === "a&amp;b&lt;c&gt;d&quot;e&#39;f");

/* ---------- safeUrl 行为 ---------- */
ok("javascript: 协议被中和", safeUrl("javascript:alert(1)") === "#");
ok("带空白的 javascript: 也被中和", safeUrl("  JAVASCRIPT:alert(1)") === "#");
ok("普通 http 链接保留", safeUrl("https://example.com?x=1") === "https://example.com?x=1");
ok("safeUrl 也转义注入字符", safeUrl("http://x/?a=<b>") === "http://x/?a=&lt;b&gt;");
ok("safeUrl 空值 -> 空串(空 href 无害)", safeUrl("") === "");

/* ---------- 集成锁：渲染层确实调用了防护 ---------- */
ok("渲染 title 使用 esc(m.title)", /esc\(\s*m\.title\s*\)/.test(html));
ok("渲染 url 文本使用 esc(m.url)", /esc\(\s*m\.url\s*\)/.test(html));
ok("链接 href 使用 safeUrl(m.url)", /safeUrl\(\s*m\.url\s*\)/.test(html));
ok("渲染 tag 使用 esc(m.tag)", /esc\(\s*m\.tag\s*\)/.test(html));

console.log("\n汇总：通过 " + pass + " / 失败 " + fail);
process.exit(fail ? 1 : 0);
