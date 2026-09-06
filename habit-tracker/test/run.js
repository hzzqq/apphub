const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[habit-tracker 纯函数]");
ok("calcStreak 函数存在", typeof sandbox.calcStreak==="function");
ok("today 函数存在", typeof sandbox.today==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
eq(sandbox.safeUrl("javascript:alert(1)"), "#", "safeUrl 拦截 javascript:");
eq(sandbox.calcStreak({}), 0, "calcStreak 空");
var hk={}; hk[sandbox.today()]=1; eq(sandbox.calcStreak(hk), 1, "calcStreak 含今天");
eq(sandbox.calcStreak({"2000-01-01":1}), 0, "calcStreak 旧日期");
});
