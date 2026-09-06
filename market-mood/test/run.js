// 自动生成 (tools/gen_microapps.py) — 市场情绪台
const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, ({ sandbox, ok, eq, arrEq, src, err }) => {
  ok("脚本无语法错误", !err || !(err instanceof SyntaxError), err ? err.message : "");
  ok("fetch 调用存在", src.indexOf("fetch(") >= 0);
  ok("端点已配置 (/api/shepherd)", src.indexOf("/api/shepherd") >= 0);
  ok("渲染函数存在", src.indexOf("function render") >= 0);
  
});
