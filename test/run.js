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

const sandbox = { console };
vm.createContext(sandbox);
const validateBackup = vm.runInContext(m[0] + "\n;validateBackup", sandbox);

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

/* ---------- 汇总 ---------- */
console.log(`\n汇总：通过 ${pass} / 失败 ${fail}`);
if (fail) { console.log("失败项：" + failed.join("; ")); process.exit(1); }
