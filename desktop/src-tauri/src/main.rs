// App Hub 桌面壳层
//
// 窗口内容由 tauri.conf.json 决定：
//   - `tauri dev`  : 直连本地 Flask 后端 http://127.0.0.1:8787
//                    （beforeDevCommand 会先起后端，端口就绪后 Tauri 才开窗口）
//   - `tauri build`: 加载 frontendDist(../dist) 的跳转页，由跳转页把窗口带到本地后端
//
// 这里刻意不引入任何插件：依赖越少，首次 `tauri build` 越不容易失败。
// 需要托盘/全局快捷键时，再往 Cargo.toml 加 tauri-plugin-* 并在 Builder 上注册。

// 发布构建隐藏 Windows 控制台窗口（调试时保留，便于看日志）
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("启动 App Hub 桌面壳层失败");
}
