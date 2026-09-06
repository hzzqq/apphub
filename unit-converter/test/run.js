const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[unit-converter 纯函数]");
ok("cat 函数存在", typeof sandbox.cat==="function");
ok("toBase 函数存在", typeof sandbox.toBase==="function");
ok("fromBase 函数存在", typeof sandbox.fromBase==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
eq(sandbox.cat().label, "长度", "cat 默认=长度");
var c=sandbox.cat();
eq(sandbox.toBase(c,"米",5), 5, "toBase 米");
eq(sandbox.toBase(c,"千米",1), 1000, "toBase 千米");
eq(sandbox.toBase(c,"厘米",100), 1, "toBase 厘米");
eq(sandbox.fromBase(c,"千米",1000), 1, "fromBase 千米");
eq(sandbox.fromBase(c,"厘米",1), 100, "fromBase 厘米");
});
