/* 逻辑自测（复用 tools/test-scaffold.js 共享脚手架：DOM 桩 + vm 加载）*/
const { loadApp } = require("../../tools/test-scaffold.js");
const { sandbox, src, err, doc, window, localStorage } = loadApp(__dirname);

let pass=0, fail=0; const fails=[];
function ok(c,msg){ if(c) pass++; else { fail++; fails.push(msg); } }
function eq(a,b,msg){ ok(a===b, msg+` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`); }
function inc(a,b,msg){ ok(a!==b || (a===b && true), msg); }

// ---------- 1. esc ----------
eq(sandbox.esc("<b>"), "&lt;b&gt;", "esc < >");
eq(sandbox.esc("&"), "&amp;", "esc &");
eq(sandbox.esc('"'), "&quot;", "esc 双引号");
eq(sandbox.esc("'"), "&#39;", "esc 单引号");
eq(sandbox.esc(null), "", "esc null => 空串");

// ---------- 2. sanitizeHTML (白名单 + 防 XSS) ----------
eq(sandbox.sanitizeHTML("纯文本"), "纯文本", "sanitizeHTML 纯文本透传");
ok(sandbox.sanitizeHTML("<script>alert(1)</script>").includes("&lt;script&gt;"), "sanitizeHTML 拦截 script");
ok(sandbox.sanitizeHTML("<img src=x onerror=alert(1)>").includes("&lt;img"), "sanitizeHTML 拦截 img/onerror");
ok(sandbox.sanitizeHTML("<b>粗体</b>") === "<b>粗体</b>", "sanitizeHTML 放开 <b>");
ok(sandbox.sanitizeHTML("<a href=\"http://x.com\">链接</a>").includes('href="http://x.com"'), "sanitizeHTML 允许 http 链接");
ok(!sandbox.sanitizeHTML("<a href=\"javascript:alert(1)\">x</a>").includes('<a href='), "sanitizeHTML 拒绝 javascript: 链接");
ok(sandbox.sanitizeHTML("<em>斜</em>") === "<em>斜</em>", "sanitizeHTML 放开 <em>");
ok(!sandbox.sanitizeHTML("<<script>>").includes("<script>"), "sanitizeHTML 嵌套转义后仍安全");

// ---------- 3. asNum ----------
eq(sandbox.asNum("12.5",0), 12.5, "asNum 正常解析");
eq(sandbox.asNum("abc", -1), -1, "asNum 非法 => 默认");
eq(sandbox.asNum("", 0), 0, "asNum 空 => 默认");
eq(sandbox.asNum("3", 9), 3, "asNum 整数");

// ---------- 4. sanitizeETF ----------
const se = sandbox.sanitizeETF({code:"510300",name:"沪深300ETF",size:"3800",ret:"12.4",fee:0.15,trackErr:0.03});
eq(se.code, "510300", "sanitizeETF code 字符串化");
eq(se.size, 3800, "sanitizeETF size 数字");
eq(se.ret, 12.4, "sanitizeETF ret 数字");
const se2 = sandbox.sanitizeETF(null);
ok(se2 && se2.code==="" && se2.size===0, "sanitizeETF(null) 安全默认");
const se3 = sandbox.sanitizeETF({code:123,name:456,size:"x",ret:undefined});
eq(se3.code, "123", "sanitizeETF 数字 code 转字符串");
eq(se3.size, 0, "sanitizeETF 非法 size => 0");

// ---------- 5. filterETFs ----------
const SAMPLE = sandbox.FALLBACK_ETFS.map(sandbox.sanitizeETF);
eq(sandbox.filterETFs(SAMPLE, {}).length, SAMPLE.length, "filter 空条件全通过");
eq(sandbox.filterETFs(SAMPLE, {type:"宽基"}).length, 4, "filter 按类型 宽基=4");
eq(sandbox.filterETFs(SAMPLE, {type:"行业",industry:"半导体"}).length, 1, "filter 类型+行业");
eq(sandbox.filterETFs(SAMPLE, {minSize:500}).length, sandbox.filterETFs(SAMPLE,{}).filter(e=>e.size>=500).length, "filter 最小规模");
eq(sandbox.filterETFs(SAMPLE, {minRet:20}).every(e=>e.ret>=20), true, "filter 最小收益");
eq(sandbox.filterETFs(SAMPLE, {maxRet:0}).every(e=>e.ret<=0), true, "filter 最大收益<=0");
eq(sandbox.filterETFs(SAMPLE, {minRet:5,maxRet:10}).every(e=>e.ret>=5&&e.ret<=10), true, "filter 收益区间");
eq(sandbox.filterETFs(SAMPLE, {maxFee:0.2}).every(e=>e.fee<=0.2), true, "filter 最大费率");
eq(sandbox.filterETFs(SAMPLE, {maxTrack:0.1}).every(e=>e.trackErr<=0.1), true, "filter 最大跟踪误差");
eq(sandbox.filterETFs(SAMPLE, {kw:"芯片"}).length, 1, "filter 关键词 芯片");
eq(sandbox.filterETFs(SAMPLE, {kw:"588"}).length, 1, "filter 关键词 代码588");
const wset = new Set(["510300","518880"]);
eq(sandbox.filterETFs(SAMPLE, {watchOnly:true}, wset).length, 2, "filter 仅看自选");
eq(sandbox.filterETFs(SAMPLE, {watchOnly:true}, new Set()).length, 0, "filter 自选为空");

// ---------- 6. sortETFs ----------
const byRetDesc = sandbox.sortETFs(SAMPLE, "ret", "desc");
ok(byRetDesc[0].ret >= byRetDesc[byRetDesc.length-1].ret, "sort ret desc 有序");
const byRetAsc = sandbox.sortETFs(SAMPLE, "ret", "asc");
ok(byRetAsc[0].ret <= byRetAsc[byRetAsc.length-1].ret, "sort ret asc 有序");
const bySize = sandbox.sortETFs(SAMPLE, "size", "desc");
eq(bySize[0].code, "510300", "sort size desc 最大规模=沪深300");
const byName = sandbox.sortETFs(SAMPLE, "name", "asc");
ok(byName[0].name.localeCompare(byName[1].name,"zh")<=0, "sort name 字典序");
// 稳定性：相同值按 code 排序
const two = [sandbox.sanitizeETF({code:"bbb",ret:5}), sandbox.sanitizeETF({code:"aaa",ret:5})];
eq(sandbox.sortETFs(two,"ret","desc")[0].code, "aaa", "sort 同值按 code");

// ---------- 7. computeStats ----------
const st1 = sandbox.computeStats(SAMPLE);
eq(st1.count, SAMPLE.length, "stats count");
ok(Math.abs(st1.avgRet - SAMPLE.reduce((s,e)=>s+e.ret,0)/SAMPLE.length) < 1e-9, "stats avgRet 正确");
ok(st1.best.ret >= st1.worst.ret, "stats best>=worst");
eq(sandbox.computeStats([]).count, 0, "stats 空 => count 0");

// ---------- 8. csvCell (防注入) ----------
eq(sandbox.csvCell("hello"), "hello", "csvCell 普通透传");
eq(sandbox.csvCell("=cmd"), "'=cmd", "csvCell 防 = 注入");
eq(sandbox.csvCell("+x"), "'+x", "csvCell 防 + 注入");
eq(sandbox.csvCell("-x"), "'-x", "csvCell 防 - 注入");
eq(sandbox.csvCell("@x"), "'@x", "csvCell 防 @ 注入");
eq(sandbox.csvCell('a"b'), '"a""b"', "csvCell 引号翻倍");
eq(sandbox.csvCell("a,b"), '"a,b"', "csvCell 逗号加引号");
eq(sandbox.csvCell("a\nb"), '"a\nb"', "csvCell 换行加引号");
eq(sandbox.csvCell(null), "", "csvCell null => 空");

// ---------- 9. exportCSV ----------
const csv = sandbox.exportCSV(SAMPLE.slice(0,3));
ok(csv.startsWith("﻿"), "exportCSV 含 BOM");
ok(csv.split("\n")[0].includes("代码"), "exportCSV 表头");
ok(csv.includes("510300"), "exportCSV 含数据");
ok(csv.split("\n").length === 4, "exportCSV 行数(表头+3)");

// ---------- 10. exportJSON ----------
const json = JSON.parse(sandbox.exportJSON(SAMPLE.slice(0,2)));
eq(json.count, 2, "exportJSON count");
ok(typeof json.exportedAt === "string" && json.exportedAt.length>0, "exportJSON 含 exportedAt");
eq(json.items[0].code, "510300", "exportJSON 项归一化");

// ---------- 11. render 转义 / 空态 ----------
sandbox.ETFS = [
  sandbox.sanitizeETF({code:"X1",name:'<script>alert(1)</script>',type:"行业",industry:"测试",size:10,ret:5,fee:0.5,trackErr:0.1,issuer:"<b>o</b>"}),
  sandbox.sanitizeETF({code:"X2",name:"正常",type:"行业",industry:"测试",size:20,ret:-3,fee:0.5,trackErr:0.1,issuer:"o"})
];
sandbox.watch = new Set();
sandbox.render();
const bodyHtml = doc.getElementById("body").innerHTML;
ok(bodyHtml.includes("&lt;script&gt;"), "render 转义 XSS 名称");
ok(bodyHtml.includes("&lt;b&gt;"), "render 转义 XSS 管理人");
ok(bodyHtml.includes("正常") && bodyHtml.includes("X1"), "render 渲染多条");
// 空态
sandbox.ETFS = [];
sandbox.render();
eq(doc.getElementById("empty").style.display, "block", "render 空态显示");
eq(doc.getElementById("body").innerHTML, "", "render 空态 tbody 空");

// ---------- 12. getWatch / saveWatch ----------
sandbox.saveWatch(new Set(["510300","518880"]));
const ws = sandbox.getWatch();
ok(ws.has("510300") && ws.has("518880"), "saveWatch/getWatch 往返");
sandbox.saveWatch(new Set());
eq(sandbox.getWatch().size, 0, "saveWatch 清空");

// ---------- 13. validateForm (输入校验) ----------
doc.getElementById("fRetMin").value = "10";
doc.getElementById("fRetMax").value = "5";
sandbox.validateForm();
eq(doc.getElementById("fRetMin").value, "5", "validateForm 收益区间自动交换(下限)");
eq(doc.getElementById("fRetMax").value, "10", "validateForm 收益区间自动交换(上限)");
doc.getElementById("fFee").value = "-1";
sandbox.validateForm();
eq(doc.getElementById("fFee").value, "0", "validateForm 负费率归零");
doc.getElementById("fTrack").value = "-2";
sandbox.validateForm();
eq(doc.getElementById("fTrack").value, "0", "validateForm 负跟踪误差归零");

// ---------- 14. 隐藏 bug 修复：持久化行业筛选在 reload 后丢失 ----------
sandbox.ETFS = sandbox.FALLBACK_ETFS.map(sandbox.sanitizeETF);
doc.getElementById("fType").value = "行业";
sandbox.refreshIndustryOptions();
ok(doc.getElementById("fInd").innerHTML.includes("半导体"), "refreshIndustryOptions 按类型生成行业选项");
localStorage.setItem("etf_filters_v1", JSON.stringify({type:"行业", industry:"半导体"}));
sandbox.loadFilters();
eq(doc.getElementById("fType").value, "行业", "loadFilters 恢复类型");
eq(doc.getElementById("fInd").value, "半导体", "loadFilters 恢复行业(修复隐藏 bug)");
localStorage.removeItem("etf_filters_v1");

// ---------- 15. clearCompare ----------
sandbox.compareSel = new Set(["510300","518880"]);
sandbox.clearCompare();
eq(sandbox.compareSel.size, 0, "clearCompare 清空选择集合");
eq(doc.getElementById("cmpBtn").textContent, "对比选中 (0)", "clearCompare 更新按钮文案");
eq(doc.getElementById("compare").className, "compare", "clearCompare 隐藏对比面板");

// ---------- 16. 导出选择集（自选/对比） ----------
sandbox.ETFS = sandbox.FALLBACK_ETFS.map(sandbox.sanitizeETF);
sandbox.watch = new Set(["510300"]);
sandbox.compareSel = new Set(["518880"]);
eq(sandbox.getExportList("watch").length, 1, "getExportList watch 数量");
eq(sandbox.getExportList("watch")[0].code, "510300", "getExportList watch 正确项");
eq(sandbox.getExportList("compare").length, 1, "getExportList compare 数量");
eq(sandbox.getExportList("compare")[0].code, "518880", "getExportList compare 正确项");
sandbox.curList = sandbox.ETFS.slice(0,2);
eq(sandbox.getExportList("cur").length, 2, "getExportList cur 数量");
sandbox.exportSet("watch");
ok(true, "exportSet 执行不抛错");

// ---------- 汇总 ----------
console.log(`\nETFPicker 自测：${pass} 通过 / ${fail} 失败`);
if(fail){ console.log("失败项："); fails.forEach(f=>console.log("  ✗ "+f)); process.exit(1); }
else { console.log("全部通过 ✅"); process.exit(0); }

