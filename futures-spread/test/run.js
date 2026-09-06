const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[futures-spread 契约(脚本包裹于 IIFE)]");
ok("脚本无语法错误", !err || !(err instanceof SyntaxError), err?err.message:"");
ok("含 linearRegression", src.indexOf("linearRegression")>=0);
ok("含 pearson", src.indexOf("pearson")>=0);
ok("含 renderTable", src.indexOf("renderTable")>=0);
ok("含 generateMonths", src.indexOf("generateMonths")>=0);
});
