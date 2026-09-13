/**
 * 启动 Flask 后端，供 Tauri `devUrl` 使用。
 * - 端口已在监听 → 直接退出（重复 dev 不冲突、不会重复拉起）
 * - 未监听 → 拉起 `python backend/app.py`，并等待端口就绪后才返回
 *
 * 环境变量：
 *   APPHUB_PORT   后端端口（默认 8787）
 *   APPHUB_PYTHON python 解释器（默认 python）
 */
const { spawn } = require('child_process');
const net = require('net');
const path = require('path');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..', '..'); // desktop/ -> 仓库根
const PORT = Number(process.env.APPHUB_PORT || 8787);
const PY = process.env.APPHUB_PYTHON || 'python';

function portOpen(port, host) {
  return new Promise((resolve) => {
    const s = net.createConnection({ port, host });
    const done = (v) => { try { s.destroy(); } catch (e) { /* noop */ } resolve(v); };
    s.once('connect', () => done(true));
    s.once('error', () => done(false));
    s.setTimeout(800, () => done(false));
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  if (await portOpen(PORT, '127.0.0.1')) {
    console.log('[apphub] 后端已在 127.0.0.1:%d 运行，跳过启动', PORT);
    return;
  }
  if (!fs.existsSync(path.join(ROOT, 'backend', 'app.py'))) {
    console.error('[apphub] 未找到 backend/app.py（ROOT=%s）', ROOT);
    process.exit(1);
  }
  console.log('[apphub] 启动后端：%s backend/app.py（cwd=%s）', PY, ROOT);
  const child = spawn(PY, ['backend/app.py'], { cwd: ROOT, stdio: 'inherit' });
  child.on('error', (e) => {
    console.error('[apphub] 启动失败：%s（可设 APPHUB_PYTHON 指定解释器）', e.message);
    process.exit(1);
  });
  for (let i = 0; i < 60; i++) {
    if (await portOpen(PORT, '127.0.0.1')) {
      console.log('[apphub] 后端已就绪');
      return;
    }
    await sleep(500);
  }
  console.error('[apphub] 后端 30s 内未就绪，请检查 Flask 依赖是否已安装');
  process.exit(1);
})();
