const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[kpattern 纯函数]");
ok("svgFor 函数存在", typeof sandbox.svgFor==="function");
ok("svgFor('tri') 返回 <svg", typeof sandbox.svgFor==="function" && sandbox.svgFor("tri").indexOf("<svg")===0);
ok("svgFor('tri') 用红涨色 ff4d4f", sandbox.svgFor("tri").indexOf("ff4d4f")>=0);
ok("svgFor('death') 用绿跌色 00d486", sandbox.svgFor("death").indexOf("00d486")>=0);
});
