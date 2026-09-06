// 自动生成 (tools/gen_microapps.py) — 交易大师·虚拟对话
const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, ({ sandbox, ok, eq, arrEq, src, err }) => {
  ok("脚本无语法错误", !err || !(err instanceof SyntaxError), err ? err.message : "");
  ok("fetch 调用存在", src.indexOf("fetch(") >= 0);
  ok("端点已配置 (/api/llm)", src.indexOf("/api/llm") >= 0);
  ok("渲染函数存在", src.indexOf("function render") >= 0);
  ok("定制渲染钩子存在", src.indexOf("function renderCustom") >= 0);
  ok("模板占位符已替换", src.indexOf("__CUSTOM") < 0);
  ok("POST 助手 fetchT/showError 存在", src.indexOf("fetchT(")>=0 && src.indexOf("function showError")>=0);ok("人格列表 TRAIT_PERSONAS 存在", src.indexOf("TRAIT_PERSONAS")>=0);ok("多轮 QA_HISTORY 存在", src.indexOf("QA_HISTORY")>=0);
});
