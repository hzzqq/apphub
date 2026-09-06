const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[focus-timer 纯函数]");
ok("fmt 函数存在", typeof sandbox.fmt==="function");
ok("checkToday 函数存在", typeof sandbox.checkToday==="function");
eq(sandbox.fmt(65), "01:05", "fmt 65s");
eq(sandbox.fmt(0), "00:00", "fmt 0s");
eq(sandbox.fmt(125), "02:05", "fmt 125s");
});
