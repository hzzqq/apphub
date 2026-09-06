const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[health-check 函数契约]");
ok("calc 函数存在", typeof sandbox.calc==="function");
ok("renderForm 函数存在", typeof sandbox.renderForm==="function");
ok("persist 函数存在", typeof sandbox.persist==="function");
});
