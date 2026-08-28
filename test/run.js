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

const sandbox = { console };
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
if (!m3 || !m4 || !m5) throw new Error("index.html 中未找到后端依赖标注相关定义");
const napi = vm.runInContext(
  m3[0] + "\n" + m4[0] + "\n" + m5[0] +
  "\n;({ needsBackend: needsBackend, backendBadgeText: backendBadgeText, NEEDS_BACKEND: NEEDS_BACKEND })",
  sandbox
);

console.log("\n[Round 3] 后端依赖标注 needsBackend");
ok("期库镜需后端", napi.needsBackend("futures-inventory") === true);
ok("价差望远镜需后端", napi.needsBackend("futures-spread") === true);
ok("ETF 精选器需后端", napi.needsBackend("etf-picker") === true);
ok("桌面宠物不需后端", napi.needsBackend("desktop-pet") === false);
ok("番茄钟不需后端", napi.needsBackend("focus-timer") === false);
ok("未知目录返回 false", napi.needsBackend("no-such-app") === false);
ok("依赖清单含 10 个 App", napi.NEEDS_BACKEND.length === 10);
ok("依赖清单无重复", new Set(napi.NEEDS_BACKEND).size === napi.NEEDS_BACKEND.length);
ok("已连后端 -> 真实数据徽标", napi.backendBadgeText(true) === "🔌 真实数据");
ok("未连后端 -> 本地样本徽标", napi.backendBadgeText(false) === "⚠ 本地样本");

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

/* ---------- 汇总 ---------- */
console.log(`\n汇总：通过 ${pass} / 失败 ${fail}`);
if (fail) { console.log("失败项：" + failed.join("; ")); process.exit(1); }
