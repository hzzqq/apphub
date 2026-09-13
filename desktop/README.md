# App Hub 桌面壳层

把 App Hub 大厅（单页 `index.html` + Flask 后端）装进**原生窗口**。两条路：

| 方式 | 需要工具链 | 产物 | 适合 |
|---|---|---|---|
| **① 零编译启动器**（`launch.py`） | 只要 Python | 应用窗口（Edge/Chrome `--app` 模式） | **现在就能用**，推荐先试 |
| **② Tauri 真编译**（`tauri build`） | Rust + Node | 独立 `.exe` / `.dmg` / `.AppImage` | 要分发、要托盘/全局快捷键 |

> 两种方式加载的都是本地 Flask 后端 `http://127.0.0.1:8787` 的页面——
> 因为 App Hub 的应用要调 `/api/*`，纯静态打包跑不起来。

---

## ① 零编译启动器（无需 Rust / Node / 打包）

```bash
# Windows：双击 launcher.bat
# mac/Linux：
bash desktop/launcher.sh

# 或直接
python desktop/launch.py
```

流程：后端没起就后台拉起 `python backend/app.py` → 等 8787 就绪 →
用 Edge/Chrome 的 `--app` 模式打开（无地址栏、无标签页，观感接近原生窗口）；
找不到 Chromium 内核时退化为系统默认浏览器。

可选环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `APPHUB_PORT` | `8787` | 后端端口 |
| `APPHUB_PYTHON` | 当前 `python` | 指定跑后端的解释器（Flask 要装在这个解释器上） |

> 后端日志写进 `desktop/.backend.log`（已被 `.gitignore` 忽略）。
> 关闭窗口**不会**停后端，要停请结束 `python backend/app.py` 进程。

---

## ② Tauri 真编译（需要 Rust）

### 先跑静态校验（不需要 Rust，随时可跑）

```bash
python desktop/scripts/verify.py
```

检查项：`tauri.conf.json` 能否解析、必填字段、`beforeDev/BuildCommand`
指向的脚本是否存在、**每个图标是否真实存在且是合法 PNG/ICO**、
`Cargo.toml` 依赖、`package.json`、零编译启动器是否齐全，以及本机工具链探测。

> 本次在本机实测：**阻断问题 0 个**；仅 3 条警告（未安装 cargo/rustc，
> 故本机只能静态校验、无法真编译）。

### 装工具链（只需一次）

1. Rust：<https://rustup.rs>（装完重启终端，确认 `cargo -V` 有输出）
2. Node 18+：<https://nodejs.org>
3. Linux 额外依赖（Tauri 官方要求）：
   ```bash
   sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
     libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev
   ```

### 开发模式

```bash
cd desktop
npm install
npm run dev          # = tauri dev
```

`beforeDevCommand` 会自动跑 `scripts/start-backend.js`：
端口已在监听就跳过，没起就拉起后端并等它就绪，然后才开窗口。

### 打正式包

```bash
cd desktop
npm run build        # = tauri build
```

`beforeBuildCommand` 先跑 `scripts/build-frontend.js` 生成 `dist/index.html`
（把窗口带到 `http://127.0.0.1:8787` 的跳转页），所以**打包产物很小，
且永远跟随最新界面**——不必把 30+ 个应用目录静态复制进安装包。

产物位置：

- Windows：`desktop/src-tauri/target/release/bundle/nsis/*.exe`、`msi/*.msi`
- macOS：`.dmg` / `.app`
- Linux：`.AppImage` / `.deb`

> **运行前提**：打包出来的程序仍需本地后端在 8787 上跑着
> （先 `python backend/app.py`，或让 `launch.py` 帮你起）。
> 要把 Python 一起打进安装包需用 Tauri sidecar 捆绑 Python 运行时，
> 体量大很多，本项目默认未开启（见下方「完全离线打包」）。

### 图标

仓库已内置占位图标（脚本生成，主题渐变紫）：

```bash
python desktop/scripts/make-icons.py    # 重新生成 32x32.png / 128x128.png / icon.ico
```

要正式图标，用官方命令一键生成全套（含 macOS 需要的 `icon.icns`）：

```bash
npx tauri icon path/to/your-1024.png
```

---

## 目录结构

```
desktop/
├── launch.py              零编译启动器（起后端 + 应用模式开窗）
├── launcher.bat           Windows 双击入口
├── launcher.sh            mac/Linux 入口
├── package.json           npm scripts（dev/build/verify/launch…）
├── scripts/
│   ├── start-backend.js   beforeDevCommand：拉起并等待后端
│   ├── build-frontend.js  beforeBuildCommand：生成 dist 跳转页
│   ├── make-icons.py      生成占位图标（纯标准库）
│   └── verify.py          静态校验（无 Rust 也能跑）
├── dist/                  构建产物（已 gitignore）
└── src-tauri/
    ├── tauri.conf.json    Tauri v2 配置（devUrl / frontendDist / 图标）
    ├── Cargo.toml         Rust 依赖（tauri 2 + tauri-build）
    ├── build.rs           tauri_build::build()
    ├── src/main.rs        入口（刻意不引插件，保证首次编译成功率）
    └── icons/             32x32.png / 128x128.png / icon.ico
```

---

## 进阶：全局快捷键（呼出/隐藏）

对标 uTools 的「呼出即用」。在 `src-tauri/Cargo.toml` 加依赖
`tauri-plugin-global-shortcut`、`tauri-plugin-shell`，再把
`src-tauri/src/main.rs` 换成：

```rust
use tauri::{Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};

fn main() {
  tauri::Builder::default()
    .plugin(tauri_plugin_global_shortcut::Builder::new().build())
    .plugin(tauri_plugin_shell::init())
    .setup(|app| {
      let window = app.get_webview_window("main").unwrap();
      let shortcut = Shortcut::new(Some("CmdOrCtrl"), "Space").unwrap();
      app.global_shortcut().on_shortcut(shortcut, move |_app, _sc, event| {
        if event.state == ShortcutState::Pressed {
          if window.is_visible().unwrap() { window.hide().unwrap(); }
          else { window.show().unwrap(); window.set_focus().unwrap(); }
        }
      })?;
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("启动 App Hub 桌面壳层失败");
}
```

## 进阶：系统托盘 + 开机自启

- **托盘**：`tauri.conf.json` 的 `app` 下加 `trayIcon`（需提供图标），见 Tauri v2 文档。
- **自启**：加 `tauri-plugin-autostart`，在 `setup` 里调用其 `enable` API。

## 进阶：完全离线打包（把后端一起带上）

希望双击桌面应用即可用、无需另起后端时：用 `tauri-plugin-shell` 的 **sidecar**
机制把后端随壳层启动。后端是纯 Flask，可先用 `pyinstaller` 打成单文件再作为 sidecar 随附：

```bash
pyinstaller --onefile backend/app.py
```

然后把可执行文件登记为 sidecar，并在 `setup` 中拉起它，再等端口就绪后显示窗口。

---

## 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| `npm run dev` 卡住 | 后端起不来 | 看 `desktop/.backend.log`；或用 `APPHUB_PYTHON` 指定装了 Flask 的解释器 |
| 窗口一片空白 | 后端没在 8787 | 先 `python backend/app.py` 再开窗口 |
| `tauri build` 报图标错 | 图标缺失/非法 | `python scripts/make-icons.py` 后重试 |
| 想要托盘/全局快捷键 | 当前未引插件 | 按上文「进阶」加 `tauri-plugin-*` 并注册 |
