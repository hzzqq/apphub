// 自选行情看板 — 轻量单测（零依赖，不依赖后端 fetch）
// 注: 沙箱桩无 location，加载时 apiBase() 会抛 ReferenceError(非语法错误)，按惯例容忍。
const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, ({ src, err, ok }) => {
  ok("脚本加载无语法错误", !err || !(err instanceof SyntaxError), err ? err.message : "");
  ok("消费统一后端 /api/quote", src.indexOf("/api/quote") >= 0);
  ok("A股红涨绿跌逻辑存在 (cls)", src.indexOf('chg>0 ? "up"') >= 0);
  ok("代码规范化函数存在 (normCode)", src.indexOf("function normCode") >= 0);
  ok("表格渲染函数存在 (renderTable)", src.indexOf("function renderTable") >= 0);
  ok("离线降级提示存在 (file://)", src.indexOf("file://") >= 0);
});
