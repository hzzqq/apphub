// 前端逻辑运行时验证：shepherd-index（牧羊人8项情绪指标）
// 深度业务断言：阈值打分 scoreOne/levelOf、综合温度三档(贪婪/中性/恐惧)、指标卡渲染、真实 fetch 冷市路径。
const fs = require('fs');
const path = require('path');
const NODE = process.argv[2] || '';
const ROOT = __dirname;
const HTML = path.join(ROOT, 'shepherd-index', 'index.html');

const store = {};
global.localStorage = { getItem:k=>(k in store?store[k]:null), setItem:(k,v)=>{store[k]=String(v);}, removeItem:k=>{delete store[k];} };
const CTX_STUB = new Proxy(function(){}, { get:()=>CTX_STUB, apply:()=>CTX_STUB });
function el(){
  return {
    _html:"", _value:"",
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

// 真实 fetch 路径：冷市快照（验证综合温度落到恐惧区 + 新鲜度徽标）
global.fetch = () => Promise.resolve({ ok:true, json:()=>Promise.resolve({
  ok:true,
  indicators:{ up_count:200, down_count:4000, limit_up:5, limit_down:40, zt_prev_ret:-2, red_ratio:20, connect_hl:1, zt_fail_ratio:80 },
  temperature:10, date:"2026-09-01", updated:"2026-09-01 10:00:00"
}) });

const html = fs.readFileSync(HTML, 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if(!m){ console.error('NO SCRIPT FOUND'); process.exit(1); }
try { eval(m[1]); } catch(e){ console.error('SCRIPT EVAL THREW:', e.message); process.exit(1); }
console.log('[1] 脚本加载无异常');

// [2] 阈值打分纯函数断言（真实领域逻辑，不能错）
let bad = 0;
function expect(name, got, want){ const ok = got===want; if(!ok){ bad++; console.error('  ✗ %s: got=%s want=%s', name, got, want); } else console.log('  ✓ %s = %s', name, got); }
expect('scoreOne(up_count,4000)', scoreOne('up_count',4000), 100);   // >=hot
expect('scoreOne(up_count,2000)', scoreOne('up_count',2000), 50);    // >=warm
expect('scoreOne(up_count,500)',  scoreOne('up_count',500), 10);     // <warm
expect('levelOf(up_count,4000)',  levelOf('up_count',4000), 'hot');
expect('levelOf(up_count,2000)',  levelOf('up_count',2000), 'mid');
expect('levelOf(up_count,500)',   levelOf('up_count',500),  'cold');
expect('levelOf(limit_down,3)',   levelOf('limit_down',3), 'hot');    // dir<0: <=hot
expect('levelOf(limit_down,10)',  levelOf('limit_down',10),'mid');
expect('levelOf(limit_down,30)',  levelOf('limit_down',30),'cold');
if(bad>0){ console.error('[2] 阈值打分断言失败 %d 项', bad); process.exit(1); }
console.log('[2] scoreOne/levelOf 阈值打分 9 项全过');

// [3] 演示快照(偏热市) -> 综合温度应进入贪婪区(>=70)
demoSnapshot();
const tHot = parseInt(document.getElementById('tempNum').textContent, 10);
console.log('[3] demoSnapshot 综合温度 =', tHot, '| verdict 含贪婪:', document.getElementById('verdict').innerHTML.includes('贪婪'));
if(!(tHot >= 70)){ console.error('[3] 热市 demo 温度未达贪婪区(>=70):', tHot); process.exit(1); }

// [4] 指标卡渲染：indGrid 非空且含 .ind
renderIndicators();
const grid = document.getElementById('indGrid').innerHTML;
console.log('[4] indGrid 渲染长度 =', grid.length, '| 含 .ind:', grid.includes('class="ind"'));
if(!grid.includes('class="ind"')){ console.error('[4] 指标卡未渲染'); process.exit(1); }

// [5] 真实 fetch 冷市路径 -> 温度落到恐惧区(<45) 且新鲜度徽标生成
store.hub_api = "http://127.0.0.1:8787";
(async function(){
  try {
    await fetchLive();
    await new Promise(r=>setTimeout(r, 60));
    const tCold = parseInt(document.getElementById('tempNum').textContent, 10);
    const verdict = document.getElementById('verdict').innerHTML;
    console.log('[5] fetchLive(冷市) 综合温度 =', tCold, '| verdict 含恐惧:', verdict.includes('恐惧'));
    if(!(tCold < 45)){ console.error('[5] 冷市温度未落恐惧区(<45):', tCold); process.exit(1); }
    const fresh = document.getElementById('freshness').innerHTML;
    console.log('[5b] 新鲜度徽标:', fresh.includes('2026-09-01 10:00:00') ? '已注入 updated' : '未注入');
    if(!fresh.includes('2026-09-01 10:00:00')){ console.error('[5b] 新鲜度徽标未显示 updated'); process.exit(1); }
  } catch(e){ console.error('[5] fetchLive THREW:', e.message); process.exit(1); }
  console.log('ALL FRONTEND RUNTIME CHECKS PASSED');
})();
