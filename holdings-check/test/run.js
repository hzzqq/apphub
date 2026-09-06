const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[holdings-check 函数契约]");
ok("render 函数存在", typeof sandbox.render==="function");
ok("exportCsv 函数存在", typeof sandbox.exportCsv==="function");
ok("add 函数存在", typeof sandbox.add==="function");
ok("diagnosis 函数存在", typeof sandbox.diagnosis==="function");
});
