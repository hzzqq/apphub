// 自动生成 (tools/gen_microapps.py) — 期货品种筛选
const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, ({ sandbox, ok, eq, arrEq, src, err }) => {
  ok("脚本无语法错误", !err || !(err instanceof SyntaxError), err ? err.message : "");
  ok("fetch 调用存在", src.indexOf("fetch(") >= 0);
  ok("端点已配置 (/api/futures_varieties)", src.indexOf("/api/futures_varieties") >= 0);
  ok("渲染函数存在", src.indexOf("function render") >= 0);
  
});
