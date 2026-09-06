// 自动生成 (tools/gen_microapps.py) — 板块强弱热力
const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, ({ sandbox, ok, eq, arrEq, src, err }) => {
  ok("脚本无语法错误", !err || !(err instanceof SyntaxError), err ? err.message : "");
  ok("fetch 调用存在", src.indexOf("fetch(") >= 0);
  ok("端点已配置 (/api/sector)", src.indexOf("/api/sector") >= 0);
  ok("渲染函数存在", src.indexOf("function render") >= 0);
  ok("定制渲染钩子存在", src.indexOf("function renderCustom") >= 0);
  ok("模板占位符已替换", src.indexOf("__CUSTOM") < 0);
  
});
