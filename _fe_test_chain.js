// 前端逻辑运行时验证：futures-chain（期货产业链望远镜）
// 深度业务断言：runAnalysis 真实 fetch 渲染报告 + initFolds 不崩 + 日期工具 _isoDate + applyDaysRange 区间。
const fs = require('fs');
const path = require('path');
const NODE = process.argv[2] || '';
const ROOT = __dirname;
const HTML = path.join(ROOT, 'futures-chain', 'index.html');

const store = {};
global.localStorage = { getItem:k=>(k in store?store[k]:null), setItem:(k,v)=>{store[k]=String(v);}, removeItem:k=>{delete store[k];} };
const CTX_STUB = new Proxy(function(){}, { get:()=>CTX_STUB, apply:()=>CTX_STUB });
function el(){
  return {
    _html:"", _value:"", disabled:false,
    set innerHTML(v){ this._html = v; }, get innerHTML(){ return this._html; },
    set value(v){ this._value = v; }, get value(){ return this._value; },
    textContent:"", style:{},
    classList:{ toggle(){}, add(){}, remove(){}, contains(){return false;} },
    addEventListener(){}, setAttribute(){}, getAttribute(){return null;},
    appendChild(){}, removeChild(){}, insertAdjacentHTML(p,h){ this._html += h; },
    querySelectorAll(){ return []; }, click(){},
    getContext(){ return CTX_STUB; },
  };
}
const cache = {};
global.document = {
  getElementById(id){ return cache[id] || (cache[id]=el()); },
  querySelectorAll(){ return []; },
  createElement(){ return el(); },
  body: el(),
};
global.window = global;
global.requestAnimationFrame = cb => cb();
if(!global.URL.createObjectURL) global.URL.createObjectURL = () => 'blob:test';
if(!global.URL.revokeObjectURL) global.URL.revokeObjectURL = () => {};

// 真实 fetch 路径：返回一份产业链报告
global.fetch = () => Promise.resolve({ ok:true, json:()=>Promise.resolve({
  ok:true, offline:false,
  html:"<div class='chain'>纸浆 SP 相关性传导：针叶浆↔阔叶浆↔下游纸品</div>",
  updated:"2026-09-01 00:00:00"
}) });

const html = fs.readFileSync(HTML, 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if(!m){ console.error('NO SCRIPT FOUND'); process.exit(1); }
try { eval(m[1]); } catch(e){ console.error('SCRIPT EVAL THREW:', e.message); process.exit(1); }
console.log('[1] 脚本加载无异常');

// [2] 日期工具
expect_iso = _isoDate(new Date(2026,0,5));
console.log('[2] _isoDate(2026-01-05) =', expect_iso);
if(expect_iso !== "2026-01-05"){ console.error('[2] _isoDate 错误:', expect_iso); process.exit(1); }

// [3] 时间区间：applyDaysRange(30) 应填充 from/to，且 from<=to
applyDaysRange(30);
const fromV = document.getElementById('from').value;
const toV = document.getElementById('to').value;
console.log('[3] applyDaysRange(30): from=%s to=%s', fromV, toV);
if(!fromV || !toV || fromV > toV){ console.error('[3] 区间无效'); process.exit(1); }

// [4] runAnalysis 真实 fetch 渲染
store.hub_api = "http://127.0.0.1:8787";
document.getElementById('sym').value = "sp";
document.getElementById('exch').value = "SHFE";
(async function(){
  try {
    runAnalysis();
    await new Promise(r=>setTimeout(r, 120)); // 等 fetch 异步链
    const rep = document.getElementById('report').innerHTML;
    const st = document.getElementById('status').innerHTML;
    console.log('[4] report 长度 =', rep.length, '| 含产业链内容:', rep.includes('chain'), '| status 含分析完成:', st.includes('分析完成'));
    if(!rep.includes('chain')){ console.error('[4] 报告未渲染'); process.exit(1); }
    if(!st.includes('分析完成')){ console.error('[4] 状态未更新为分析完成:', st); process.exit(1); }
    // [4b] 新鲜度徽标
    const fresh = document.getElementById('freshness').innerHTML;
    console.log('[4b] 新鲜度徽标:', fresh.includes('2026-09-01 00:00:00') ? '已注入 updated' : '未注入');
    if(!fresh.includes('2026-09-01 00:00:00')){ console.error('[4b] 新鲜度徽标未显示 updated'); process.exit(1); }
  } catch(e){ console.error('[4] runAnalysis THREW:', e.message); process.exit(1); }
  console.log('ALL FRONTEND RUNTIME CHECKS PASSED');
})();
