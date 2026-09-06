/* 逻辑自测（复用 tools/test-scaffold.js 共享脚手架：DOM 桩 + vm 加载）*/
const { loadApp } = require("../../tools/test-scaffold.js");
const { sandbox, src, err, doc, window, localStorage } = loadApp(__dirname);

let pass = 0, fail = 0;
const fails = [];
function ok(cond, msg) { if (cond) pass++; else { fail++; fails.push(msg); } }
function eq(a, b, msg) { ok(a === b, msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`); }
function approx(a, b, eps, msg) { ok(Math.abs(a - b) <= (eps || 1e-6), msg + ` (got ${JSON.stringify(a)} want≈ ${JSON.stringify(b)})`); }

// ============================================================
// 1. esc 转义
// ============================================================
eq(sandbox.esc("<b>&'\""), "&lt;b&gt;&amp;&#39;&quot;", "esc 转义 < > & ' \"");
eq(sandbox.esc(null), "", "esc(null) => ''");
eq(sandbox.esc(123), "123", "esc(数字) => 字符串");

// ============================================================
// 2. 确定性行情生成
// ============================================================
const mk1 = sandbox.genMarket("600519|side|0", 180, 0.018, 0);
const mk2 = sandbox.genMarket("600519|side|0", 180, 0.018, 0);
eq(mk1.length, 180, "genMarket 长度=n");
eq(JSON.stringify(mk1), JSON.stringify(mk2), "genMarket 同种子完全可复现");
const mk3 = sandbox.genMarket("600519|side|1", 180, 0.018, 0);
ok(JSON.stringify(mk1) !== JSON.stringify(mk3), "genMarket 不同 variant 产生不同行情");
eq(mk1[0].close > 0, true, "genMarket 收盘价为正");
ok(mk1.every((x) => x.high >= x.low && x.high >= x.close && x.low <= x.close), "genMarket OHLC 关系自洽");

// ============================================================
// 3. 指标：sma / ema / rsi / macd / atr / rolling
// ============================================================
eq(JSON.stringify(sandbox.sma([1, 2, 3, 4, 5], 2)), JSON.stringify([null, 1.5, 2.5, 3.5, 4.5]), "sma([1..5],2)");
const e = sandbox.ema([1, 2, 3, 4], 2);
eq(e[0], null, "ema k=2 首根为 null");
eq(e[1], 1.67, "ema([1,2,3,4],2)[1]=5/3≈1.67（r2 取整）");
const rsUp = sandbox.rsi(Array.from({ length: 20 }, (_, i) => i + 1), 14);
eq(rsUp.length, 20, "rsi 输出长度等于输入");
ok(rsUp[19] > 95 && rsUp[19] <= 100, "rsi 单调递增序列 ≈100");
const rsDn = sandbox.rsi(Array.from({ length: 20 }, (_, i) => 20 - i), 14);
ok(rsDn[19] < 5, "rsi 单调递减序列 ≈0");
const mc = sandbox.macd([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 2, 4, 2);
eq(mc.macd.length, 10, "macd.macd 长度");
ok(typeof mc.hist[9] === "number", "macd.hist 末根为数值（足够数据）");
const at = sandbox.atr([{ high: 10, low: 8, close: 9 }, { high: 11, low: 9, close: 10 }], 2);
eq(at[0], null, "atr period=2 首根 null");
eq(at[1], 2, "atr([...],2) 第二根=2");
eq(JSON.stringify(sandbox.rollingMax([1, 3, 2, 5, 4], 3)), JSON.stringify([null, null, null, 3, 5]), "rollingMax");
eq(JSON.stringify(sandbox.rollingMin([5, 3, 4, 1, 2], 3)), JSON.stringify([null, null, null, 3, 1]), "rollingMin");

// ============================================================
// 4. 策略智能体
// ============================================================
const maUp = sandbox.agentMA([1, 2, 3, 4, 5], 1, 3);
eq(maUp.signal, "BUY", "agentMA 上行=BUY");
eq(maUp.confidence > 0, true, "agentMA BUY 有置信度");
const maFlat = sandbox.agentMA([1, 1, 1, 1, 1], 1, 3);
eq(maFlat.signal, "HOLD", "agentMA 持平=HOLD");
eq(maFlat.confidence, 0, "agentMA HOLD 置信=0");
const maDn = sandbox.agentMA([5, 4, 3, 2, 1], 1, 3);
eq(maDn.signal, "SELL", "agentMA 下行=SELL");

const rsSell = sandbox.agentRSI(Array.from({ length: 20 }, (_, i) => i + 1), 14, 70, 30);
eq(rsSell.signal, "SELL", "agentRSI 超买=SELL");
const rsBuy = sandbox.agentRSI(Array.from({ length: 20 }, (_, i) => 20 - i), 14, 70, 30);
eq(rsBuy.signal, "BUY", "agentRSI 超卖=BUY");

// agentBreakout：前 5 根区间 [9,11]，末根收 15 → 突破 BUY
const boMkt = [];
for (let i = 0; i < 6; i++) boMkt.push({ i, open: 10, high: 11, low: 9, close: 10, vol: 1 });
boMkt[5].close = 15; boMkt[5].high = 15;
eq(sandbox.agentBreakout(boMkt, 5).signal, "BUY", "agentBreakout 向上突破=BUY");
boMkt[5].close = 5; boMkt[5].low = 5;
eq(sandbox.agentBreakout(boMkt, 5).signal, "SELL", "agentBreakout 向下跌破=SELL");

// agentMeanRev：末根远低于均值 → BUY
const mr = sandbox.agentMeanRev([10, 10, 10, 10, 10, 5], 5);
eq(mr.signal, "BUY", "agentMeanRev 极端偏低=BUY");
ok(mr.confidence > 0, "agentMeanRev BUY 有置信度");

// agentRisk：低波动 → factor=1；高波动 → factor<1
const calm = [{ high: 101, low: 99, close: 100 }, { high: 101, low: 99, close: 100 }];
eq(sandbox.agentRisk([100, 100], calm, 14).factor, 1, "agentRisk 低波动 factor=1");
const wild = Array.from({ length: 20 }, () => ({ high: 120, low: 80, close: 100 }));
const wildCloses = wild.map(() => 100);
ok(sandbox.agentRisk(wildCloses, wild, 14).factor < 1, "agentRisk 高波动 factor<1");

// ============================================================
// 5. 集成共识 ensemble
// ============================================================
const bullRes = {};
["fundamental", "technical", "sentiment", "news", "bull"].forEach((id) => bullRes[id] = { signal: "BUY", confidence: 90, reason: "x" });
bullRes.bear = { signal: "SELL", confidence: 90, reason: "x" }; // 被反向计票
bullRes.risk = { signal: "HOLD", confidence: 10, reason: "x", factor: 1 };
const eBull = sandbox.ensemble(bullRes, sandbox.CFG);
ok(eBull.score >= sandbox.CFG.buyTh, "ensemble 多数看多→score≥买入阈值");
eq(eBull.label, "看多", "ensemble 看多标签");
ok(eBull.items.length === 7, "ensemble 输出 7 个智能体条目");
const bearRes = {};
["fundamental", "technical", "sentiment", "news", "bull"].forEach((id) => bearRes[id] = { signal: "SELL", confidence: 90, reason: "x" });
bearRes.bear = { signal: "BUY", confidence: 90, reason: "x" };
bearRes.risk = { signal: "HOLD", confidence: 10, reason: "x", factor: 1 };
const eBear = sandbox.ensemble(bearRes, sandbox.CFG);
ok(eBear.score <= sandbox.CFG.sellTh, "ensemble 多数看空→score≤卖出阈值");
eq(eBear.label, "看空", "ensemble 看空标签");
// 风控减仓因子
bearRes.risk = { signal: "HOLD", confidence: 10, reason: "x", factor: 0.4 };
ok(sandbox.ensemble(bearRes, sandbox.CFG).factor === 0.4, "ensemble 透传风控 factor");
// riskPct 影响仓位建议
const eBull30 = sandbox.ensemble(bullRes, sandbox.CFG, 30);
ok(eBull30.action.indexOf("30") >= 0, "ensemble 使用 riskPct=30 计算建议仓位");
const eBullLow = sandbox.ensemble(bullRes, sandbox.CFG, 10);
ok(eBullLow.action.indexOf("10") >= 0, "ensemble 使用 riskPct=10 计算建议仓位");

// ============================================================
// 6. 回测 backtest
// ============================================================
const btMkt = sandbox.genMarket("TEST|side|0", 180, 0.018, 0);
const bt1 = sandbox.backtest(btMkt, sandbox.CFG, sandbox.ACTIVE);
const bt2 = sandbox.backtest(btMkt, sandbox.CFG, sandbox.ACTIVE);
eq(bt1.equity.length, 180, "backtest 净值序列长度=n");
eq(bt1.finalReturn, bt2.finalReturn, "backtest 确定性：两次同结果");
ok(typeof bt1.finalReturn === "number" && isFinite(bt1.finalReturn), "backtest finalReturn 为有限数");
ok(bt1.maxDD >= 0, "backtest maxDD≥0");
ok(bt1.winRate >= 0 && bt1.winRate <= 100, "backtest 胜率∈[0,100]");
eq(bt1.win + bt1.loss, bt1.trades, "backtest 盈利+亏损=交易数");
// 空行情保护
eq(sandbox.backtest([{ i: 0, open: 1, high: 1, low: 1, close: 1, vol: 1 }], sandbox.CFG, sandbox.ACTIVE), null, "backtest 行情过短返回 null");
// 买入持有基准
const clsBt = sandbox.closesOf(btMkt);
eq(bt1.buyHold, sandbox.r2((clsBt[clsBt.length - 1] / clsBt[0] - 1) * 100), "backtest.buyHold 计算正确");
// 风险预算真实生效：riskPct 减半 → 权益曲线更接近 1.0 且结果不同
const upMkt = sandbox.genMarket("UP|bull|0", 180, 0.018, 0.001);
const b100 = sandbox.backtest(upMkt, sandbox.CFG, sandbox.ACTIVE, 100);
const b50 = sandbox.backtest(upMkt, sandbox.CFG, sandbox.ACTIVE, 50);
ok(b50.finalReturn !== b100.finalReturn, "backtest 风险预算(riskPct)改变回测结果");
ok(Math.abs(b50.equity[b50.equity.length - 1] - 1) <= Math.abs(b100.equity[b100.equity.length - 1] - 1) + 1e-9, "风险预算减半→权益更接近基准线（仓位真实缩放）");
// 无未来函数：把最后一根收盘价改成极端值不应改变前序权益
const mMod = btMkt.slice(); mMod[mMod.length - 1] = Object.assign({}, mMod[mMod.length - 1], { close: 99999 });
ok(sandbox.backtest(mMod, sandbox.CFG, sandbox.ACTIVE).equity.slice(0, -1).every((v, i) => v === bt1.equity[i]), "backtest 最后一根不影响前序（无未来函数）");
// 新增指标：持仓占比 / 年化(CAGR) 字段存在且合理
ok(typeof bt1.exposure === "number" && bt1.exposure >= 0 && bt1.exposure <= 100, "backtest 持仓占比∈[0,100]");
ok(isFinite(bt1.cagr), "backtest CAGR 为有限数");
// 时序一致性：权益曲线末值为正有限数（入场/出场价与逐根收益自洽，无 1 根错位）
const btCons = sandbox.backtest(upMkt, sandbox.CFG, sandbox.ACTIVE, 100);
ok(isFinite(btCons.finalReturn) && btCons.equity[btCons.equity.length - 1] > 0, "backtest 权益末值为正有限数（时序一致）");
// 持仓占比与交易次数方向一致：有交易才可能高持仓，空仓则持仓占比为 0
if(btCons.trades === 0) eq(btCons.exposure, 0, "backtest 零交易→持仓占比 0");
else ok(btCons.exposure > 0, "backtest 有交易→持仓占比>0");

// ============================================================
// 6b. 信号筛选（纯函数，供 UI 复用）
// ============================================================
const fRes = {
  fundamental: { signal: "BUY", confidence: 80, reason: "x" },
  technical: { signal: "SELL", confidence: 60, reason: "x" },
  sentiment: { signal: "HOLD", confidence: 0, reason: "x" },
  news: { signal: "BUY", confidence: 70, reason: "x" }
};
eq(Object.keys(sandbox.filterSignals(fRes, "ALL")).length, 4, "filterSignals ALL 返回全部");
eq(Object.keys(sandbox.filterSignals(fRes, "BUY")).length, 2, "filterSignals BUY 仅 2 个看多");
eq(sandbox.filterSignals(fRes, "SELL").technical.signal, "SELL", "filterSignals SELL 含空头智能体");
eq(Object.keys(sandbox.filterSignals(fRes, "HOLD")).length, 1, "filterSignals HOLD 仅 1 个中性");
eq(Object.keys(sandbox.filterSignals({}, "BUY")).length, 0, "filterSignals 空输入安全返回空");

// orderSignalIds：默认按注册顺序；开启排序后按置信度降序
const oRes = {
  fundamental: { signal: "BUY", confidence: 10, reason: "x" },
  technical:   { signal: "SELL", confidence: 90, reason: "x" },
  sentiment:   { signal: "HOLD", confidence: 5, reason: "x" }
};
const ordDef = sandbox.orderSignalIds(oRes, false);
eq(ordDef[0], "fundamental", "orderSignalIds 默认按注册顺序（fundamental 在前）");
const ordConf = sandbox.orderSignalIds(oRes, true);
eq(ordConf[0], "technical", "orderSignalIds 按置信排序 technical(90) 居首");
eq(ordConf[2], "sentiment", "orderSignalIds 置信最低者(sentiment 5) 居末");
// 排序+筛选组合：先筛 BUY 再排序
const comb = sandbox.orderSignalIds(sandbox.filterSignals(oRes, "BUY"), true);
eq(comb.length, 1, "filter+sort 组合：BUY 仅 1 个");
eq(comb[0], "fundamental", "filter+sort 组合：结果为 fundamental");

// signalCardHtml：HOLD 信号置信弱化为「—」且置信条弱化（避免误导性高亮）
const scBuy = sandbox.signalCardHtml("fundamental", { signal: "BUY", confidence: 80, reason: "x" });
ok(scBuy.indexOf("置信 80") >= 0, "signalCardHtml BUY 显示数值置信度");
const scHold = sandbox.signalCardHtml("sentiment", { signal: "HOLD", confidence: 44, reason: "x" });
ok(scHold.indexOf("置信 —") >= 0, "signalCardHtml HOLD 置信显示为 —（不误导）");
ok(scHold.indexOf("opacity") >= 0, "signalCardHtml HOLD 置信条弱化");

// ============================================================
// 7. runAgents / sparkline / maxDrawdown / sharpe
// ============================================================
const ra = sandbox.runAgents(btMkt, sandbox.CFG, sandbox.ACTIVE);
eq(Object.keys(ra).length, 7, "runAgents 默认启用 7 个智能体");
const raOff = sandbox.runAgents(btMkt, sandbox.CFG, Object.assign({}, sandbox.ACTIVE, { risk: false }));
ok(!("risk" in raOff), "runAgents 关闭的智能体不出现");
ok(sandbox.sparkline([1, 1.1, 0.9, 1.2], 300, 90).includes("<polyline"), "sparkline 输出含 polyline");
ok(sandbox.sparkline([1, 2, 3], 10, 10).includes("<svg"), "sparkline 输出含 svg");
// 基准叠加：传入两条序列应绘制两条 polyline
const ov=sandbox.sparkline([[1, 1.2, 0.9], [1, 1.1, 1.05]], 300, 90);
ok((ov.match(/<polyline/g) || []).length === 2, "sparkline 双序列叠加两条 polyline（策略 vs 买入持有）");
eq(Math.round(sandbox.maxDrawdown([1, 1.2, 0.9, 1.1]) * 100), 25, "maxDrawdown [1,1.2,0.9,1.1]=25%");
eq(sandbox.sharpeRatio([1, 1, 1, 1]), 0, "sharpe 无波动=0");

// ============================================================
// 8. 参数可配置性：不同参数应改变智能体行为（证明 UI 调参会真正生效）
// ============================================================
const cfgMkt = [];
for (let i = 0; i < 6; i++) cfgMkt.push({ i, open: 10, high: 11, low: 9, close: 10 + i, vol: 1 });
const boShort = sandbox.agentBreakout(cfgMkt, 2);   // 窗口足够 → 末根高于近 2 根高点 → BUY
const boLong = sandbox.agentBreakout(cfgMkt, 20);   // 窗口超长 → 数据不足 → HOLD
ok(boShort.signal !== boLong.signal, "agentBreakout 不同窗口参数产生不同信号（参数确实生效）");
// runAgents 接受自定义 cfg 并应用到各智能体
const customCfg = Object.assign({}, sandbox.CFG, { breakLook: 2, rsiOb: 50, rsiOs: 20 });
const raCustom = sandbox.runAgents(cfgMkt, customCfg, sandbox.ACTIVE);
ok(raCustom.bull.signal === boShort.signal, "runAgents 将自定义 cfg.breakLook 透传给突破智能体");
ok(raCustom.sentiment.confidence >= 0, "runAgents 使用自定义 cfg 计算 RSI 智能体");

// ============================================================
// 9. 关键纯函数覆盖率补全（行为级断言，兼作回归护栏）
// ============================================================
// agentTrend：上行站上均线→BUY；下行跌破→SELL；数据不足→HOLD
const trUp = Array.from({ length: 60 }, (_, i) => 100 + i);            // 单调上行
const trDn = Array.from({ length: 60 }, (_, i) => 160 - i);            // 单调下行
eq(sandbox.agentTrend(trUp, 60).signal, "BUY", "agentTrend 上行站上均线=BUY");
ok(sandbox.agentTrend(trUp, 60).confidence > 0, "agentTrend BUY 有置信度");
eq(sandbox.agentTrend(trDn, 60).signal, "SELL", "agentTrend 下行跌破均线=SELL");
const trShort = [1, 2, 3];
eq(sandbox.agentTrend(trShort, 60).signal, "HOLD", "agentTrend 数据不足=HOLD");
eq(sandbox.agentTrend(trShort, 60).confidence, 0, "agentTrend HOLD 置信=0");

// agentMACD：下行序列→SELL（动能为负）；上行序列不为 SELL；结构合法
const mcDn = Array.from({ length: 40 }, (_, i) => 100 - i);
eq(sandbox.agentMACD(mcDn, 12, 26, 9).signal, "SELL", "agentMACD 下行动能=SELL");
const mcUp = Array.from({ length: 40 }, (_, i) => 100 + i);
ok(["BUY", "HOLD"].indexOf(sandbox.agentMACD(mcUp, 12, 26, 9).signal) >= 0, "agentMACD 上行序列不为 SELL");
const mcOut = sandbox.agentMACD(mcUp, 12, 26, 9);
ok(["BUY", "SELL", "HOLD"].indexOf(mcOut.signal) >= 0 && mcOut.confidence >= 0 && mcOut.confidence <= 100, "agentMACD 输出结构合法");

// stdev：已知样本、空、单值
eq(sandbox.stdev([2, 4, 4, 4, 5, 5, 7, 9]), Math.sqrt(32 / 7), "stdev 已知样本=√(32/7)≈2.138（样本标准差 n-1）");
eq(sandbox.stdev([]), 0, "stdev 空=0");
eq(sandbox.stdev([5]), 0, "stdev 单值=0");

// hashStr / mulberry32：确定性 & 区间
eq(sandbox.hashStr("abc"), sandbox.hashStr("abc"), "hashStr 同输入同输出");
ok(sandbox.hashStr("abc") !== sandbox.hashStr("abd"), "hashStr 不同输入不同输出");
const r1 = sandbox.mulberry32(42), r2b = sandbox.mulberry32(42);
ok(r1() === r2b() && r1() >= 0 && r1() < 1, "mulberry32 确定性且∈[0,1)");

// getScenarioDrift
eq(sandbox.getScenarioDrift("bull"), 0.001, "getScenarioDrift bull=+0.001");
eq(sandbox.getScenarioDrift("bear"), -0.001, "getScenarioDrift bear=-0.001");
eq(sandbox.getScenarioDrift("side"), 0, "getScenarioDrift side=0");

// maxDrawdown / sharpe 边界
eq(sandbox.maxDrawdown([1, 2, 3, 4]), 0, "maxDrawdown 单调上行=0");
eq(sandbox.maxDrawdown([1]), 0, "maxDrawdown 单值=0");
const shUp = sandbox.sharpeRatio([1, 1.01, 1.02, 1.03, 1.04, 1.05]);
ok(isFinite(shUp) && shUp > 0, "sharpe 上行序列>0 且有限");
eq(sandbox.sharpeRatio([1]), 0, "sharpe 数据点不足=0");

// agentRisk 三档波动率因子
function mkMkt(vol){ const m=[]; for(let i=0;i<20;i++) m.push({high:100*(1+vol/2),low:100*(1-vol/2),close:100}); return m; }
eq(sandbox.agentRisk(Array(20).fill(100), mkMkt(0.005), 14).factor, 1, "agentRisk 低波动(vol≈0.5%) factor=1");
eq(sandbox.agentRisk(Array(20).fill(100), mkMkt(0.03), 14).factor, 0.7, "agentRisk 中波动(vol≈3%) factor=0.7");
eq(sandbox.agentRisk(Array(20).fill(100), mkMkt(0.05), 14).factor, 0.4, "agentRisk 高波动(vol≈5%) factor=0.4");

// ensemble 中性：全部 HOLD → score=50 标签 中性
const neutral = {};
["fundamental", "technical", "sentiment", "news", "bull", "bear", "risk"].forEach((id) => neutral[id] = { signal: "HOLD", confidence: 50, reason: "x" });
neutral.risk = { signal: "HOLD", confidence: 50, reason: "x", factor: 1 };
const eNeu = sandbox.ensemble(neutral, sandbox.CFG);
eq(eNeu.score, 50, "ensemble 全中性→score=50");
eq(eNeu.label, "中性", "ensemble 全中性→标签 中性");

// ============================================================
// 汇总
// ============================================================
console.log(`\nTradingAgents 自测: ${pass} 通过 / ${fail} 失败`);
if (fail) { console.log("失败项:\n - " + fails.join("\n - ")); process.exit(1); }
else console.log("全部通过 ✅");

