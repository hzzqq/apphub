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

// ---------- ② 纯函数 ----------
console.log("\n[sector-rotation 纯函数]");
ok("statusOf 领涨", (() => { const r = sandbox.statusOf({ strength5: 0.6 }); return r.cls === "lead" && r.txt === "领涨"; })());
ok("statusOf 掉队", (() => { const r = sandbox.statusOf({ strength5: -0.3 }); return r.cls === "lag" && r.txt === "掉队"; })());
ok("statusOf 中性", (() => { const r = sandbox.statusOf({ strength5: 0.1 }); return r.cls === "mid" && r.txt === "中性"; })());
});
