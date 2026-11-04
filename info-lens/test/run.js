/*
 * InfoLens 信息照妖镜 v2 · 逻辑自测（零依赖，Node 内置 vm）
 * 运行：node test/run.js
 * 覆盖：三桶可解释打分 / 双视角(A股·期货词表) / 六道关口漏斗 / 反馈调权 /
 *       事件面确认 / 右侧 AI 面板降级 / 定时简报 / 简报导出 / 皮肤契约 / 端点一致性 / 诚实声明
 */
"use strict";
const fs = require("fs");
const path = require("path");
const { loadApp } = require("../../tools/test-scaffold.js");

const htmlPath = path.resolve(__dirname, "..", "index.html");
const html = fs.readFileSync(htmlPath, "utf8");
const backendPath = path.resolve(__dirname, "..", "..", "backend", "app.py");
const backendSrc = fs.existsSync(backendPath) ? fs.readFileSync(backendPath, "utf8") : "";
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

/* ---------- Round 6：简报导出（v2 含事件面 16 列） ---------- */
console.log("\n[Round 6] 简报 MD / CSV(16列) / 转义 / 空数据");
const md = S.buildBrief(f.scored, "md", { threshold:40, view:"learner" });
ok("MD 含标题与日期", md.indexOf("# 信息照妖镜") >= 0 && md.indexOf("2026-") >= 0);
ok("MD 含视角 / 阈值 / 扫描统计", md.indexOf("视角：") >= 0 && md.indexOf("信号阈值") >= 0 && md.indexOf("扫描") >= 0);
ok("MD 含选题角度与行动建议", md.indexOf("选题") >= 0 && md.indexOf("为什么") >= 0);
const csv = S.buildBrief(f.scored, "csv", { threshold:40, view:"learner" });
const csvHead = csv.split("\n")[0].split(",");
ok("CSV 表头 16 列（11 基础 + 5 事件面）", csvHead.length === 16, "cols="+csvHead.length);
ok("CSV 前 11 列顺序不变", csvHead[0] === '"标题"' && csvHead[6] === '"信号分"' && csvHead[10] === '"选题角度"', csvHead.slice(0,11).join("|"));
ok("CSV 后 5 列为事件面字段", JSON.stringify(csvHead.slice(11)) === JSON.stringify(['"市场"','"品种"','"事件类型"','"影响方向"','"确认状态"']), csvHead.slice(11).join("|"));
ok("CSV 行数 = 1 表头 + 高价值条数", csv.split("\n").length === 1 + f.high.length, "lines="+csv.split("\n").length);
ok("CSV 双引号转义", (function(){
  var x = { card:mk('含"引号",逗号',"",""), scores:S.scoreCard(mk('含"引号",逗号',"",""),R.learner,{}),
            bucket:"none", high:true, flag:null, angle:"角度" };
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
ok("CSV 无事件条目补 5 个空字段", (function(){
  var x = { card:mk("无事件条目","",""), scores:{hype:0,fact:0,signal:80,hits:{hype:[],fact:[],signal:[]}}, bucket:"signal", high:true, flag:null, angle:"角度" };
  var row = S.buildBrief([x],"csv",{view:"learner"}).split("\n")[1];
  return row.split(",").length === 16 && row.indexOf('"","","","",""') >= 0;
})());
ok("CSV/MD 事件面字段写入（带事件条目）", (function(){
  var c = mk("纸浆港口库存环比去库","","");
  c.event = { id:"f:sp:0", market:"futures", symbol:"SHFE:sp", eventType:"库存", impact:"利好", confirmed:"已确认" };
  c.src = "local";
  var x = { card:c, scores:{hype:0,fact:20,signal:80,hits:{hype:[],fact:[],signal:[]}}, bucket:"signal", high:true, flag:null, angle:"角度" };
  var row = S.buildBrief([x],"csv",{view:"learner"}).split("\n")[1];
  var mdt = S.buildBrief([x],"md",{view:"learner"});
  return row.indexOf('"期货"') >= 0 && row.indexOf('"SHFE:sp"') >= 0 && row.indexOf('"库存"') >= 0 &&
         row.indexOf('"已确认"') >= 0 && mdt.indexOf("事件面：") >= 0 && mdt.indexOf("本地真实") >= 0;
})());

/* ---------- Round 7：规则编辑 / 冒烟 / 皮肤契约 ---------- */
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
ok("四态来源元数据齐全（含 live 实时抓取）", !!S.SRC_META.sample && !!S.SRC_META.local && !!S.SRC_META.manual && !!S.SRC_META.live && S.SRC_META.live.label === "实时抓取");
ok("皮肤契约：10 变量齐备", (function(){
  var need = ["--bg","--card","--card2","--accent","--accent2","--up","--down","--txt","--sub","--line"];
  return need.every(v => html.indexOf(v+":") >= 0);
})());
ok("皮肤契约：主题桥接 JS 在位", html.indexOf("NEON-THEME-BRIDGE BEGIN") >= 0);
ok("零依赖：无外部 script src / iframe", !/<script[^>]*\bsrc\s*=/i.test(html) && !/<iframe/i.test(html));

/* ---------- Round 8：事件面确认（v2 新增） ---------- */
console.log("\n[Round 8] 事件面确认：匹配 / 卡片转换 / 展示 HTML");
const EV = { id:"f:sp:0", market:"futures", symbol:"SHFE:sp", eventType:"库存", impact:"利好", confirmed:"已确认" };
const EV2 = { id:"s:0", market:"stock", symbol:"600519", eventType:"财报", impact:"利空", confirmed:"待确认" };
const feed = { ok:true, source:"local", degraded:true, count:2, live_count:0, events:[
  { id:"f:sp:0", title:"纸浆港口库存环比去库", body:"库存下降", date:"2026-11-04", source:"futures_events.json",
    market:"futures", symbol:"SHFE:sp", eventType:"库存", impact:"利好", confirmed:"已确认", src:"local" },
  { id:"l:0", title:"央行公开市场净投放", body:"资金面改善", date:"2026-11-03", source:"akshare",
    market:"macro", symbol:"财经快讯", eventType:"政策", impact:"利好", confirmed:"已确认", src:"live" }
]};
const evCards = S.feedToCards(feed);
ok("feedToCards 空输入返回空数组", S.feedToCards(null).length === 0 && S.feedToCards({}).length === 0);
ok("feedToCards 条数与事件面字段", evCards.length === 2 && evCards[0].event.id === "f:sp:0" && evCards[0].event.market === "futures" && evCards[0].event.symbol === "SHFE:sp");
ok("feedToCards 保留 src=live / local 区分", evCards[0].src === "local" && evCards[1].src === "live");
ok("eventMatches 全选放行", S.eventMatches(EV, "all", "全部") === true);
ok("eventMatches 市场过滤生效", S.eventMatches(EV, "stock", "全部") === false && S.eventMatches(EV2, "stock", "全部") === true);
ok("eventMatches 事件类型过滤生效", S.eventMatches(EV, "all", "库存") === true && S.eventMatches(EV, "all", "财报") === false);
ok("eventMatches 无事件条目仅在全选时放行", S.eventMatches(null, "all", "全部") === true && S.eventMatches(null, "stock", "全部") === false);
ok("eventFaceHtml 输出市场/品种/类型/影响/确认", (function(){
  var h = S.eventFaceHtml(EV);
  return h.indexOf("期货") >= 0 && h.indexOf("SHFE:sp") >= 0 && h.indexOf("库存") >= 0 && h.indexOf("利好") >= 0 && h.indexOf("已确认") >= 0;
})());
ok("eventFaceHtml 待确认/仅传闻有区分 class", S.eventFaceHtml(EV2).indexOf("cfm wait") >= 0 &&
   S.eventFaceHtml({market:"stock",symbol:"X",eventType:"事件",impact:"",confirmed:"仅传闻"}).indexOf("cfm rumor") >= 0);
ok("eventFaceHtml 无事件返回空串且转义", S.eventFaceHtml(null) === "" &&
   S.eventFaceHtml({market:"futures",symbol:'<script>',eventType:"库存",impact:"",confirmed:"已确认"}).indexOf("&lt;script&gt;") >= 0);
ok("eventCols 有/无事件均为 5 列", (function(){
  var a = S.eventCols({card:{event:EV}});
  var b = S.eventCols({card:{}});
  return a.length === 5 && a[0] === "期货" && a[4] === "已确认" && b.length === 5 && b.every(v => v === "");
})());
ok("srcBadgeHtml 四态标签正确", (function(){
  return S.srcBadgeHtml("sample").indexOf("离线示例") >= 0 &&
         S.srcBadgeHtml("local").indexOf("本地真实") >= 0 &&
         S.srcBadgeHtml("manual").indexOf("手动录入") >= 0 &&
         S.srcBadgeHtml("live").indexOf("实时抓取") >= 0;
})());
ok("事件条目并入漏斗：总数增加且带事件面", (function(){
  var saveEv = S.STATE.events, saveM = S.STATE.market, saveE = S.STATE.etype;
  S.STATE.events = evCards; S.STATE.market = "all"; S.STATE.etype = "全部";
  var z = S.recompute();
  var withEv = z.scored.filter(function(x){ return !!x.card.event; }).length;
  S.STATE.events = saveEv; S.STATE.market = saveM; S.STATE.etype = saveE; S.recompute();
  return z.total === 12 && withEv === 2;
})());
ok("市场筛选 visibleItems 只留对应事件条目", (function(){
  var saveEv = S.STATE.events, saveM = S.STATE.market, saveE = S.STATE.etype, saveB = S.STATE.bucket;
  S.STATE.events = evCards; S.STATE.market = "futures"; S.STATE.etype = "全部"; S.STATE.bucket = "all";
  S.recompute();
  var list = S.visibleItems();
  S.STATE.events = saveEv; S.STATE.market = saveM; S.STATE.etype = saveE; S.STATE.bucket = saveB; S.recompute();
  return list.length === 1 && list[0].card.event.market === "futures";
})());

/* ---------- Round 9：A股/期货真实信息源词表（量化视角） ---------- */
console.log("\n[Round 9] 量化视角词表：A股 / 期货真实信息源关键词");
ok("quant.fact 含期货库存/仓单/基差/停产", ["港口库存","仓单","基差","停产","开工率"].every(w => R.quant.fact.indexOf(w) >= 0));
ok("quant.fact 含 A股/宏观 财报/央行/CPI/利率", ["财报","季报","央行","CPI","美联储","利率"].every(w => R.quant.fact.indexOf(w) >= 0));
ok("quant.signal 含可落地信号词", ["库存环比","仓单变化","基差走强","可回测","样本外","破位"].every(w => R.quant.signal.indexOf(w) >= 0));
ok("quant.hint 明确写 A股/期货真实信息源", R.quant.hint.indexOf("A股") >= 0 && R.quant.hint.indexOf("期货") >= 0);
ok("纸浆库存新闻在 quant 下命中事实词、learner 下不命中", (function(){
  var c = mk("纸浆港口库存环比去库，仓单下降，开工率回升", "", "");
  var a = S.scoreCard(c, R.quant, {}), b = S.scoreCard(c, R.learner, {});
  return a.fact > 0 && a.hits.fact.length >= 3 && b.fact === 0;
})());
ok("A股财报/央行新闻在 quant 下命中事实词", (function(){
  var c = mk("季报公布，央行政策与 CPI 数据同步披露", "", "");
  var a = S.scoreCard(c, R.quant, {});
  return a.fact > 0 && a.hits.fact.length >= 3;
})());
ok("learner 词表保持 AI 学习者定位（教程/Colab）", ["教程","Colab","可复现","notebook"].every(w => R.learner.signal.indexOf(w) >= 0));
ok("EVENT_TYPES 覆盖期货/股票/宏观事件类型", ["库存","价格","停产","外盘","财报","政策","公司","事件"].every(t => S.EVENT_TYPES.indexOf(t) >= 0));
ok("MARKET_LABEL 三市场映射完整", S.MARKET_LABEL.futures === "期货" && S.MARKET_LABEL.stock === "股票" && S.MARKET_LABEL.macro === "宏观");

/* ---------- Round 10：右侧 AI 面板 / 降级 / 定时简报 ---------- */
console.log("\n[Round 10] AI 面板降级 / 状态渲染 / 定时简报");
const aiItem = { card:mk("纸浆港口库存环比去库","库存下降","卓创"),
  scores:{hype:0,fact:20,signal:60,hits:{hype:[],fact:["库存"],signal:["去库"]}},
  bucket:"signal", high:true, flag:null, angle:"落地：接进因子池做样本外验证" };
const aiItemEv = JSON.parse(JSON.stringify(aiItem));
aiItemEv.card.event = EV;
ok("aiFallbackParse 明确标注非 AI / 未调用 LLM", (function(){
  var t = S.aiFallbackParse(aiItemEv);
  return t.indexOf("非 AI") >= 0 && t.indexOf("未调用 LLM") >= 0 && t.indexOf("规则降级解析") >= 0;
})());
ok("aiFallbackParse 输出三分、事件面、判断、建议", (function(){
  var t = S.aiFallbackParse(aiItemEv);
  return t.indexOf("炒作 0 / 事实 20 / 信号 60") >= 0 && t.indexOf("事件面：期货") >= 0 &&
         t.indexOf("SHFE:sp") >= 0 && t.indexOf("判断：") >= 0 && t.indexOf("建议：") >= 0;
})());
ok("aiFallbackParse 无事件条目标未分类（不臆造）", S.aiFallbackParse(aiItem).indexOf("事件面：未分类") >= 0);
ok("setAiResult 规则降级标记 src=rule", (function(){
  S.setAiResult("测试输出", "rule");
  return S.STATE.aiLastSrc === "rule" && S.STATE.aiLast === "测试输出";
})());
ok("setAiResult AI 结果标记 src=ai", (function(){
  S.setAiResult("模型输出", "ai");
  return S.STATE.aiLastSrc === "ai";
})());
ok("renderAiStatus 可用时标注「非页面内置」", (function(){
  S.renderAiStatus({available:true,disabled:false,provider:"ollama",model:"qwen2.5:3b"});
  return loaded.doc.getElementById("aiStatus").innerHTML.indexOf("非页面内置") >= 0 && loaded.doc.getElementById("aiStatus").innerHTML.indexOf("✅ 可用") >= 0;
})());
ok("renderAiStatus 不可用时标注规则降级（非 AI）", (function(){
  S.renderAiStatus(null);
  return loaded.doc.getElementById("aiStatus").innerHTML.indexOf("模型不可达") >= 0 && loaded.doc.getElementById("aiStatus").innerHTML.indexOf("非 AI") >= 0;
})());
ok("renderFeedStatus 降级时写明「未真正爬取」", (function(){
  S.STATE.feedMeta = {source:"local",degraded:true,reason:"OFFLINE_MODE=True",count:20,live:0,updated:"2026-11-04 20:00:00"};
  S.renderFeedStatus();
  var h = loaded.doc.getElementById("feedHint").innerHTML;
  S.STATE.feedMeta = null;
  return h.indexOf("未真正爬取") >= 0 && h.indexOf("本地真实") >= 0;
})());
ok("定时配置默认值：启用 / 30 分钟轮询 / 20 点简报", S.STATE.timer.enabled === true && S.STATE.timer.pollMin === 30 && S.STATE.timer.briefHour === 20);
ok("loadState 对轮询/简报小时做 5–240 / 0–23 钳位", (function(){
  var save = { e:S.STATE.timer.enabled, p:S.STATE.timer.pollMin, h:S.STATE.timer.briefHour };
  S.lsSet("infolens_timer", JSON.stringify({enabled:false,pollMin:9999,briefHour:99}));
  S.loadState();
  var r = S.STATE.timer.enabled === false && S.STATE.timer.pollMin === 240 && S.STATE.timer.briefHour === 23;
  S.lsSet("infolens_timer", JSON.stringify({enabled:true,pollMin:1,briefHour:-5}));
  S.loadState();
  r = r && S.STATE.timer.pollMin === 5 && S.STATE.timer.briefHour === 0;
  S.STATE.timer.enabled = save.e; S.STATE.timer.pollMin = save.p; S.STATE.timer.briefHour = save.h;
  S.lsSet("infolens_timer", JSON.stringify({enabled:save.e,pollMin:save.p,briefHour:save.h}));
  return r;
})());
ok("checkBriefTime 到点自动生成简报且一天只生成一次", (function(){
  var saveH = S.STATE.timer.briefHour, saveLast = S.STATE.aiLast, saveSrc = S.STATE.aiLastSrc;
  S.STATE.timer.briefHour = new Date().getHours();
  S.lsSet("infolens_last_brief", "");
  S.checkBriefTime();
  var once = S.lsGet("infolens_last_brief", "") === S.today() && S.STATE.aiLast.indexOf("定时自动生成简报") >= 0 && S.STATE.aiLastSrc === "rule";
  S.STATE.aiLast = "已生成标记";
  S.checkBriefTime();
  var twice = S.STATE.aiLast === "已生成标记";
  S.STATE.timer.briefHour = saveH; S.STATE.aiLast = saveLast; S.STATE.aiLastSrc = saveSrc;
  S.lsSet("infolens_last_brief", "");
  return once && twice;
})());
ok("generateBrief 返回可导出的 Markdown", S.generateBrief(false).indexOf("# 信息照妖镜") >= 0);
ok("callLlm 在 fetch 不可用时同步不抛错、错误交给回调", (function(){
  var threw = false;
  try { S.callLlm("sys", "usr", function(){}); } catch(e){ threw = true; }
  return typeof S.callLlm === "function" && !threw;
})());

/* ---------- Round 11：三栏布局 / 端点一致性 / 诚实声明 ---------- */
console.log("\n[Round 11] 三栏布局 / 端点一致性 / 诚实声明");
ok("三栏布局：左 240 / 中自适应 / 右 320", html.indexOf("grid-template-columns:240px minmax(0,1fr) 320px") >= 0);
ok("窄屏响应式把右侧栏折到整行", html.indexOf("@media(max-width:1280px)") >= 0 && html.indexOf("grid-column:1/-1") >= 0);
ok("右侧边栏含 AI 状态 / 输出 / 结果来源", html.indexOf('id="aiStatus"') >= 0 && html.indexOf('id="aiOut"') >= 0 && html.indexOf('id="aiSrc"') >= 0);
ok("右侧边栏含解析与生成简报按钮", html.indexOf('id="aiParse"') >= 0 && html.indexOf('id="aiBrief"') >= 0);
ok("定时控件齐全（开关 / 轮询 / 简报小时）", html.indexOf('id="timerOn"') >= 0 && html.indexOf('id="pollMin"') >= 0 && html.indexOf('id="briefHour"') >= 0);
ok("新闻源载入与刷新按钮齐全", html.indexOf('id="loadFeed"') >= 0 && html.indexOf('id="feedRefresh"') >= 0);
ok("诚实声明：分数不是结论 / 并未真正爬取 / 不包装成 AI", html.indexOf("不是结论") >= 0 && html.indexOf("并未真正爬取") >= 0 && html.indexOf("不包装成 AI") >= 0);
ok("诚实声明：页面定时器需保持页面打开（非后台常驻）", html.indexOf("需保持页面打开") >= 0 && html.indexOf("非后台常驻") >= 0);
ok("诚实声明：有网 OFFLINE_MODE=False 才真抓取", html.indexOf("OFFLINE_MODE=False") >= 0 && html.indexOf("degraded:true") >= 0);
ok("诚实声明：模型在后端非页面内置 / 影响方向仅参考", html.indexOf("非页面内置") >= 0 && html.indexOf("仅供参考") >= 0);
ok("端点一致性：前端仅用 3 个 /api 端点", (function(){
  var eps = (html.match(/\/api\/[A-Za-z_][A-Za-z0-9_]*(?:\/[A-Za-z_][A-Za-z0-9_]*)*/g) || []).filter(function(v,i,a){ return a.indexOf(v) === i; }).sort();
  return JSON.stringify(eps) === JSON.stringify(["/api/info_lens_feed","/api/llm","/api/llm/status"]);
})());
ok("端点一致性：3 个端点后端均有 @app.route", backendSrc.length > 0 &&
   ["/api/info_lens_feed","/api/llm","/api/llm/status"].every(function(e){
     return backendSrc.indexOf('@app.route("' + e + '"') >= 0;
   }));
ok("后端 feed 端点声明 source=local/live 与 degraded 语义", backendSrc.indexOf('"degraded": degraded') >= 0 &&
   backendSrc.indexOf('"source": "live" if live else "local"') >= 0 &&
   backendSrc.indexOf("OFFLINE_MODE=True：沙箱出网被拦") >= 0);
ok("后端 feed 聚合期货/股票/宏观三类本地真实数据", backendSrc.indexOf('"futures_events.json"') >= 0 &&
   backendSrc.indexOf('"stocknote.json"') >= 0 && backendSrc.indexOf('"market_brief.json"') >= 0);

console.log(`\n汇总：通过 ${pass} / 失败 ${fail}`);
process.exit(fail ? 1 : 0);
