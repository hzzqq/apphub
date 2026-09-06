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
  doc.getElementById("ttlSel").value = "0";
  eq(withCache("http://x/api/foo"), "http://x/api/foo?ttl=0", "ttl=0(强制刷新) 追加 ?ttl=0");
  doc.getElementById("ttlSel").value = "300"; doc.getElementById("refreshChk").checked = true;
  eq(withCache("http://x/api/foo"), "http://x/api/foo?refresh=1", "绕过缓存优先于 ttl");
  doc.getElementById("refreshChk").checked = false; doc.getElementById("ttlSel").value = "15";
  eq(withCache("http://x/api/foo?a=1"), "http://x/api/foo?a=1&ttl=15", "已有 ? 时以 & 连接");
}

// ---------- ② 纯函数 ----------
console.log("\n[market-cube 纯函数]");
ok("esc 中和标签", sandbox.esc("<b>") === "&lt;b&gt;");
ok("esc null=>空串", sandbox.esc(null) === "");
ok("fmtVal 取小数位", sandbox.fmtVal(3.14159, { dec: 2 }) === "3.14");
ok("cellColor null=>transparent", sandbox.cellColor(null, {}, { maxAbs: 1 }) === "transparent");
ok("cellColor 正值返回红涨 rgba", (() => {
  const c = sandbox.cellColor(1, { signed: true }, { maxAbs: 1 });
  return typeof c === "string" && c.indexOf("255,77,79") >= 0;
})());
});
