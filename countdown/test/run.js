const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[countdown 纯函数]");
ok("daysBetween 函数存在", typeof sandbox.daysBetween==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
eq(sandbox.safeUrl("javascript:alert(1)"), "#", "safeUrl 拦截 javascript:");
eq(sandbox.descOf(5).lab, "天后", "descOf(5)");
eq(sandbox.descOf(0).lab, "就是今天", "descOf(0)");
eq(sandbox.descOf(-3).lab, "天前", "descOf(-3)");
});
