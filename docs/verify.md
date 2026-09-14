# App Hub 门禁（verify_all.py）· 12 维一键校验

> 一条命令校验整个 App Hub（57 微应用 + Flask 后端）的健康度，防止迭代留下损坏状态。
> 退出码 `0` = 全部通过；`1` = 存在问题。R88 起共 **12 大门禁**。

## 怎么跑（三选一）

| 方式 | 命令 |
|---|---|
| **一键（Windows）** | 双击根目录 **`verify.bat`**（自动选解释器、跑完暂停显示结果） |
| 命令行 | `python verify_all.py` |
| CI | push / PR 时由 `.github/workflows/verify.yml` 自动跑（GitHub Actions） |

> 本机解释器：`C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12.old.18140\python.exe`
> （装了 Flask 3.1.3；managed 3.13.12 无 Flask，跑后端会 ModuleNotFoundError）。

## 12 大门禁

| # | 门禁 | 校验内容 |
|---|---|---|
| 1 | 前端语法 | 遍历所有应用 `index.html`，抽取内联 `<script>` 用 `node --check` 校验；检测外部 `<script src=>`（含无引号）违规 |
| 2 | 前端单测 | 运行各应用 `test/run.js`（当前 **58 套件**） |
| 3 | 前端运行时 | Node + DOM 模拟实跑各应用脚本（专项 + 通用冒烟），抓加载/初始化崩溃 |
| 4 | 后端冒烟 | import `backend.app`，用 test_client 冒烟 **25 个端点**（含 gen/submit/export 边界） |
| 5 | 数据一致性 | `backend/data/*.json` ↔ `/api/data` 白名单一一对应 |
| 6 | 目录卫生 | 应用目录（有 `index.html` + 大厅注册）↔ 显式声明的非应用目录边界 |
| 7 | 端点一致性 | 前端 fetch 的 `/api/*` ↔ 后端 `@app.route` 定义 |
| 8 | 真实数据覆盖 | 起全新后端，逐一探测后端依赖应用的端点，防真实数据链路断点 |
| 9 | 期货保护 | `futures-inventory/index.html` 工作树必须干净（项目硬规则禁止提交） |
| 10 | 生成守卫 | 规则兜底生成器占位符一致性 + 用户输入已 HTML 转义 + 规则模板可通过自身零依赖门禁 |
| 11 | 库存守卫 | `_bake_inv_em.refresh_one` 异常抓取不得清空真实库存缓存（回归测试） |
| 12 | 生态端点守卫 | `gen_app / submit_app / export_app` 的安全与边界（回归测试，APP_ROOT 重定向临时目录） |

## 环境要点（踩过的坑）

- **删除保护（safe-delete）**：本机单回合删除次数达阈值后，删除动作会被硬拦、可能中断非交互进程。
  门禁已**做到零删除**：前端临时文件写系统临时目录（覆盖写、不删）、运行时桩缺失时先探测再创建、
  冒烟产物用 `rename` 清理。因此 `verify_all.py` 现在**无需任何外部 runner 即可直跑**。
- **node 解析**：优先托管路径，缺失时回退 `PATH` 上的 `node`（故可跑在 CI/ubuntu）。
- **离线模式**：门禁自起后端用 `OFFLINE_MODE=True`，不依赖外网。
- **git 推送**：本环境不支持 `--ff-only`；用 `git push origin master`（默认拒绝非快进 = 安全 FF）。

## 失败排查

- 看汇总行 `汇总: 前端错误 X, ... 总计 N`，定位是哪一维。
- 前端运行时/单测失败会打印对应 `test/run.js` 或 App 名的失败尾部。
- 删除保护误拦：确认 `_jscheck_*.tmp.js` 不再写仓库根（应在系统临时目录 `apphub_jscheck`）。
