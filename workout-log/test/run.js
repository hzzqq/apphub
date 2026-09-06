const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[workout-log 纯函数]");
ok("vol 函数存在", typeof sandbox.vol==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
eq(sandbox.safeUrl("javascript:alert(1)"), "#", "safeUrl 拦截 javascript:");
eq(sandbox.vol({kg:50,reps:10,sets:3}), 1500, "vol 完整");
eq(sandbox.vol({}), 0, "vol 空");
eq(sandbox.vol({kg:50,reps:10}), 0, "vol 缺 sets");
});
