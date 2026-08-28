/*
 * CodeTeacher 逻辑自测脚手架（零依赖，仅用 Node 内置 vm/fs）。
 * 加载 index.html 内联脚本到 vm 上下文，断言纯逻辑函数：
 *   tokenizeToLines / parse / explainProgram / analyze / analyzeComplexity / execute
 * 运行：node test/run.js
 */
"use strict";
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");

const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) throw new Error("index.html 中未找到 <script>");
const src = m[1];

// 不提供 window，使 initApp() 不会被自动调用（避免触碰 DOM）
const ctx = {
  console,
  setTimeout: () => 0,
  clearTimeout: () => {}
};
vm.createContext(ctx);
vm.runInContext(src, ctx); // 若脚本有语法错误，这里会抛

// ---------- 断言工具 ----------
let pass = 0, fail = 0;
const fails = [];
function ok(cond, msg) { if (cond) pass++; else { fail++; fails.push(msg); } }
function eq(a, b, msg) {
  ok(a === b, msg + ` (got ${JSON.stringify(a)} want ${JSON.stringify(b)})`);
}

// ============ 1. 词法 ============
const t1 = ctx.tokenizeToLines("x = 5\nprint(x)");
eq(t1.lines.length, 2, "词法：两行逻辑行");
eq(t1.lines[0].tokens[0].value, "x", "词法：首 token 是名字 x");
eq(t1.lines[0].tokens[1].value, "=", "词法：赋值符号 =");
eq(t1.lines[0].tokens[2].type, "num", "词法：数字 5");

// ============ 2. 语法 ============
const ast1 = ctx.parse(ctx.tokenizeToLines("x = 5\nprint(x)").lines);
eq(ast1.type, "module", "语法：module 根");
eq(ast1.body[0].type, "assign", "语法：首句是赋值");
eq(ast1.body[1].type, "expr", "语法：次句是表达式语句");

// ============ 3. 讲解生成（三模式均基于 AST，非关键字硬匹配） ============
const exPlain = ctx.explainProgram("x = 5\nprint(x)", "plain");
ok(/赋值/.test(exPlain), "讲解：plain 含赋值说明");
const exMom = ctx.explainProgram("for i in range(3):\n    print(i)", "mom");
ok(/循环|小火车|苹果/.test(exMom), "讲解：mom 含生活类比");
const exBro = ctx.explainProgram("def add(a,b):\n    return a+b", "brother");
ok(/魔法盒子|小狐狸/.test(exBro), "讲解：brother 含童趣拟人");

// 关键回归：旧 classify 对 `if x>0`（无 else）会误判 default；新版按 AST 识别 if
const exIf = ctx.explainProgram("if x>0:\n    print('pos')", "plain");
ok(/判断|条件/.test(exIf), "讲解：无 else 的 if 仍被正确识别");

// ============ 4. 错误检测：未定义变量 ============
const errSrc = "print(score)\nscore = 100";
const errAst = ctx.parse(ctx.tokenizeToLines(errSrc).lines);
const errs = ctx.findErrorsWrapper(errSrc, errAst, []);
ok(errs.some((e) => /未定义/.test(e.msg)), "纠错：检测到未定义变量 score");

// 干净代码应报告“没问题”
const cleanAst = ctx.parse(ctx.tokenizeToLines("x = 1\nprint(x)").lines);
const cleanErrs = ctx.findErrorsWrapper("x = 1\nprint(x)", cleanAst, []);
ok(cleanErrs.length === 1 && cleanErrs[0].severity === "ok", "纠错：干净代码报 ok");

// ============ 5. 错误检测：条件里写 = 而非 == ============
const eqAst = ctx.parse(ctx.tokenizeToLines("if x = 5:\n    pass").lines);
const eqErrs = ctx.findErrorsWrapper("if x = 5:\n    pass", eqAst, []);
ok(eqErrs.some((e) => /==/.test(e.msg)), "纠错：if 里写成 = 被指出应用 ==");

// ============ 6. 复杂度分析 ============
const cSingle = ctx.analyzeComplexity(ctx.parse(ctx.tokenizeToLines("for i in range(3):\n    print(i)").lines));
eq(cSingle.depth, 1, "复杂度：单层循环 depth=1");
ok(/O\(n\)/.test(cSingle.label), "复杂度：单层循环标 O(n)");

const cDouble = ctx.analyzeComplexity(ctx.parse(ctx.tokenizeToLines("for i in range(3):\n    for j in range(3):\n        print(i)").lines));
eq(cDouble.depth, 2, "复杂度：双层循环 depth=2");
ok(/O\(n²\)/.test(cDouble.label), "复杂度：双层循环标 O(n²)");

const cFlat = ctx.analyzeComplexity(ctx.parse(ctx.tokenizeToLines("x = 1\ny = 2\nprint(x)").lines));
eq(cFlat.depth, 0, "复杂度：无循环 depth=0");
ok(/O\(1\)/.test(cFlat.label), "复杂度：无循环标 O(1)");

// 递归检测
const cRec = ctx.analyzeComplexity(ctx.parse(ctx.tokenizeToLines("def f(n):\n    return f(n-1)").lines));
ok(cRec.notes.some((n) => /递归/.test(n)), "复杂度：检测到递归");

// 列表推导式应计为一次循环（旧实现会误判 O(1)）
const cComp = ctx.analyzeComplexity(ctx.parse(ctx.tokenizeToLines("squares = [x*x for x in range(3)]").lines));
ok(cComp.depth >= 1 && /O\(n\)/.test(cComp.label), "复杂度：列表推导式标 O(n)");
const cCompNest = ctx.analyzeComplexity(ctx.parse(ctx.tokenizeToLines("for i in range(3):\n    s = [x*x for x in range(3)]").lines));
ok(/O\(n²\)/.test(cCompNest.label), "复杂度：for 内套列表推导式标 O(n²)");

// ============ 7. 执行：for + print ============
const r1 = ctx.execute("for i in range(3):\n    print(i)");
eq(r1.output, "0\n1\n2", "执行：for+print 输出 0 1 2");

// ============ 8. 执行：函数定义 + 调用 + 返回值 ============
const r2 = ctx.execute("def add(a, b):\n    return a + b\nprint(add(2, 3))");
eq(r2.output, "5", "执行：函数 add(2,3) 输出 5");

// ============ 9. 执行：if/else ============
const r3 = ctx.execute("x = 10\nif x > 0:\n    print('pos')\nelse:\n    print('neg')");
eq(r3.output, "pos", "执行：if 分支命中 pos");
const r3b = ctx.execute("x = -1\nif x > 0:\n    print('pos')\nelse:\n    print('neg')");
eq(r3b.output, "neg", "执行：else 分支命中 neg");

// ============ 10. 执行：列表 + sum + 算术 ============
const r4 = ctx.execute("numbers = [1, 2, 3]\nprint(sum(numbers))");
eq(r4.output, "6", "执行：sum([1,2,3]) 输出 6");

// ============ 11. 执行：增强赋值 ============
const r5 = ctx.execute("n = 1\nn += 4\nprint(n)");
eq(r5.output, "5", "执行：n+=4 输出 5");

// ============ 12. 执行：while 循环 ============
const r6 = ctx.execute("i = 0\nwhile i < 3:\n    print(i)\n    i += 1");
eq(r6.output, "0\n1\n2", "执行：while 输出 0 1 2");

// ============ 13. 执行：字符串 / 列表运算 ============
const r7 = ctx.execute('s = "ab"\nprint(s * 3)');
eq(r7.output, "ababab", "执行：字符串乘法");
const r8 = ctx.execute("a = [1,2]\nb = [3,4]\nprint(a + b)");
eq(r8.output, "1,2,3,4", "执行：列表相加");

// ============ 14. 执行：方法（append / upper） ============
const r9 = ctx.execute("lst = []\nlst.append(1)\nlst.append(2)\nprint(lst)");
eq(r9.output, "1,2", "执行：list.append");
const r10 = ctx.execute('s = "hello"\nprint(s.upper())');
eq(r10.output, "HELLO", "执行：str.upper");

// ============ 15. 执行：未定义变量抛错（UI 会友好提示） ============
let threw = false;
try { ctx.execute("print(y)"); } catch (e) { threw = true; }
ok(threw, "执行：未定义变量抛出错误（交由 UI 兜底）");

// ============ 16. 执行：死循环防护 ============
let guardThrew = false;
try { ctx.execute("while True:\n    pass"); } catch (e) { guardThrew = /死循环/.test(e.message); }
ok(guardThrew, "执行：死循环被 STEP_CAP 拦下");

// ============ 17. 端到端 analyze 聚合 ============
const full = ctx.analyze("for i in range(5):\n    print(i)", "plain");
ok(full.explain && full.complexity && Array.isArray(full.errors), "analyze：聚合返回 explain/complexity/errors");
ok(/O\(n\)/.test(full.complexity.label), "analyze：复杂度标 O(n)");

// ============ 18. 列表推导式：解析 / 讲解 / 执行 ============
const lcAst = ctx.parse(ctx.tokenizeToLines("squares = [x*x for x in range(3)]").lines);
eq(lcAst.body[0].type, "assign", "推导式：顶层仍是赋值");
const lcExec = ctx.execute("squares = [x*x for x in range(3)]\nprint(squares)");
eq(lcExec.output, "0,1,4", "推导式：平方列表 [0,1,4]");
const lcExec2 = ctx.execute("evens = [x for x in range(6) if x % 2 == 0]\nprint(evens)");
eq(lcExec2.output, "0,2,4", "推导式：带 if 过滤 [0,2,4]");
const lcEx = ctx.explainProgram("a = [x for x in range(3)]", "plain");
ok(/列表推导式/.test(lcEx), "推导式：讲解识别列表推导式");

// ============ 19. 切片 / 负索引 ============
const slExec = ctx.execute("lst = [10,20,30,40]\nprint(lst[1:3])\nprint(lst[-1])");
eq(slExec.output, "20,30\n40", "切片/负索引：lst[1:3]=[20,30], lst[-1]=40");

// ============ 25. 执行：break / continue ============
const rb = ctx.execute("i = 0\nwhile i < 5:\n    i += 1\n    if i == 3:\n        break\n    print(i)");
eq(rb.output, "1\n2", "执行：break 跳出循环（只打印 1,2）");
const rc = ctx.execute("for i in range(5):\n    if i % 2 == 0:\n        continue\n    print(i)");
eq(rc.output, "1\n3", "执行：continue 跳过偶数（打印 1,3）");

// ============ 24. 练习自测比对 ============
const ce1 = ctx.checkExercise("0\n1\n2", "0\n1\n2");
ok(ce1.pass === true, "自测：输出一致判通过");
const ce2 = ctx.checkExercise("15", "0");
ok(ce2.pass === false, "自测：输出不一致判不通过");
const ce3 = ctx.checkExercise("yes\n", "yes");
ok(ce3.pass === true, "自测：容忍首尾空白");
const ceSol = ctx.execute("for i in range(3):\n    print(i)");
ok(ctx.checkExercise("0\n1\n2", ceSol.output).pass, "自测：正确解通过比对");

// ============ 21b. 结构检测：缺冒号 ============
const structTok = ctx.tokenizeToLines("if x > 0\n    print('pos')").lines;
const structErrs = ctx.findStructureIssues(structTok);
ok(structErrs.some(function(e){ return /冒号/.test(e.msg); }), "结构：if 缺冒号被指出");
const structOk = ctx.findStructureIssues(ctx.tokenizeToLines("if x > 0:\n    print('pos')").lines);
ok(structOk.length === 0, "结构：if 有冒号不误报");
const structFor = ctx.findStructureIssues(ctx.tokenizeToLines("for i in range(3)\n    print(i)").lines);
ok(structFor.length === 1, "结构：for 缺冒号被指出");
const structAnalyze = ctx.analyze("def add(a, b)\n    return a+b", "plain");
ok(structAnalyze.errors.some(function(e){ return /冒号/.test(e.msg); }), "结构：analyze 聚合能返回缺冒号问题");

// ============ 21. 多变量赋值 / 解包 ============
const ma = ctx.execute("a, b = 1, 2\nprint(a)\nprint(b)");
eq(ma.output, "1\n2", "多变量赋值：a=1, b=2");
const ma2 = ctx.execute("x, y = [10, 20]\nprint(x + y)");
eq(ma2.output, "30", "列表解包：x,y=[10,20] → 30");
const ma3 = ctx.execute("one, two, three = range(3)\nprint(one + two + three)");
eq(ma3.output, "3", "可迭代解包：range(3) 拆给三个变量");

// ============ 20. 运行轨迹（教学价值） ============
const tr = ctx.execute("x = 2\ny = x * 3\nprint(y)", {trace:true});
ok(tr.trace && tr.trace.length>=3, "轨迹：记录了多步执行");
ok(tr.trace.some(function(l){ return /x = 2/.test(l); }), "轨迹：记录了赋值 x = 2");
ok(tr.trace.some(function(l){ return /y = 6/.test(l); }), "轨迹：记录了赋值 y = 6");
ok(tr.trace.some(function(l){ return /输出 → 6/.test(l); }), "轨迹：记录 print 输出 6");
const trLoop = ctx.execute("for i in range(3):\n    print(i)", {trace:true});
ok(trLoop.trace.some(function(l){ return /第 1 轮/.test(l); }) && trLoop.trace.some(function(l){ return /第 3 轮/.test(l); }), "轨迹：记录了循环的每一轮");

// ---------- 结果 ----------
console.log(`\n通过 ${pass} 项，失败 ${fail} 项`);
if (fail) {
  console.log("失败明细：");
  fails.forEach((f) => console.log("  - " + f));
  process.exit(1);
} else {
  console.log("全部逻辑自测通过 ✅");
}
