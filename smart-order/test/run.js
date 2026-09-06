const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
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

// ---------- ② 关键元素可用性（smart-order 主逻辑包在 IIFE 内，函数不暴露为 vm 全局） ----------
// 注：该 App 的 build/check/render 等定义在顶层 IIFE 中，无法从 vm 外部直接断言；
// 此处以 widget 注入后 ttlSel/refreshChk 可用 + 全脚本无抛错作为回归护栏（IIFE 内逻辑由浏览器运行时门禁覆盖）。
console.log("\n[smart-order 回归护栏]");
ok("缓存 widget 注入后 ttlSel 元素可用", (() => { const el = doc.getElementById("ttlSel"); return el && typeof el.value === "string"; })());
ok("缓存 widget 注入后 refreshChk 元素可用", (() => { const el = doc.getElementById("refreshChk"); return el && typeof el.checked === "boolean"; })());
});
