/* 逻辑自测（复用 tools/test-scaffold.js 共享脚手架：DOM 桩 + vm 加载）*/
const { loadApp } = require("../../tools/test-scaffold.js");
const { sandbox, src, err, doc, window, localStorage } = loadApp(__dirname);

let pass = 0, fail = 0;
const fails = [];
function ok(cond, msg) { if (cond) pass++; else { fail++; fails.push(msg); } }
function eq(a, b, msg) { ok(a === b, msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`); }

// ============================================================
// 1. esc 转义
// ============================================================
eq(sandbox.esc("<b>&'\""), "&lt;b&gt;&amp;&#39;&quot;", "esc 转义 < > & ' \"");
eq(sandbox.esc(null), "", "esc(null) => ''");
eq(sandbox.esc(123), "123", "esc(数字) => 字符串");
eq(sandbox.esc("<script>alert(1)</script>"), "&lt;script&gt;alert(1)&lt;/script&gt;", "esc 阻断 script 注入");

// ============================================================
// 2. sanitizeUserText 白名单 + 转义（属性一律去除）
// ============================================================
eq(sandbox.sanitizeUserText("<b>hi</b>"), "<b>hi</b>", "sanitize 保留 <b>");
eq(sandbox.sanitizeUserText("<i>x</i>"), "<i>x</i>", "sanitize 保留 <i>");
eq(sandbox.sanitizeUserText("<strong>a</strong>"), "<strong>a</strong>", "sanitize 保留 <strong>");
eq(sandbox.sanitizeUserText("<script>alert(1)</script>"), "&lt;script&gt;alert(1)&lt;/script&gt;", "sanitize 拦截 script");
eq(sandbox.sanitizeUserText("<img src=x onerror=alert(1)>"), "&lt;img src=x onerror=alert(1)&gt;", "sanitize 拦截 img");
eq(sandbox.sanitizeUserText('<b onclick="x">hi</b>'), "&lt;b onclick=&quot;x&quot;&gt;hi&lt;/b&gt;", "sanitize 去除属性（变纯文本）");
eq(sandbox.sanitizeUserText("<unknown>tag</unknown>"), "&lt;unknown&gt;tag&lt;/unknown&gt;", "sanitize 非白名单标签被转义");

// ============================================================
// 3. hex 校验 / 归一化 / rgb 互转
// ============================================================
ok(sandbox.isValidHex("#abc") === true, "isValidHex(#abc)=true");
ok(sandbox.isValidHex("#abcdef") === true, "isValidHex(#abcdef)=true");
ok(sandbox.isValidHex("abc") === false, "isValidHex(abc)=false(无#)");
ok(sandbox.isValidHex("#xyz") === false, "isValidHex(#xyz)=false");
ok(sandbox.isValidHex("#12345") === false, "isValidHex(#12345)=false(长度错)");
eq(sandbox.normalizeHex("#ABC"), "#aabbcc", "normalizeHex(#ABC 3位)=#aabbcc");
eq(sandbox.normalizeHex("#abcdef"), "#abcdef", "normalizeHex 6位保持");
eq(sandbox.normalizeHex("bad"), null, "normalizeHex(bad)=null");
eq(JSON.stringify(sandbox.hexToRgb("#667eea")), JSON.stringify({ r: 102, g: 126, b: 234 }), "hexToRgb(#667eea)");
eq(sandbox.rgbToHex(102, 126, 234), "#667eea", "rgbToHex 往返");

// ============================================================
// 4. shade 明暗（带钳制）
// ============================================================
eq(sandbox.shade("#ffffff", -100), "#000000", "shade(#fff,-100)=#000");
eq(sandbox.shade("#000000", 100), "#ffffff", "shade(#000,+100)=#fff");
eq(sandbox.shade("#808080", 0), "#808080", "shade 0 不变");
eq(sandbox.shade("#ffffff", 50), "#ffffff", "shade 上溢钳制到 #fff");
eq(sandbox.shade("#000000", -50), "#000000", "shade 下溢钳制到 #000");
eq(sandbox.shade("bad", 10), "#000000", "shade 非法输入回退 #000");

// ============================================================
// 5. 相对亮度 / 对比文字色
// ============================================================
eq(sandbox.relativeLuminance("#000000"), 0, "relativeLuminance(#000)=0");
ok(sandbox.relativeLuminance("#ffffff") > 0.9, "relativeLuminance(#fff)≈1");
eq(sandbox.contrastText("#0f0f23"), "#f5f5fa", "contrastText 深色背景→浅色字");
eq(sandbox.contrastText("#ffffff"), "#111111", "contrastText 浅色背景→深色字");

// ============================================================
// 6. 智能生成 generateTheme（确定性 + 协调）
// ============================================================
const g1 = sandbox.generateTheme("#667eea", "dark");
const g2 = sandbox.generateTheme("#667eea", "dark");
eq(JSON.stringify(g1), JSON.stringify(g2), "generateTheme 同输入完全可复现");
const g3 = sandbox.generateTheme("#ff0000", "dark");
ok(JSON.stringify(g1) !== JSON.stringify(g3), "generateTheme 不同种子→不同结果");
["bg","card","card2","accent","accent2","up","down","txt","sub","line"].forEach((k) =>
  ok(sandbox.isValidHex(g1[k]), "generateTheme 输出字段 " + k + " 为合法 hex"));
eq(g1.accent, "#667eea", "generateTheme accent=归一化种子");
const gDark = sandbox.generateTheme("#3399ff", "dark");
const gLight = sandbox.generateTheme("#3399ff", "light");
ok(sandbox.relativeLuminance(gDark.bg) < sandbox.relativeLuminance(gLight.bg), "深色模式背景比浅色模式更暗");
const gDef = sandbox.generateTheme("#667eea", "weird");
eq(gDef.bg, sandbox.generateTheme("#667eea", "dark").bg, "generateTheme 非法模式回退 dark");
// 生成结果可通过校验，闭环自洽
let genOk = true; try { sandbox.validateTheme(g1); } catch (e) { genOk = false; }
ok(genOk, "generateTheme 产物可被 validateTheme 接受（闭环自洽）");

// ============================================================
// 7. validateTheme 校验 / 补全 / 截断
// ============================================================
const vMin = sandbox.validateTheme({ bg: "#0f0f23", accent: "#667eea" });
ok(sandbox.isValidHex(vMin.card) && sandbox.isValidHex(vMin.card2) && sandbox.isValidHex(vMin.txt) && sandbox.isValidHex(vMin.sub) && sandbox.isValidHex(vMin.line), "validateTheme 缺省字段已用合理默认值补齐");
eq(vMin.up, "#ff4d4f", "validateTheme 默认 up");
let threw = false; try { sandbox.validateTheme({ accent: "#667eea" }); } catch (e) { threw = true; }
ok(threw, "validateTheme 缺 bg 抛错");
threw = false; try { sandbox.validateTheme({ bg: "red", accent: "#667eea" }); } catch (e) { threw = true; }
ok(threw, "validateTheme 非法 bg 抛错");
const vShort = sandbox.validateTheme({ bg: "#abc", accent: "#def" });
eq(vShort.bg, "#aabbcc", "validateTheme 3位hex归一化");
const vName = sandbox.validateTheme({ bg: "#0f0f23", accent: "#667eea", name: "x".repeat(100) });
eq(vName.name.length, 40, "validateTheme name 截断到40");
const vKeep = sandbox.validateTheme({ bg: "#0f0f23", accent: "#667eea", up: "#123456", down: "#654321" });
eq(vKeep.up, "#123456", "validateTheme 保留提供的 up");
eq(vKeep.down, "#654321", "validateTheme 保留提供的 down");

// ============================================================
// 8. themeToCssVars / exportCss / themeToJson（含 CSS 注入防护）
// ============================================================
const cssVars = sandbox.themeToCssVars({ bg: "#0f0f23", accent: "#667eea" });
ok(cssVars.indexOf(":root{") === 0, "themeToCssVars 以 :root{ 开头");
ok(cssVars.indexOf("--bg: #0f0f23;") >= 0, "themeToCssVars 含 --bg");
ok(/\}$/.test(cssVars.trim()), "themeToCssVars 以 } 结尾");
ok(sandbox.themeToCssVars({ bg: "bad" }).indexOf("--bg: #000000;") >= 0, "themeToCssVars 非法色回退 #000000（防注入）");
const ex = sandbox.exportCss({ name: "<b>主题</b>", bg: "#0f0f23", accent: "#667eea" });
ok(ex.indexOf("/*") === 0, "exportCss 含注释头");
ok(ex.indexOf(":root{") >= 0, "exportCss 含 :root");
ok(ex.indexOf("<b>主题</b>") >= 0, "exportCss 白名单 <b> 在注释内保留（符合规范）");
const exMal = sandbox.exportCss({ name: "<script>alert(1)</script>", bg: "#0f0f23", accent: "#667eea" });
ok(exMal.indexOf("<script") < 0, "exportCss 恶意 <script> 在注释内被转义（防 XSS）");
ok(exMal.indexOf("&lt;script&gt;") >= 0, "exportCss 恶意标签以转义形式存在（不执行）");
const js = sandbox.themeToJson({ bg: "#111", card: "#222", foo: "bar" });
ok(!("foo" in js), "themeToJson 不含无关字段");

// ============================================================
// 9. 内置主题库合法性 + 全局函数存在
// ============================================================
ok(Array.isArray(sandbox.THEMES) && sandbox.THEMES.length >= 6, "THEMES 存在且不少于6个");
let allValid = true;
sandbox.THEMES.forEach((t) => {
  ["bg","card","card2","accent","accent2","up","down"].forEach((k) => { if (!sandbox.isValidHex(t[k])) allValid = false; });
});
ok(allValid, "THEMES 全部必备颜色字段均为合法 hex");
["esc","sanitizeUserText","isValidHex","normalizeHex","shade","generateTheme","randomSeed","validateTheme","themeToCssVars","exportCss","themeToJson","applyTheme","renderGrid","switchTab"].forEach((fn) =>
  ok(typeof sandbox[fn] === "function", "全局函数 " + fn + " 存在（可被测试/UIR复用）"));

// ============================================================
// 10. 随机惊喜生成（真实用户功能）
// ============================================================
ok(sandbox.isValidHex(sandbox.randomSeed()), "randomSeed 返回合法 hex");
const rndTheme = sandbox.generateTheme(sandbox.randomSeed(), "dark");
ok(rndTheme && sandbox.isValidHex(rndTheme.accent) && sandbox.isValidHex(rndTheme.bg), "randomSeed+generateTheme 产出可用主题");

// ============================================================
// 汇总
// ============================================================
console.log(`\nTheme Studio 自测: ${pass} 通过 / ${fail} 失败`);
if (fail) { console.log("失败项:\n - " + fails.join("\n - ")); process.exit(1); }
else console.log("全部通过 ✅");

