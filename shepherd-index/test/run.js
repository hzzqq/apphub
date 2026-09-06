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

// ---------- ② 纯函数（THRESH 在脚本内定义，函数闭包可访问） ----------
console.log("\n[shepherd-index 纯函数]");
ok("levelOf up_count 高温", sandbox.levelOf("up_count", 4000) === "hot");
ok("levelOf up_count 低温", sandbox.levelOf("up_count", 100) === "cold");
ok("levelOf down_count 高温(dir<0)", sandbox.levelOf("down_count", 100) === "hot");
ok("scoreOne up_count 高温=100", sandbox.scoreOne("up_count", 4000) === 100);
ok("scoreOne up_count 低温=10", sandbox.scoreOne("up_count", 100) === 10);
});
