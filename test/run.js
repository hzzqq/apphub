/*
 * App Hub 大厅逻辑自测（零依赖，仅用 Node 内置 vm/fs）。
 * 从 index.html 抽取 validateBackup 函数源码后断言 —— 只取该函数而不加载整页脚本，
 * 避免大厅顶层代码对 DOM/localStorage 的重依赖，测试更轻更稳。
 * 运行：node test/run.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const html = fs.readFileSync(path.resolve(__dirname, "..", "index.html"), "utf8");
const m = html.match(/function validateBackup\(payload\)\{[\s\S]*?\n\}/);
if (!m) throw new Error("index.html 中未找到 validateBackup");

const m2 = html.match(/function formatDataStatus\(j\)\{[\s\S]*?\n\}/);
if (!m2) throw new Error("index.html 中未找到 formatDataStatus");

const sandbox = { console, URLSearchParams };
vm.createContext(sandbox);
const validateBackup = vm.runInContext(m[0] + "\n;validateBackup", sandbox);
const formatDataStatus = vm.runInContext(m2[0] + "\n;formatDataStatus", sandbox);

let pass = 0, fail = 0;
const failed = [];
function ok(desc, cond) {
  if (cond) { pass++; console.log("  ✓ " + desc); }
  else { fail++; failed.push(desc); console.log("  ✗ " + desc); }
}

/* ============================================================
 *  Round 1: 备份文件校验（防损坏 / 防恶意备份写入 localStorage）
 * ============================================================ */
console.log("[Round 1] 备份校验 validateBackup");

const good = { format: "apphub-backup", version: 1, data: { hub_fav: "[]", theme_config: "{}" } };
const r = validateBackup(good);
ok("合法备份通过", r.ok === true);
ok("返回键列表", Array.isArray(r.keys) && r.keys.length === 2);
ok("统计字节大小", typeof r.size === "number" && r.size > 0);

ok("null 被拒绝", validateBackup(null).ok === false);
ok("undefined 被拒绝", validateBackup(undefined).ok === false);
ok("数组 payload 被拒绝", validateBackup([]).ok === false);
ok("缺 format 标记被拒绝", validateBackup({ data: { a: "1" } }).ok === false);
ok("data 为数组被拒绝", validateBackup({ format: "apphub-backup", data: ["x"] }).ok === false);
ok("data 为空被拒绝", validateBackup({ format: "apphub-backup", data: {} }).ok === false);
ok("缺 data 被拒绝", validateBackup({ format: "apphub-backup" }).ok === false);

ok("键名含尖括号被拒绝", validateBackup({ format: "apphub-backup", data: { "<script>": "x" } }).ok === false);
ok("键名含空格被拒绝", validateBackup({ format: "apphub-backup", data: { "a b": "1" } }).ok === false);
ok("键名含引号被拒绝", validateBackup({ format: "apphub-backup", data: { "a\"b": "1" } }).ok === false);
ok("超长键名(>64)被拒绝", validateBackup({ format: "apphub-backup", data: { ["k".repeat(65)]: "1" } }).ok === false);

ok("数字值被拒绝", validateBackup({ format: "apphub-backup", data: { a: 1 } }).ok === false);
ok("null 值被拒绝", validateBackup({ format: "apphub-backup", data: { a: null } }).ok === false);
ok("对象值被拒绝", validateBackup({ format: "apphub-backup", data: { a: {} } }).ok === false);

const big = { format: "apphub-backup", data: { big: "x".repeat(9 * 1024 * 1024) } };
ok("超过 8MB 被拒绝", validateBackup(big).ok === false);

ok("键名允许点/冒号/下划线/连字符", validateBackup({ format: "apphub-backup", data: { "a.b:c_d-e": "1" } }).ok === true);
ok("值含 HTML 仍按字符串通过(由各 App 的 esc 负责转义)",
  validateBackup({ format: "apphub-backup", data: { note: "<img onerror=1>" } }).ok === true);

/* ============================================================
 *  Round 2: 数据新鲜度文案（大厅展示 /api/data_status 结论）
 * ============================================================ */
console.log("\n[Round 2] 数据新鲜度文案 formatDataStatus");

ok("无效响应返回空文案", formatDataStatus(null).text === "");
ok("ok=false 返回空文案", formatDataStatus({ ok: false, count: 10 }).text === "");
ok("count=0 返回空文案", formatDataStatus({ ok: true, count: 0 }).text === "");

const fresh = formatDataStatus({ ok: true, count: 55, with_data: 55, newest_age_days: 1, avg_age_days: 1.1, stale_count: 0 });
ok("含品种数与最新天数", fresh.text.indexOf("55 个品种") >= 0 && fresh.text.indexOf("最新 1 天前") >= 0);
ok("含平均滞后天数", fresh.text.indexOf("平均 1.1 天") >= 0);
ok("无滞后时不显示警告", fresh.text.indexOf("滞后") < 0);
ok("新鲜数据标记为 ok(绿)", fresh.cls === "ok");

const lagged = formatDataStatus({ ok: true, count: 55, with_data: 55, newest_age_days: 9, avg_age_days: 12.4, stale_count: 3 });
ok("有滞后显示警告数", lagged.text.indexOf("⚠ 3 个滞后") >= 0);
ok("有滞后标记为 bad(红)", lagged.cls === "bad");

const mid = formatDataStatus({ ok: true, count: 55, with_data: 55, newest_age_days: 10, avg_age_days: 11, stale_count: 0 });
ok("最新>7天但无滞后 -> 中性", mid.cls === "");

ok("无数据日期时提示", formatDataStatus({ ok: true, count: 55, with_data: 0 }).text.indexOf("暂无数据日期") >= 0);
ok("缺字段不崩溃(可选字段缺失仍出文案)", (() => {
  try { return formatDataStatus({ ok: true, count: 5, with_data: 5 }).text.indexOf("5 个品种") >= 0; }
  catch (e) { return false; }
})());

/* ============================================================
 *  Round 3: 后端依赖标注（哪些 App 必须连后端才有真实数据）
 * ============================================================ */
const m3 = html.match(/const NEEDS_BACKEND = \[[\s\S]*?\];/);
const m4 = html.match(/function needsBackend\(dir\)\{[^}]*?\}/);
const m5 = html.match(/function backendBadgeText\(up\)\{[^}]*?\}/);
const m7 = html.match(/const APP_ENDPOINTS = \{[\s\S]*?\};/);
if (!m3 || !m4 || !m5 || !m7) throw new Error("index.html 中未找到后端依赖标注相关定义");
const napi = vm.runInContext(
  m3[0] + "\n" + m4[0] + "\n" + m5[0] + "\n" + m7[0] +
  "\n;({ needsBackend: needsBackend, backendBadgeText: backendBadgeText, NEEDS_BACKEND: NEEDS_BACKEND, APP_ENDPOINTS: APP_ENDPOINTS })",
  sandbox
);

console.log("\n[Round 3] 后端依赖标注 needsBackend");
ok("期库镜需后端", napi.needsBackend("futures-inventory") === true);
ok("价差望远镜需后端", napi.needsBackend("futures-spread") === true);
ok("ETF 精选器需后端", napi.needsBackend("etf-picker") === true);
ok("产业链联动需后端", napi.needsBackend("futures-chain") === true);
ok("AI 投研问答需后端", napi.needsBackend("market-qa") === true);
ok("交易大师需后端", napi.needsBackend("trader-avatars") === true);
ok("桌面宠物不需后端", napi.needsBackend("desktop-pet") === false);
ok("番茄钟不需后端", napi.needsBackend("focus-timer") === false);
ok("未知目录返回 false", napi.needsBackend("no-such-app") === false);
ok("依赖清单含 36 个 App", napi.NEEDS_BACKEND.length === 36);
ok("依赖清单无重复", new Set(napi.NEEDS_BACKEND).size === napi.NEEDS_BACKEND.length);
ok("已连后端 -> 真实数据徽标", napi.backendBadgeText(true) === "🔌 真实数据");
ok("未连后端 -> 本地样本徽标", napi.backendBadgeText(false) === "⚠ 本地样本");

/* 提前注入 R70/R71/R72 纯函数到沙箱：paletteFilter 运行时依赖 semanticMatch，须在 Round 10 调用前就绪 */
const mR70 = html.match(/function paletteAppNeed\(dir, backendUp\)\{[\s\S]*?\n\}/);
const mR71 = html.match(/function semanticMatch\(q, dir\)\{[\s\S]*?\n\}/);
const mR72 = html.match(/function dataStatTarget\(\)\{[\s\S]*?\n\}/);
const mEP  = html.match(/const APP_ENDPOINTS = \{[\s\S]*?\};/);
const mEPD = html.match(/const EP_DESC = \{[\s\S]*?\n\};/);
const mR73 = html.match(/function endpointMatch\(q, dir\)\{[\s\S]*?\n\}/);
const mR75 = html.match(/function defaultAppDirs\(recentArr, favArr\)\{[\s\S]*?\n\}/);
if (!mR70 || !mR71 || !mR72 || !mEP || !mEPD || !mR73 || !mR75) throw new Error("index.html 中未找到 paletteAppNeed/semanticMatch/dataStatTarget/endpointMatch/defaultAppDirs/APP_ENDPOINTS/EP_DESC");
const paletteAppNeed = vm.runInContext(mR70[0] + "\n;paletteAppNeed", sandbox);
const semanticMatch  = vm.runInContext(mR71[0] + "\n;semanticMatch", sandbox);
const dataStatTarget = vm.runInContext(mR72[0] + "\n;dataStatTarget", sandbox);
const endpointMatch  = vm.runInContext(mEPD[0] + "\n" + mR73[0] + "\n;endpointMatch", sandbox);
const defaultAppDirs = vm.runInContext(mR75[0] + "\n;defaultAppDirs", sandbox);
const mR77a = html.match(/function levenshtein\(a, b\)\{[\s\S]*?\n\}/);
const mR77b = html.match(/function nearTokens\(q, text, maxDist\)\{[\s\S]*?\n\}/);
const mR77c = html.match(/function recencyBoost\(dir, rec, fav\)\{[\s\S]*?\n\}/);
if (!mR77a || !mR77b || !mR77c) throw new Error("index.html 中未找到 levenshtein/nearTokens/recencyBoost");
const R77 = vm.runInContext(mR77a[0] + "\n" + mR77b[0] + "\n" + mR77c[0] + "\n;({levenshtein:levenshtein, nearTokens:nearTokens, recencyBoost:recencyBoost})", sandbox);
const levenshtein = R77.levenshtein, nearTokens = R77.nearTokens, recencyBoost = R77.recencyBoost;
const mR78a = html.match(/const PINYIN_RAW = "([^"]*)";/);
const mR78b = html.match(/var PINYIN_MAP = \(function\(\)\{[\s\S]*?\}\)\(\);/);
const mR78c = html.match(/function pinyinKey\(text\)\{[\s\S]*?\n\}/);
const mR78d = html.match(/function pinyinHit\(q, text\)\{[\s\S]*?\n\}/);
if (!mR78a || !mR78b || !mR78c || !mR78d) throw new Error("index.html 中未找到 PINYIN_RAW/PINYIN_MAP/pinyinKey/pinyinHit");
const R78 = vm.runInContext(mR78a[0] + "\n" + mR78b[0] + "\n" + mR78c[0] + "\n" + mR78d[0] + "\n;({pinyinKey:pinyinKey, pinyinHit:pinyinHit})", sandbox);
const pinyinKey = R78.pinyinKey, pinyinHit = R78.pinyinHit;
/* R75 测试桩：注入最近/收藏数据，使空查询个性化默认列表可确定性验证 */
sandbox.getRecent = function(){ return ["etf-picker","futures-board"]; };
sandbox.getFav = function(){ return ["futures-inventory"]; };

console.log("\n[Round 3b] 端点映射 APP_ENDPOINTS 覆盖性（R52 弹窗数据源）");
ok("存在 APP_ENDPOINTS 端点映射对象", napi.APP_ENDPOINTS && typeof napi.APP_ENDPOINTS === "object");
ok("端点映射覆盖全部 36 个后端 App", Object.keys(napi.APP_ENDPOINTS).length === napi.NEEDS_BACKEND.length);
ok("每个后端 App 都列出非空端点清单", napi.NEEDS_BACKEND.every(function(d){
  return Array.isArray(napi.APP_ENDPOINTS[d]) && napi.APP_ENDPOINTS[d].length > 0;
}));
ok("期库镜列出 7 个端点", (napi.APP_ENDPOINTS["futures-inventory"] || []).length === 7);
ok("交易大师仅 /api/llm", JSON.stringify(napi.APP_ENDPOINTS["trader-avatars"]) === JSON.stringify(["/api/llm"]));

console.log("\n[Round 3c] 端点弹窗复制按钮（R53）");
ok("index.html 含 copyEndpoint 复制函数", /function copyEndpoint\(/.test(html));
ok("弹窗列表项含 epcopy 复制按钮", /class="epcopy"/.test(html));

console.log("\n[Round 3d] 端点弹窗复制后端地址按钮（R54）");
ok("index.html 含 copyBackendAddr 复制函数", /function copyBackendAddr\(/.test(html));
ok("弹窗含「复制地址」按钮", /复制地址/.test(html));

console.log("\n[Round 3e] 端点弹窗复制全部端点按钮（R55）");
ok("index.html 含 copyAllEndpoints 复制函数", /function copyAllEndpoints\(/.test(html));
ok("弹窗含「复制全部端点」按钮", /复制全部端点/.test(html));

console.log("\n[Round 3f] 数据新鲜度小标（R59）");
ok("index.html 含 FRESH_EPS 期货缓存端点集", /const FRESH_EPS/.test(html));
ok("index.html 含 isFreshApp 判定", /function isFreshApp\(/.test(html));
ok("index.html 含 updateFreshnessBadges 函数", /function updateFreshnessBadges\(/.test(html));
ok("卡片模板含 freshpill 占位", /class="freshpill" id="fresh-/.test(html));

/* ============================================================
 *  Round 4: openApp 参数兼容（防同名函数覆盖导致键盘打开失效的回归）
 * ============================================================ */
const m6 = html.match(/function parseOpenArgs\(a, b\)\{[\s\S]*?\n\}/);
if (!m6) throw new Error("index.html 中未找到 parseOpenArgs");
const parseOpenArgs = vm.runInContext(m6[0] + "\n;parseOpenArgs", sandbox);

console.log("\n[Round 4] openApp 参数兼容 parseOpenArgs");
ok("(event, dir) 形式解析出 ev 与 dir", (() => {
  const r = parseOpenArgs({ type: "click" }, "futures-inventory");
  return r.dir === "futures-inventory" && r.ev && r.ev.type === "click";
})());
ok("(dir) 形式 ev 为 null", (() => {
  const r = parseOpenArgs("futures-inventory");
  return r.dir === "futures-inventory" && r.ev === null;
})());
ok("(dir, undefined) 仍按单参处理", parseOpenArgs("etf-picker", undefined).dir === "etf-picker");
ok("缺 dir 时返回 undefined 供调用方拦截", parseOpenArgs(undefined).dir === undefined);
// 关键回归防线: 曾因重复定义 openApp 导致键盘 Enter 打开应用失效
ok("index.html 中 openApp 只定义一次", (html.match(/function openApp\(/g) || []).length === 1);

/* ============================================================
 *  Round 5: 命令面板模糊匹配（R62）
 * ============================================================ */
const m8 = html.match(/function fuzzyScore\(q, text\)\{[\s\S]*?\n\}/);
const m9 = html.match(/function paletteFilter\(q, list\)\{[\s\S]*?\n\}/);
if (!m8) throw new Error("index.html 中未找到 fuzzyScore");
if (!m9) throw new Error("index.html 中未找到 paletteFilter");
// paletteFilter 内部引用 CAT_LABEL（仅打分用），测试沙箱需提供，避免 ReferenceError
sandbox.CAT_LABEL = { fin:"金融", life:"生活", tool:"效率", fav:"收藏" };
const fuzzyScore = vm.runInContext(m8[0] + "\n;fuzzyScore", sandbox);
const paletteFilter = vm.runInContext(m9[0] + "\n;paletteFilter", sandbox);

const MOCK = [
  { dir:"futures-board", name:"期货看板", ico:"📈", cat:"fin", tag:"期货盯盘", desc:"期货实时行情与持仓" },
  { dir:"futures-inventory", name:"期库镜", ico:"🗄", cat:"fin", tag:"库存", desc:"期货库存透视" },
  { dir:"etf-picker", name:"ETF 选基", ico:"🧺", cat:"fin", tag:"ETF", desc:"ETF 筛选" },
  { dir:"pet-diary", name:"宠物日记", ico:"🐾", cat:"life", tag:"宠物", desc:"记录宠物日常" },
  { dir:"todo-list", name:"待办清单", ico:"✅", cat:"tool", tag:"效率", desc:"任务管理" },
];

console.log("\n[Round 5] 命令面板模糊匹配 paletteFilter / fuzzyScore (R62)");
ok("fuzzyScore 前缀匹配得分高于无关项", fuzzyScore("期货","期货看板") > fuzzyScore("期货","宠物日记"));
ok("fuzzyScore 命中>0 且未命中=0", fuzzyScore("etf","ETF 选基") > 0 && fuzzyScore("zzz","ETF 选基") === 0);
ok("paletteFilter 空查询返回个性化最近+收藏列表（非全部）", (() => {
  const r = paletteFilter("", MOCK);
  const dirs = r.map(x => x.dir).filter(Boolean);
  // R75：空查询应只列「最近打开 + 收藏」中真实存在的 App，而非全部 MOCK
  return dirs.length > 0 && dirs.length < MOCK.length && dirs.indexOf("etf-picker") >= 0;
})());
ok("paletteFilter('etf') 把 ETF 选基排第一", (() => {
  const r = paletteFilter("etf", MOCK);
  return r.length > 0 && r[0].dir === "etf-picker";
})());
ok("paletteFilter('期货') 优先命中期货类应用", (() => {
  const r = paletteFilter("期货", MOCK);
  return r[0].dir === "futures-board" || r[0].dir === "futures-inventory";
})());
ok("paletteFilter('随机') 命中快捷操作项", (() => {
  const r = paletteFilter("随机", MOCK);
  return r.some(x => x.type === "act");
})());
ok("paletteFilter 结果上限 8 条", (() => {
  const big = [];
  for (let i=0;i<40;i++) big.push({ dir:"a"+i, name:"应用"+i, ico:"•", cat:"tool", tag:"t", desc:"d" });
  return paletteFilter("", big).length <= 8;
})());

/* ============================================================
 *  Round 6: 键盘快捷键帮助（R63）
 * ============================================================ */
const m10 = html.match(/function helpShortcuts\(\)\{[\s\S]*?\n\}/);
if (!m10) throw new Error("index.html 中未找到 helpShortcuts");
const helpShortcuts = vm.runInContext(m10[0] + "\n;helpShortcuts", sandbox);

console.log("\n[Round 6] 键盘快捷键帮助 helpShortcuts (R63)");
const HS = helpShortcuts();
ok("helpShortcuts 返回非空数组", Array.isArray(HS) && HS.length >= 5);
ok("helpShortcuts 含 ? 打开帮助条目", HS.some(s => s.key.indexOf("?") >= 0));
ok("helpShortcuts 含命令面板(Ctrl/Cmd+K)条目", HS.some(s => /Ctrl|Cmd/.test(s.key)));
ok("helpShortcuts 含搜索框聚焦(/)条目", HS.some(s => s.key.indexOf("/") >= 0));
ok("helpShortcuts 每条含 key 与 desc", HS.every(s => typeof s.key === "string" && typeof s.desc === "string" && s.key && s.desc));

/* ============================================================
 *  Round 7: URL hash 深链解析（R64）
 * ============================================================ */
const m11 = html.match(/function parseHashDir\(hash\)\{[\s\S]*?\n\}/);
if (!m11) throw new Error("index.html 中未找到 parseHashDir");
// parseHashDir 依赖全局 APPS 做「已知目录」校验；单测沙箱注入最小 APPS 即可验证识别逻辑
sandbox.APPS = [{ dir:"futures-inventory" }, { dir:"etf-picker" }];
const parseHashDir = vm.runInContext(m11[0] + "\n;parseHashDir", sandbox);

console.log("\n[Round 7] URL hash 深链解析 parseHashDir (R64)");
ok("parseHashDir('#futures-inventory') 解析出目录", parseHashDir("#futures-inventory") === "futures-inventory");
ok("parseHashDir('#/futures-inventory') 兼容斜杠前缀", parseHashDir("#/futures-inventory") === "futures-inventory");
ok("parseHashDir('#') 空 hash 返回 null", parseHashDir("#") === null);
ok("parseHashDir('') 无 hash 返回 null", parseHashDir("") === null);
ok("parseHashDir('#nope') 未知目录返回 null", parseHashDir("#nope") === null);

/* ============================================================
 *  Round 8: 使用计数「常用」排序（R65）
 * ============================================================ */
const m12 = html.match(/function sortByCount\(list, counts\)\{[\s\S]*?\n\}/);
if (!m12) throw new Error("index.html 中未找到 sortByCount");
const sortByCount = vm.runInContext(m12[0] + "\n;sortByCount", sandbox);

console.log("\n[Round 8] 使用计数排序 sortByCount (R65)");
const SL = [
  { dir:"a", name:"阿" }, { dir:"b", name:"波" }, { dir:"c", name:"次" },
];
ok("无计数时退化为按名称升序", (() => {
  const r = sortByCount(SL, {});
  return r.map(x => x.dir).join(",") === "a,b,c";
})());
ok("计数高者排在最前", (() => {
  const r = sortByCount(SL, { b:5, a:1, c:2 });
  return r[0].dir === "b";
})());
ok("次数相同按名称升序", (() => {
  const r = sortByCount(SL, { a:3, c:3, b:3 });
  return r.map(x => x.dir).join(",") === "a,b,c";
})());
ok("不修改原数组（纯函数）", (() => {
  const before = SL.map(x => x.dir).join(",");
  sortByCount(SL, { b:9 });
  return SL.map(x => x.dir).join(",") === before;
})());

/* ============================================================
 *  Round 9: 帮助 ↔ 命令面板 交叉跳转（R66，数据驱动）
 * ============================================================ */
const m13 = html.match(/function crossLinks\(\)\{[\s\S]*?\n\}/);
if (!m13) throw new Error("index.html 中未找到 crossLinks");
const crossLinks = vm.runInContext(m13[0] + "\n;crossLinks", sandbox);

console.log("\n[Round 9] 帮助↔命令面板交叉跳转 crossLinks (R66)");
const CL = crossLinks();
ok("crossLinks 返回两条交叉跳转", CL.length === 2);
ok("含 help→palette 跳转", CL.some(c => c.from === "help" && c.to === "palette" && c.label));
ok("含 palette→help 跳转", CL.some(c => c.from === "palette" && c.to === "help" && c.label));
ok("每条跳转 label 非空", CL.every(c => typeof c.label === "string" && c.label.trim()));

/* ============================================================
 *  Round 10: 搜索 ↔ 命令面板 联动（R67）
 * ============================================================ */
console.log("\n[Round 10] 搜索↔面板联动 paletteFilter (R67)");
ok("paletteFilter('etf') 含「在列表中筛选」快捷项", (() => {
  const r = paletteFilter("etf", MOCK);
  return r.some(x => x.type === "act" && x.nm.indexOf("筛选") >= 0);
})());
ok("筛选快捷项置于末尾(低分-1不抢占应用排序)", (() => {
  const r = paletteFilter("etf", MOCK);
  const idx = r.findIndex(x => x.type === "act" && x.nm.indexOf("筛选") >= 0);
  return idx >= 0 && idx === r.length - 1;
})());
ok("空查询不含筛选快捷项(避免干扰)", paletteFilter("", MOCK).every(x => x.nm.indexOf("筛选") < 0));

/* ============================================================
 *  Round 11: 收藏快捷区数据驱动 favBarItems（R68）
 * ============================================================ */
const m14 = html.match(/function favBarItems\(favArr\)\{[\s\S]*?\n\}/);
if (!m14) throw new Error("index.html 中未找到 favBarItems");
const favBarItems = vm.runInContext(m14[0] + "\n;favBarItems", sandbox);

console.log("\n[Round 11] 收藏快捷区 favBarItems (R68)");
ok("favBarItems 已知目录解析出 dir", favBarItems(["futures-inventory","etf-picker"])[0].dir === "futures-inventory");
ok("favBarItems 未知目录回退为 dir 本身", (() => {
  const r = favBarItems(["zzz-unknown"]);
  return r.length === 1 && r[0].dir === "zzz-unknown" && r[0].ico === "•" && r[0].name === "zzz-unknown";
})());
ok("favBarItems 空数组返回空", favBarItems([]).length === 0);

/* ============================================================
 *  Round 12: 真实数据概览 dataStatText（R69，纯函数）
 * ============================================================ */
const m15 = html.match(/function dataStatText\(backendUp, n\)\{[\s\S]*?\n\}/);
if (!m15) throw new Error("index.html 中未找到 dataStatText");
const dataStatText = vm.runInContext(m15[0] + "\n;dataStatText", sandbox);

console.log("\n[Round 12] 真实数据概览 dataStatText (R69)");
ok("dataStatText 后端连通 → n=全量且文案含'已接入'", (() => {
  const s = dataStatText(true, 36);
  return s.n === 36 && /已接入实时数据/.test(s.text);
})());
ok("dataStatText 后端未连 → n=0 且文案含'待连后端'", (() => {
  const s = dataStatText(false, 36);
  return s.n === 0 && /待连后端/.test(s.text);
})());
ok("dataStatText 个数随入参变化", dataStatText(true, 10).n === 10 && dataStatText(false, 10).n === 0);

/* ============================================================
 *  Round 13: 命令面板真实数据标识 paletteAppNeed（R70，纯函数）
 * ============================================================ */
console.log("\n[Round 13] 面板真实数据标识 paletteAppNeed (R70)");
ok("后端 App + 已连 → 真实数据", (() => {
  const r = paletteAppNeed("futures-board", true);
  return r.need === true && r.text === "🔌 真实数据";
})());
ok("后端 App + 未连 → 本地样本", (() => {
  const r = paletteAppNeed("futures-board", false);
  return r.need === true && r.text === "⚠ 本地样本";
})());
ok("纯前端 App → 本地运行（need=false）", (() => {
  const r = paletteAppNeed("todo-list", true);
  return r.need === false && r.text === "🖥 本地运行";
})());

/* ============================================================
 *  Round 14: 语义搜索 semanticMatch（R71，纯函数）
 * ============================================================ */
console.log("\n[Round 14] 语义搜索 semanticMatch (R71)");
ok("'真实数据' 命中后端 App", semanticMatch("真实数据", "futures-board") === true);
ok("'后端' 命中后端 App", semanticMatch("后端", "etf-picker") === true);
ok("'在线' 命中后端 App", semanticMatch("在线", "market-mood") === true);
ok("'api' 命中后端 App（大小写无关）", semanticMatch("API", "quote-board") === true);
ok("'本地' 命中纯前端 App", semanticMatch("本地", "todo-list") === true);
ok("'真实数据' 不命中纯前端 App", semanticMatch("真实数据", "todo-list") === false);
ok("'本地' 不命中后端 App", semanticMatch("本地", "futures-board") === false);
ok("空查询不误命中", semanticMatch("", "futures-board") === false);
ok("无关词不误命中", semanticMatch("宠物", "futures-board") === false);

/* ============================================================
 *  Round 15: hero 实时数据 chip 直达 dataStatTarget（R72，纯函数）
 * ============================================================ */
console.log("\n[Round 15] hero chip 直达 dataStatTarget (R72)");
ok("dataStatTarget 指向 data-status-dash", dataStatTarget() === "data-status-dash");

/* ============================================================
 *  Round 16: 端点反查搜索 endpointMatch（R73，纯函数）
 * ============================================================ */
console.log("\n[Round 16] 端点反查搜索 endpointMatch (R73)");
ok("'/api/etf' 命中 etf-picker", endpointMatch("/api/etf", "etf-picker") === true);
ok("'etf' 命中 etf-picker", endpointMatch("etf", "etf-picker") === true);
ok("'corr' 命中 corr-explorer（端点路径）", endpointMatch("corr", "corr-explorer") === true);
ok("'相关性' 命中 corr-explorer（端点说明）", endpointMatch("相关性", "corr-explorer") === true);
ok("'refresh' 命中 inv-refresh", endpointMatch("refresh", "inv-refresh") === true);
ok("'etf' 不命中纯前端 todo-list", endpointMatch("etf", "todo-list") === false);
ok("后端 App 但无关端点不误命中", endpointMatch("zzz-nope", "etf-picker") === false);
ok("空查询不误命中", endpointMatch("", "etf-picker") === false);

/* ============================================================
 *  Round 17: 空查询个性化默认列表 defaultAppDirs（R75，纯函数）
 * ============================================================ */
console.log("\n[Round 17] 空查询个性化默认 defaultAppDirs (R75)");
ok("最近置前、收藏去重追加", JSON.stringify(defaultAppDirs(["a","b"],["b","c"])) === JSON.stringify(["a","b","c"]));
ok("空输入返回空", defaultAppDirs([],[]).length === 0);
ok("容错非数组输入", defaultAppDirs(null, undefined).length === 0);

/* ============================================================
 *  Round 18: 可分享筛选视图深链 parseHashView / buildViewHash（R76，纯函数）
 * ============================================================ */
const mVars = html.match(/var VIEW_CATS = \[[^\]]*\];\n\s*var VIEW_SORTS = \[[^\]]*\];\n\s*var VIEW_VIEWS = \[[^\]]*\];/);
const mR76a = html.match(/function parseHashView\(hash\)\{[\s\S]*?\n\}/);
const mR76b = html.match(/function buildViewHash\(st\)\{[\s\S]*?\n\}/);
if (!mVars || !mR76a || !mR76b) throw new Error("index.html 中未找到 parseHashView/buildViewHash/VIEW_* 常量");
const R76 = vm.runInContext(mVars[0] + "\n" + mR76a[0] + "\n" + mR76b[0] + "\n;({parseHashView:parseHashView, buildViewHash:buildViewHash})", sandbox);
const parseHashView = R76.parseHashView, buildViewHash = R76.buildViewHash;

console.log("\n[Round 18] 可分享筛选视图深链 (R76)");
ok("全参数视图链接解析完整", (() => { var v = parseHashView("#view?cat=fin&q=etf&sort=count&view=list"); return v && v.cat==="fin" && v.q==="etf" && v.sort==="count" && v.view==="list"; })());
ok("部分参数视图链接解析", JSON.stringify(parseHashView("#view?cat=fin")) === JSON.stringify({cat:"fin"}));
ok("识别斜杠前缀 #/view", JSON.stringify(parseHashView("#/view?cat=tool&sort=name")) === JSON.stringify({cat:"tool",sort:"name"}));
ok("非法 cat 返回 null", parseHashView("#view?cat=bogus") === null);
ok("非法 sort 且无有效参数返回 null", parseHashView("#view?sort=bogus") === null);
ok("非法 view 仅保留合法部分", JSON.stringify(parseHashView("#view?cat=fin&view=bogus")) === JSON.stringify({cat:"fin"}));
ok("纯 'view' 无参数返回 null", parseHashView("#view") === null);
ok("'viewxyz' 非合法视图返回 null", parseHashView("#viewxyz") === null);
ok("与 R64 #dir 深链不冲突（返回 null）", parseHashView("#futures-inventory") === null);
ok("空 hash 返回 null", parseHashView("") === null);
ok("中文 q 正常解析", parseHashView("#view?q=你好").q === "你好");
ok("build→parse 往返一致", (() => { var b = parseHashView(buildViewHash({cat:"fin",q:"etf",sort:"count",view:"list"})); return b && b.cat==="fin" && b.q==="etf" && b.sort==="count" && b.view==="list"; })());
ok("buildViewHash 编码特殊字符", buildViewHash({q:"a b&c"}).indexOf("q=") >= 0 && buildViewHash({q:"a b&c"}).indexOf("&") === buildViewHash({q:"a b&c"}).lastIndexOf("&"));

/* ============================================================
 *  Round 19: 搜索相关性升级 levenshtein / nearTokens / recencyBoost（R77，纯函数）
 *  注：三个函数已在 Round 3b 前的早期注入块编译进 sandbox（供 paletteFilter 调用），此处直接断言。
 * ============================================================ */
console.log("\n[Round 19] 搜索相关性升级 (R77)");
ok("levenshtein 换位距离=1", levenshtein("etf","eft") === 1);
ok("levenshtein 经典 kitten/sitting=3", levenshtein("kitten","sitting") === 3);
ok("levenshtein 空串退化为长度", levenshtein("","abc") === 3 && levenshtein("abc","") === 3);
ok("levenshtein 相同串=0", levenshtein("etf","etf") === 0);
ok("nearTokens 错别字 'eft' 命中 'ETF picker'", nearTokens("eft","ETF picker",1) > 0);
ok("nearTokens 中文错位 '欺货' 命中 '期货'", nearTokens("欺货","期货行情",1) > 0);
ok("nearTokens 精确子串不算近邻（返回0）", nearTokens("etf","ETF picker",1) === 0);
ok("nearTokens 无关词返回0", nearTokens("zzz","ETF picker",1) === 0);
ok("recencyBoost 最近打开加分", recencyBoost("a",["a","b"],["c"]) > 0);
ok("recencyBoost 收藏加分", recencyBoost("a",["b"],["a"]) > 0);
ok("recencyBoost 越近加权越高", recencyBoost("a",["a","b"],[]) > recencyBoost("b",["a","b"],[]));
ok("recencyBoost 无关项返回0", recencyBoost("x",["b"],["c"]) === 0);

/* ============================================================
 *  Round 20: 拼音首字母搜索 pinyinKey / pinyinHit（R78，纯函数）
 *  注：PINYIN_RAW/PINYIN_MAP/pinyinKey/pinyinHit 已在早期注入块编译进 sandbox（供 paletteFilter/grid 调用）。
 * ============================================================ */
console.log("\n[Round 20] 拼音首字母搜索 (R78)");
ok("pinyinKey('期货') === 'qh'", pinyinKey("期货") === "qh");
ok("pinyinKey('期货ETF') === 'qhetf'", pinyinKey("期货ETF") === "qhetf");
ok("pinyinKey('ETF-123') === 'etf-123'（英文/数字原样）", pinyinKey("ETF-123") === "etf-123");
ok("pinyinHit('qh','期货行情') 命中（拼音→中文）", pinyinHit("qh","期货行情") === true);
ok("pinyinHit('gp','股票') 命中（词表内 股票→gp）", pinyinHit("gp","股票") === true);
ok("pinyinHit('etf','ETF') 命中（英文原样）", pinyinHit("etf","ETF") === true);
ok("pinyinHit('xyz','期货') 不误命中", pinyinHit("xyz","期货") === false);
ok("pinyinHit 拼音首字母也容错('qj'→'qh')", pinyinHit("qj","期货行情") === true);

/* ============================================================
 *  Round 21: 实时端点覆盖解析 parseDataStatus（R79，纯函数）
 * ============================================================ */
const mR79 = html.match(/function parseDataStatus\(j\)\{[\s\S]*?\n\}/);
if (!mR79) throw new Error("index.html 中未找到 parseDataStatus");
const parseDataStatus = vm.runInContext(mR79[0] + "\n;parseDataStatus", sandbox);

console.log("\n[Round 21] 实时端点覆盖解析 parseDataStatus (R79)");
ok("全量在线解析", (() => { var v = parseDataStatus({count:36, with_data:36, stale_count:0, ok:true});
  return v.total===36 && v.withData===36 && v.stale===0 && v.ok===true; })());
ok("部分在线解析", (() => { var v = parseDataStatus({count:36, with_data:30, stale_count:2, ok:false});
  return v.total===36 && v.withData===30 && v.stale===2 && v.ok===false; })());
ok("空对象安全默认", (() => { var v = parseDataStatus({});
  return v.total===0 && v.withData===0 && v.stale===0 && v.ok===false; })());
ok("无 count 时回退 items 长度", (() => { var v = parseDataStatus({items:[{ok:true},{ok:false}]});
  return v.total===2 && v.withData===1; })());

/* ---------- 汇总 ---------- */
console.log(`\n汇总：通过 ${pass} / 失败 ${fail}`);
if (fail) { console.log("失败项：" + failed.join("; ")); process.exit(1); }
