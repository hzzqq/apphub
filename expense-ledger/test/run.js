const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[expense-ledger 纯函数]");
ok("fmt 函数存在", typeof sandbox.fmt==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
eq(sandbox.safeUrl("javascript:alert(1)"), "#", "safeUrl 拦截 javascript:");
eq(sandbox.fmt(3.5), "¥3.50", "fmt(3.5)");
eq(sandbox.fmt(0), "¥0.00", "fmt(0)");
eq(sandbox.shiftMonth("2024-01",1), "2024-02", "shiftMonth +1");
eq(sandbox.shiftMonth("2024-12",1), "2025-01", "shiftMonth 跨年");
});
