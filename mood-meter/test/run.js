const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[mood-meter 纯函数]");
ok("stageOf 函数存在", typeof sandbox.stageOf==="function");
ok("colorOf 函数存在", typeof sandbox.colorOf==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
eq(sandbox.safeUrl("javascript:alert(1)"), "#", "safeUrl 拦截 javascript:");
eq(sandbox.stageOf(80).txt, "贪婪", "stageOf 80");
eq(sandbox.stageOf(60).txt, "偏多", "stageOf 60");
eq(sandbox.stageOf(40).cls, "neutral", "stageOf 40");
eq(sandbox.stageOf(10).cls, "bear", "stageOf 10");
eq(sandbox.colorOf(50), "#ff4d4f", "colorOf 50");
eq(sandbox.colorOf(49), "#00d486", "colorOf 49");
});
