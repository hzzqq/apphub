const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[cube-trainer 纯函数]");
ok("rot 函数存在", typeof sandbox.rot==="function");
eq(sandbox.fmt(1000), "1.00", "fmt(1000)");
eq(sandbox.fmt(1500), "1.50", "fmt(1500)");
arrEq(sandbox.rot("x",1,[1,2,3]), [1,-3,2], "rot x+");
arrEq(sandbox.rot("y",1,[1,2,3]), [3,2,-1], "rot y+");
arrEq(sandbox.rot("z",-1,[1,2,3]), [2,-1,3], "rot z-");
});
