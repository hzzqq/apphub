const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[desktop-pet 函数契约]");
ok("moodText 函数存在", typeof sandbox.moodText==="function");
ok("render 函数存在", typeof sandbox.render==="function");
ok("save 函数存在", typeof sandbox.save==="function");
ok("load 函数存在", typeof sandbox.load==="function");
});
