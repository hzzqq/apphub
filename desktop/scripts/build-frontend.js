/**
 * 生成 desktop/dist/index.html —— Tauri `tauri build` 需要的 frontendDist。
 *
 * App Hub 的界面由 Flask 后端托管，所以桌面端窗口真正需要的不是一份静态拷贝，
 * 而是一个「把窗口带到本地后端」的跳转页。这样打包产物体积最小，且永远跟随最新界面。
 */
const fs = require('fs');
const path = require('path');

const DIST = path.resolve(__dirname, '..', 'dist');
const PORT = Number(process.env.APPHUB_PORT || 8787);
const URL = 'http://127.0.0.1:' + PORT;

fs.mkdirSync(DIST, { recursive: true });

const html = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0;url=${URL}">
<title>App Hub</title>
<style>
  body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
       background:#0f0f23;color:#e8e8f0;font-family:system-ui,'PingFang SC','Microsoft YaHei',sans-serif}
  .box{text-align:center;line-height:2;font-size:14px}
  .sub{color:#9aa0b5;font-size:12px}
  code{background:rgba(255,255,255,.08);padding:2px 6px;border-radius:4px}
</style>
</head>
<body>
  <div class="box">
    <div>正在打开 App Hub…</div>
    <div class="sub">若长时间停留在此，请先启动后端：<code>python backend/app.py</code></div>
  </div>
  <script>window.location.replace(${JSON.stringify(URL)});</script>
</body>
</html>
`;

fs.writeFileSync(path.join(DIST, 'index.html'), html, 'utf8');
console.log('[apphub] 已生成 %s（跳转至 %s）', path.join(DIST, 'index.html'), URL);
