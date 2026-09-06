const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[cache-insight 契约(脚本包裹于 IIFE)]");
ok("脚本无语法错误", !err || !(err instanceof SyntaxError), err?err.message:"");
ok("消费 /api/cache/stats", src.indexOf("cache/stats")>=0);
ok("含 clearCache 调用", src.indexOf("clearCache")>=0);
ok("含 escapeHtml", src.indexOf("escapeHtml")>=0);
ok("含 freshness", src.indexOf("freshness")>=0);
});
