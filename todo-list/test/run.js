const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[todo-list 纯函数]");
ok("dueInfo 函数存在", typeof sandbox.dueInfo==="function");
ok("todayStr 函数存在", typeof sandbox.todayStr==="function");
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc 转义 <b>");
eq(sandbox.safeUrl("javascript:alert(1)"), "#", "safeUrl 拦截 javascript:");
ok("dueInfo 空串 => null", sandbox.dueInfo("")===null);
ok("dueInfo null => null", sandbox.dueInfo(null)===null);
ok("dueInfo 未来 => 对象", (function(){var r=sandbox.dueInfo("2099-12-31"); return r && typeof r==="object" && r.over===false;})());
});
