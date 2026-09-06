const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[recipe-box 函数契约]");
ok("esc 函数存在", typeof sandbox.esc==="function");
ok("renderFilters 函数存在", typeof sandbox.renderFilters==="function");
ok("openModal 函数存在", typeof sandbox.openModal==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
});
