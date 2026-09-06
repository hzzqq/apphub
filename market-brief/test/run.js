const { runAppTest } = require("../../tools/test-scaffold.js");
runAppTest(__dirname, (api) => {
  const { sandbox, window, doc, ok, eq, arrEq, src, err } = api;
console.log("\n[market-brief 纯函数]");
ok("tagOf 函数存在", typeof sandbox.tagOf==="function");
ok("today 函数存在", typeof sandbox.today==="function");
eq(sandbox.tagOf("利好上涨"), '<span class="tag bull">利好</span>', "tagOf 利好");
eq(sandbox.tagOf("利空下跌"), '<span class="tag bear">利空</span>', "tagOf 利空");
eq(sandbox.tagOf("关注xxx"), '<span class="tag watch">关注</span>', "tagOf 关注");
eq(sandbox.tagOf("普通文本"), "", "tagOf 普通");
});
