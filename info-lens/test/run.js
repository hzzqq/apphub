/*
 * InfoLens 信息照妖镜 · 逻辑自测（零依赖，Node 内置 vm）
 * 运行：node test/run.js
 * 覆盖：三桶可解释打分 / 双视角规则 / 六道关口漏斗 / 反馈调权 / 简报导出 / 规则编辑 / 皮肤契约
 */
"use strict";
const fs = require("fs");
const path = require("path");
const { loadApp } = require("../../tools/test-scaffold.js");

const htmlPath = path.resolve(__dirname, "..", "index.html");
const html = fs.readFileSync(htmlPath, "utf8");
const loaded = loadApp(__dirname);
const S = loaded.sandbox;

let pass = 0, fail = 0;
function ok(name, cond, extra){
  if(cond){ pass++; console.log("  ✓ " + name); }
  else { fail++; console.log("  ✗ " + name + (extra ? " :: " + extra : "")); }
}

const R = S.RULE_PRESETS;
const mk = (title, body, source) => ({ title:title || "", body:body || "", source:source || "", date:"2026-11-04", src:"sample" });

/* ---------- Round 1：工具 ---------- */
console.log("\n[Round 1] 工具：转义 / 钳位 / 规则解析");
ok("esc 转义 < & \"", S.esc('<b>&"').indexOf("&lt;b&gt;") >= 0 && S.esc('<b>&"').indexOf("&amp;") >= 0 && S.esc('<b>&"').indexOf("&quot;") >= 0);
ok("clamp 上界 100", S.clamp(150, 0, 100) === 100);
ok("clamp 下界 0", S.clamp(-5, 0, 100) === 0);
ok("parseRules 多分隔符 + 去重", JSON.stringify(S.parseRules("开源, 论文、教程\n开源")) === JSON.stringify(["开源","论文","教程"]));
ok("parseRules 空输入返回空数组", S.parseRules("").length === 0 && S.parseRules(null).length === 0);
ok("today 返回 YYYY-MM-DD", /^\d{4}-\d{2}-\d{2}$/.test(S.today()));

/* ---------- Round 2：三桶打分引擎 ---------- */
console.log("\n[Round 2] 三桶可解释打分");
const hypeCard  = mk("史上最强、彻底改变行业，刷屏引爆全网", "只有宣传稿", "");
const factCard  = mk("新论文公布，数据集与基准测试报告", "结论成立但用不上", "");
const sigCard   = mk("开放API，免费额度已上线，附Colab教程与可复现notebook", "可立即上手", "");
const sh = S.scoreCard(hypeCard, R.learner, {});
const sf = S.scoreCard(factCard, R.learner, {});
const ss = S.scoreCard(sigCard,  R.learner, {});
ok("纯炒作：炒作分>0 且事实/信号=0", sh.hype > 0 && sh.fact === 0 && sh.signal === 0, JSON.stringify(sh));
ok("纯事实：事实分>0 且炒作/信号=0", sf.fact > 0 && sf.hype === 0 && sf.signal === 0, JSON.stringify(sf));
ok("信号卡：信号分为主且命中词可解释", ss.signal > 0 && ss.hits.signal.length >= 3, JSON.stringify(ss.hits.signal));
ok("空卡：三分全 0", (function(){ var z = S.scoreCard(mk("","",""), R.learner, {}); return z.hype===0&&z.fact===0&&z.signal===0; })());
ok("分数钳位 0–100", (function(){
  var long = mk(Array(20).fill("颠覆").join("") + Array(20).fill("论文").join(""), "", "");
  var z = S.scoreCard(long, R.learner, {});
  return z.hype <= 100 && z.fact <= 100 && z.signal <= 100;
})());
ok("反馈权重影响分数", (function(){
  var c = mk("教程", "", "");
  return S.scoreCard(c, R.learner, {"教程":6}).signal > S.scoreCard(c, R.learner, {}).signal;
})());

/* ---------- Round 3：主桶 / 理由 / 双视角 ---------- */
console.log("\n[Round 3] 主桶判定 / 理由 / 双视角差异");
ok("bucketOf 炒作主导", S.bucketOf({hype:56,fact:0,signal:0}) === "hype");
ok("bucketOf 事实主导", S.bucketOf({hype:0,fact:68,signal:0}) === "fact");
ok("bucketOf 信号主导（信号≥事实）", S.bucketOf({hype:0,fact:20,signal:60}) === "signal");
ok("bucketOf 信息不足", S.bucketOf({hype:0,fact:0,signal:0}) === "none");
ok("reasonOf 命中给出关键词", S.reasonOf(["教程","Colab"],"signal").indexOf("命中信号词：教程、Colab") >= 0);
ok("reasonOf 未命中说明无支撑", S.reasonOf([],"fact").indexOf("无支撑") >= 0);
ok("angleOf 学习者视角给选题角度", S.angleOf("learner","signal",{}).indexOf("选题") >= 0);
ok("angleOf 量化视角给落地动作", S.angleOf("quant","signal",{}).indexOf("样本外") >= 0);
ok("双视角差异：学习者卡在 learner 下信号更高", (function(){
  var c = mk("开放API，附Colab教程与可复现notebook", "", "");
  return S.scoreCard(c, R.learner, {}).signal > S.scoreCard(c, R.quant, {}).signal;
})());
ok("双视角差异：量化卡在 quant 下信号更高", (function(){
  var c = mk("数据接口已开放调用，附API文档与样本外回测样例", "", "");
  return S.scoreCard(c, R.quant, {}).signal > S.scoreCard(c, R.learner, {}).signal;
})());
ok("actionOf 高信号给行动建议", S.actionOf("signal",{signal:60},40).indexOf("值得现在") >= 0);

/* ---------- Round 4：六道关口漏斗 ---------- */
console.log("\n[Round 4] 六道关口漏斗 / 标记 / 成本示意");
const cards = [
  mk("某模型开放API，免费额度已上线，附Colab教程与可复现notebook", "可立即上手", "演示源"),
  mk("某模型开放API，免费额度已上线，附Colab教程与可复现notebook", "重复条目", "演示源"),
  mk("史上最强刷屏引爆，全网沸腾", "只有情绪", "演示源"),
  mk("新论文公布，数据集与基准测试报告", "用不上", "演示源"),
  mk("短", "无效标题", "演示源"),
  mk("数据接口已开放调用，附API文档与样本外回测样例", "可接回测", "演示源")
];
const f = S.runFunnel(cards, { threshold:40, rules:R.learner, weights:{}, view:"learner" });
ok("漏斗保留原始总数", f.total === cards.length, "total="+f.total);
ok("六道关口齐全", f.stages.length === 6 && f.stages[0].name.indexOf("去重") >= 0 && f.stages[5].name.indexOf("视角加权") >= 0);
ok("① 去重生效（6→5）", f.stages[0].count === 5, "count="+f.stages[0].count);
ok("② 有效性过滤短标题（5→4）", f.stages[1].count === 4, "count="+f.stages[1].count);
ok("③ 炒作初筛标「仅炒作」", f.scored.some(x=>x.flag==="仅炒作"));
ok("④ 事实核验标「未证实」", f.scored.some(x=>x.flag==="未证实"));
ok("⑤ 信号阈值数量 = 高价值池数量", f.stages[4].count === f.high.length && f.high.length > 0, "high="+f.high.length);
ok("⑥ 视角加权后数量不变", f.stages[5].count === f.high.length);
ok("成本示意 = 条数×0.004（非真实计费）", f.cost === +(cards.length*0.004).toFixed(3) && f.llmCalls === 0, "cost="+f.cost);
ok("阈值提高 → 高价值池单调不增", (function(){
  var a = S.runFunnel(cards,{threshold:40,rules:R.learner,view:"learner"}).high.length;
  var b = S.runFunnel(cards,{threshold:70,rules:R.learner,view:"learner"}).high.length;
  var c = S.runFunnel(cards,{threshold:100,rules:R.learner,view:"learner"}).high.length;
  return a >= b && b >= c;
})());
ok("阈值=100 仅留信号满分条目（分数钳位行为）", S.runFunnel(cards,{threshold:100,rules:R.learner,view:"learner"}).high.every(x=>x.scores.signal===100));
ok("阈值=0 → 全部进高价值池", (function(){
  var z = S.runFunnel(cards,{threshold:0,rules:R.learner,view:"learner"});
  return z.high.length === z.scored.length;
})());
ok("空数据不抛错且返回 0", (function(){ var z=S.runFunnel([],{}); return z.total===0 && z.stages.length===6 && z.high.length===0; })());

/* ---------- Round 5：反馈调权 ---------- */
console.log("\n[Round 5] 反馈调权（有用 / 别推 / 多看这类）");
ok("newFeedback 结构完整", (function(){ var b=S.newFeedback(); return b.weights&&b.up&&b.down; })());
const item = { card:{title:"教程"}, scores:{ hype:0, fact:20, signal:40, hits:{ hype:[], fact:["论文"], signal:["教程"] } } };
let fb = S.newFeedback();
S.applyFeedback(fb, item, "up");
ok("👍 有用：记录点赞 + 信号词权重 +3", fb.up["教程"] === 1 && fb.weights["教程"] === 3);
S.applyFeedback(fb, item, "down");
ok("👎 别推：记录点踩 + 权重回落 0", fb.down["教程"] === 1 && fb.weights["教程"] === 0);
S.applyFeedback(fb, item, "more");
ok("＋ 多看这类：事实词与信号词各 +6", fb.weights["教程"] === 6 && fb.weights["论文"] === 6, JSON.stringify(fb.weights));
ok("调权后重算分数确实变化", (function(){
  var c = mk("教程与论文", "", "");
  var before = S.runFunnel([c],{threshold:0,rules:R.learner,weights:{},view:"learner"}).scored[0].scores.signal;
  var after  = S.runFunnel([c],{threshold:0,rules:R.learner,weights:{"教程":6},view:"learner"}).scored[0].scores.signal;
  return after > before;
})());

/* ---------- Round 6：简报导出 ---------- */
console.log("\n[Round 6] 简报 MD / CSV / 转义 / 空数据");
const md = S.buildBrief(f.scored, "md", { threshold:40, view:"learner" });
ok("MD 含标题与日期", md.indexOf("# 信息照妖镜") >= 0 && md.indexOf("2026-") >= 0);
ok("MD 含视角 / 阈值 / 扫描统计", md.indexOf("视角：") >= 0 && md.indexOf("信号阈值") >= 0 && md.indexOf("扫描") >= 0);
ok("MD 含选题角度与行动建议", md.indexOf("选题") >= 0 && md.indexOf("为什么") >= 0);
const csv = S.buildBrief(f.scored, "csv", { threshold:40, view:"learner" });
const csvHead = csv.split("\n")[0].split(",");
ok("CSV 表头 11 列且全字段加引号", csvHead.length === 11 && csvHead[0] === '"标题"' && csvHead[6] === '"信号分"', csvHead.join("|"));
ok("CSV 行数 = 1 表头 + 高价值条数", csv.split("\n").length === 1 + f.high.length, "lines="+csv.split("\n").length);
ok("CSV 双引号转义", (function(){
  var x = { card:mk('含"引号",逗号',"",""), scores:S.scoreCard(mk('含"引号",逗号',"",""),R.learner,{}),
            bucket:"none", high:true, flag:null, angle:"角度", };
  return S.buildBrief([x],"csv",{view:"learner"}).indexOf('""引号""') >= 0;
})());
ok("空数据 MD 不抛错且含标题", S.buildBrief([],"md",{}).indexOf("# 信息照妖镜") >= 0);
ok("空数据 CSV 只有表头一行", S.buildBrief([],"csv",{}).split("\n").length === 1);
ok("简报只收高价值条目", (function(){
  var onlyHigh = { card:mk("高价值条目","",""), scores:{hype:0,fact:0,signal:80,hits:{hype:[],fact:[],signal:[]}}, bucket:"signal", high:true, flag:null, angle:"角度" };
  var low      = { card:mk("低价值条目","",""), scores:{hype:0,fact:0,signal:0,hits:{hype:[],fact:[],signal:[]}}, bucket:"none", high:false, flag:null, angle:"角度" };
  var out = S.buildBrief([onlyHigh,low],"md",{view:"learner"});
  return out.indexOf("高价值条目") >= 0 && out.indexOf("低价值条目") < 0;
})());

/* ---------- Round 7：规则可编辑 / 冒烟 / 皮肤契约 ---------- */
console.log("\n[Round 7] 规则编辑 / 脚本冒烟 / 皮肤契约");
ok("自定义规则生效（改词即改分）", (function(){
  var custom = { hype:["独家"], fact:[], signal:[] };
  var c = mk("独家消息", "", "");
  return S.scoreCard(c, custom, {}).hype > 0 && S.scoreCard(c, R.learner, {}).hype === 0;
})());
ok("boot() 在 mock DOM 下不抛错", loaded.err === null, loaded.err ? loaded.err.message : "");
ok("渲染入口与状态可用", typeof S.renderAll === "function" && !!S.STATE && !!S.STATE.funnel);
ok("内置示例 10 条且均标 离线示例", S.SAMPLE_CARDS.length === 10 && (function(){
  var t = S.allCards(); return t.length >= 10 && t[0].src === "sample";
})());
ok("三态来源元数据齐全", !!S.SRC_META.sample && !!S.SRC_META.local && !!S.SRC_META.manual && !!S.SRC_META.live);
ok("皮肤契约：10 变量齐备", (function(){
  var need = ["--bg","--card","--card2","--accent","--accent2","--up","--down","--txt","--sub","--line"];
  return need.every(v => html.indexOf(v+":") >= 0);
})());
ok("皮肤契约：主题桥接 JS 在位", html.indexOf("NEON-THEME-BRIDGE BEGIN") >= 0);
ok("零依赖：无外部 script src / iframe", !/<script[^>]*\bsrc\s*=/i.test(html) && !/<iframe/i.test(html));
ok("诚实声明：标明非实时/不调 LLM/分数非结论", html.indexOf("不做实时抓取") >= 0 && html.indexOf("不调用 LLM") >= 0 && html.indexOf("不是结论") >= 0);
ok("端点一致性：仅用已存在的 /api/data", (function(){
  var eps = html.match(/\/api\/[A-Za-z_][A-Za-z0-9_]*/g) || [];
  return eps.every(e => e === "/api/data");
})());

console.log(`\n汇总：通过 ${pass} / 失败 ${fail}`);
process.exit(fail ? 1 : 0);
