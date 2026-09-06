const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[itinerary 纯函数]");
ok("curPlan 函数存在", typeof sandbox.curPlan==="function");
ok("enc/dec 函数存在", typeof sandbox.enc==="function" && typeof sandbox.dec==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
});
