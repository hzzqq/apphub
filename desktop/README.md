# App Hub 桌面壳层（Tauri）

把 App Hub 大厅包成桌面应用，获得 **全局快捷键呼出 + 系统托盘常驻 + 开机自启**，
对标 uTools / Rubick 的「呼出即用、用完即走」体验。选用 **Tauri**（Rust + 系统 WebView），
安装包比 Electron 小一个数量级，且 App Hub 本身就是零依赖单文件 HTML，天然契合。

## 目录约定
```
app/                  ← 仓库根（index.html / backend/ 都在这里）
└── desktop/          ← 本目录（Tauri 工程）
    ├── tauri.conf.json
    ├── package.json
    └── src-tauri/     ← 首次 `npm i` 后由 Tauri CLI 生成（Rust 侧）
```

## 构建步骤
1. 前置：安装 [Node](https://nodejs.org) + [Rust 工具链](https://rustup.rs) + Tauri CLI 依赖（见官网「prerequisites」）。
2. 安装依赖：
   ```bash
   cd desktop && npm install
   ```
3. 启动后端（桌面壳层加载的是 `http://127.0.0.1:8787` 的真实页面，需后端提供）：
   ```bash
   # 仓库根目录另开终端
   python backend/app.py
   ```
4. 开发模式启动桌面壳层：
   ```bash
   npm run tauri dev
   ```
5. 打包安装包：
   ```bash
   npm run tauri build
   ```
   产物在 `desktop/src-tauri/target/release/bundle/`（.msi / .dmg / .AppImage 等）。

## 全局快捷键（呼出/隐藏）
在 `src-tauri/` 生成后，于 `src-tauri/src/lib.rs` 注册：
```rust
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};
use tauri::{Manager};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_global_shortcut::Builder::new().build())
    .plugin(tauri_plugin_shell::init())
    .setup(|app| {
      let window = app.get_webview_window("main").unwrap();
      let shortcut = Shortcut::new(Some("CmdOrCtrl"), "Space").unwrap();
      app.global_shortcut().register(shortcut).unwrap();
      app.global_shortcut().on_shortcut(shortcut, move |_app, _sc, event| {
        if event.state == ShortcutState::Pressed {
          if window.is_visible().unwrap() { window.hide().unwrap(); }
          else { window.show().unwrap(); window.set_focus().unwrap(); }
        }
      }).unwrap();
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
```
并把 `src-tauri/Cargo.toml` 加上依赖 `tauri-plugin-global-shortcut`、`tauri-plugin-shell`、`tauri-plugin-autostart`。

## 系统托盘 + 开机自启（可选）
- **托盘**：`tauri.conf.json` 的 `app` 下加 `systemTray`（需提供托盘图标），见 Tauri 文档。
- **自启**：在 `setup` 中调用 `tauri_plugin_autostart` 的 `enable` API，并在 `Cargo.toml` 加 `tauri-plugin-autostart`。

## 完全离线打包（进阶）
若希望双击桌面应用即可用、无需另起后端：把后端用 `tauri-plugin-shell` 作为 **sidecar** 随壳层启动，
并让 `devUrl`/`frontendDist` 指向本地服务。App Hub 后端是纯 Flask，可 `pyinstaller` 打成单文件后作为 sidecar 随附。

> 说明：本目录仅提供**可构建的配置骨架**，沙箱环境无 Rust/Node 工具链未实际编译，按上述步骤在本地即可产出安装包。
