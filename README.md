# App Hub · 零依赖微应用集合

31 个**单文件 HTML** 小工具，双击即开、数据本地存储（localStorage），零外部依赖、零构建。
覆盖金融投研与生活效率两大类，并配一个**统一后端**为金融类 App 提供真实行情/数据。

> 标记 🔌 的应用需要连后端才有真实数据；未连后端时自动显示本地样本，大厅卡片会实时标注当前状态。
> 其余应用纯本地运行，不联网也有完整功能。

> 设计原则：每个 App 都是独立的 `index.html`（内联 CSS/JS，不引用任何外部 `.js`/`.css`），
> 可直接用浏览器打开，也能被大厅聚合分发。

---

## 快速开始

1. **纯本地模式**：直接用浏览器打开 `index.html`（应用大厅），挑应用打开即可。
   所有数据存于浏览器本地，不依赖任何服务。
2. **真实数据模式**（可选，需联网机器）：
   ```bash
   cd backend
   pip install -r requirements.txt          # Flask / flask-cors / akshare / pytest
   python app.py                             # 默认 http://127.0.0.1:8787
   ```
   回到大厅，在「🔌 真实数据接口」填 `http://127.0.0.1:8787` 并保存。
   **所有支持后端的 App 会自动继承该地址**，无需逐个配置。
3. 后端默认 `OFFLINE_MODE=True`（沙箱禁网环境返回结构化静态样本，可离线跑/验证）。
   部署时用环境变量 `OFFLINE_MODE=False`（Dockerfile / Procfile / systemd 单元已默认注入），
   即自动抓取 akshare 真实数据，并按 `REFRESH_HOURS`（默认 6 小时）**后台自动刷新缓存**——
   访客打开网页看到的就是最新数据，无需任何操作。
4. **先备份你的数据**：所有 App 的数据只存在当前浏览器的 localStorage，
   清缓存 / 换设备 / 重装浏览器即永久丢失。大厅顶部「💾 数据备份」可一键导出全部数据为 JSON，
   换设备时用「导入恢复」还原（导入前二次确认，并做键名 / 类型 / 8MB 大小校验）。

---

## 应用清单（31 个）

### 金融类（15）
| 应用 | 说明 |
|---|---|
| 股事贴 stocknote | 个股利好/利空事件卡片，按股票分组、搜索、JSON 导入导出 |
| 价格预警 price-alert | 监控股票价格，突破阈值浏览器弹窗 + 微信/企业微信提醒 |
| K线形态速查卡 kpattern 🔌 | 14 种 K 线形态图解与多空信号 |
| 市场情绪温度计 mood-meter | 从 2008 起 A股牛熊基准叠加每日情绪打分 |
| 财报跟踪器 earnings-calendar | 财报披露日历，临近高亮，可查往年财报 |
| 期库镜 futures-inventory 🔌 | 期货 K线×库存双轴透视，皮尔逊相关性 + 全球合计，含**数据新鲜度徽标** |
| 价差望远镜 futures-spread 🔌 | 跨期 / 跨品种价差序列，自定义区间、选择记忆、导出 CSV（内置 21 品种真实快照） |
| 产业链联动分析 futures-chain 🔌 | 输入期货品种，自动产出跨品种相关性（原始 + 剔除大盘β偏相关）+ 产业链传导报告 |
| 盘前收盘速读 market-brief | A股盘前策略与收盘复盘要点卡 |
| 牧羊人指标 shepherd-index 🔌 | 复刻股海牧羊人 8 项情绪指标 + 温度计打分 |
| 黑天鹅预警 blackswan | 宏观黑天鹅时间轴 + 个股业绩雷/监管异动扫描 |
| 板块轮动仪 sector-rotation 🔌 | 申万行业涨跌与轮动强度可视化 |
| ETF筛选器 etf-picker 🔌 | 按类型/规模/收益筛选 ETF |
| 持仓体检 holdings-check 🔌 | 持仓集中度/行业集中/浮亏 4 维诊断 |
| 智能条件单 smart-order 🔌 | 涨破/跌破触发规则，浏览器 Notification 弹窗 |

### 生活 / 效率类（16）
| 应用 | 说明 |
|---|---|
| 桌面宠物豆豆 desktop-pet | 心情/饱食/精力三态宠物，喂食玩耍 |
| 行程规划 itinerary | 源自 map 项目的 AI 行程生成器，按城市+天数+风格生成每日骨架，支持分享码/对比/多格式导出 |
| 健康体检单 health-check | 个人/品牌 4 维自检清单 + 短板诊断 |
| TradingAgents trading-agents 🔌 | 模拟投行投研团队多智能体协同出结论（可接 LLM 综合解读） |
| 主题工坊 theme-studio | 类似 Miku Codex 的主题更换器，一键切换并导出配色 |
| 小狐狸讲代码 code-teacher 🔌 | 输入代码，输出妈妈版/弟弟版/标准版解释（可接 LLM 增强） |
| 习惯打卡 habit-tracker | 每日打卡 + 连续天数 + 30 天热力图 |
| 专注番茄钟 focus-timer | 25/5/15 分钟番茄钟，统计番茄数 |
| 菜谱收藏盒 recipe-box | 收藏菜谱，按分类与食材搜索 |
| 健身记录 workout-log | 记录训练组数/重量，统计近 7 天容量 |
| 书签收藏家 bookmark-manager | 收藏网页/工具/论文，按标签检索 |
| 密码保险库 password-vault | 本地生成强密码 + 保存账号，数据不上传 |
| 随手记账本 expense-ledger | 记录收支，分类统计，月度结余 |
| 待办清单 todo-list | 添加待办，设优先级/截止日/分类，筛选统计并导出 JSON |
| 倒数日 countdown | 记录纪念日与目标日，实时显示倒计时或已过天数，按临近排序 |
| 单位换算器 unit-converter | 长度/重量/温度/面积/体积/时间/速度/数据等常用单位实时换算 |

### 🔌 需要后端才有真实数据的应用（11 个）

| 应用 | 目录 | 应用 | 目录 |
|---|---|---|---|
| 期库镜 | `futures-inventory` | 持仓体检 | `holdings-check` |
| 价差望远镜 | `futures-spread` | 智能条件单 | `smart-order` |
| 产业链联动分析 | `futures-chain` | | |
| ETF 筛选器 | `etf-picker` | K线形态速查卡 | `kpattern` |
| 板块轮动仪 | `sector-rotation` | TradingAgents | `trading-agents` |
| 牧羊人指标 | `shepherd-index` | 小狐狸讲代码 | `code-teacher` |

其余 17 个应用**纯本地运行**，不联网也有完整功能。大厅会在每张卡片上实时标注当前后端连通状态
（🔌 真实数据 / ⚠ 本地样本），并在打开依赖后端的应用而后端未连接时提醒一次。

---

## 统一后端（`backend/`）

Flask 服务，为前端微型 App 提供真实数据。行情源模仿 StockSignal（新浪 `hq.sinajs.cn` + akshare 兜底）。

**主要端点**（完整清单见 `/api/info` 或 `backend/README.md`）：
- `/api/futures` 期货 K线×库存（单品种 / 全球合计）
- `/api/corr_top` 全品种皮尔逊相关性 Top N（自动选最相关库存口径）
- `/api/quote` 股票实时行情
- `/api/shepherd` 牧羊人 8 项情绪指标 + 综合温度
- `/api/blackswan` 黑天鹅事件 + 个股业绩雷扫描
- `/api/earnings` 往年财报
- `/api/search` 股票/基金/期货/指数搜索
- `/api/etf` `/api/sector` ETF/板块行情
- `/api/data` 工具类 App 的本地结构化 JSON（白名单防穿越）
- `/api/futures_spread` 价差序列 · `/api/futures_events` 事件时间轴
- `/api/trading_agents` `/api/code_teacher` `/api/llm` `/api/theme` 新 App 数据
- `/api/health` 存活检查（含 `auto_refresh` 刷新诊断）
- `/api/data_status` **数据新鲜度总览**：每个期货缓存的最新数据日期 / 距今天数 / 记录数，
  以及最新 / 最旧 / 平均滞后天数与滞后品种数
- `/api/refresh` 手动触发重抓真实数据并改写缓存

**自动刷新（部署后数据自保持最新）**：后端启动即开后台线程，按 `REFRESH_HOURS`（默认 6 小时）重抓全部品种。
- 刷新失败保留上一次真实缓存，**绝不回退合成样本、绝不空白**；
- 连续失败 ≥3 次的品种自动降频（每 3 轮才重试一次），避免长期无数据源的品种每轮白抓；
- `/api/health` 返回 `last_run / last_ok / last_fail / last_errors / next_run / runs / degraded`，
  部署后可直接判断"数据到底有没有在更新、失败原因是什么"。

**三级数据加载（前端约定）**：真实后端 → 本地静态样本（`backend/data/*.json`）→ 内置兜底，永不空白/随机。

**数据新鲜度（让用户看得见）**：数据"是哪一天的"此前完全不可见，容易造成误判。现在：
- **期库镜** KPI 显示「🟢/🟡/🔴 数据截至 YYYY-MM-DD（N 天前）」：超过一个发布周期提示可能滞后，
  超过两个周期红色告警，并给出「下次预计发布日」。
- **大厅**连上后端后显示「📊 N 个品种 · 最新 X 天前 · 平均 Y 天 · ⚠ Z 个滞后」。

**安全**：`/api/data` 仅允许白名单文件，目录穿越/越权均返回 400；CORS 已放开供本地前端调用。

---

## 设计风格

大厅采用 **Bento Grids（暗色版）** 设计系统（模板来源：`ui-ux-pro-max` 模板库 #53 Bento Grids + #7 Dark Mode(OLED)）：
4 列模块化 tile 网格、`--grid-gap:16px` / `--card-radius:20px` / 柔和阴影 / hover 微缩放（1.02）/ **收藏的应用渲染为 2×1 宽卡**。
沿用原有 CSS 变量名（`--bg` / `--card` / `--accent` 等），因此「主题工坊」切换主题仍可全局覆盖。
响应式：>1080px 四列、660–1080px 两列、<660px 单列；尊重 `prefers-reduced-motion`，并保留键盘焦点轮廓。

## 开发新 App

1. 在大厅 `index.html` 的 `APPS` 数组加一行（`dir`/`name`/`ico`/`cat`/`tag`/`desc`）。
2. 新建 `<dir>/index.html`，**单文件内联 CSS/JS**，不引用任何外部资源。
3. 如需真实数据：读取 `localStorage.getItem("hub_api")` 作为后端根地址，拼对应 `/api/*` 端点；
   失败时回退本地静态样本或内置演示，保证离线可用。
4. 若该 App 依赖后端，把目录名加进大厅的 `NEEDS_BACKEND` 列表——大厅据此标注状态，
   并在后端未连接时提醒用户"将看到本地样本"。
5. ⚠️ **不要在 `<dir>/` 下再建 git 仓库**。曾因 5 个目录含嵌套 `.git`，父仓库只记录了 gitlink，
   导致 GitHub 仓库 clone 后这些目录为空、分享出去跑不起来。

---

## 数据备份 / 迁移

大厅顶部「💾 数据备份」：
- **导出**：把本机全部 localStorage 打包为 `AppHub备份_YYYY-MM-DD.json`（含 `format` 标记、版本、时间戳）。
- **导入**：依次校验 format 标记 → 结构 → 键名合法性 → 值必须为字符串 → 8MB 上限，
  通过后才写入，覆盖前二次确认，完成后自动刷新。
- 密码保险库等数据以**密文**形式导出，恢复后仍用原主密码解密。

---

## 质量门禁

```bash
python verify_all.py
```

一键校验：
- 前端 30 个 App + 大厅的内联 JS 语法（`node --check`）
- 各 App 与大厅的 `test/run.js` 前端逻辑单测（11 个套件；大厅覆盖备份校验、新鲜度文案、后端依赖标注）
- 后端全部端点冒烟（离线模式）
- `backend/data/*.json` 与 `/api/data` 白名单一致性
- **应用目录 vs 非应用目录卫生**（有 `index.html` 且在大厅 `APPS` 注册才算应用；其余须声明为非应用目录）
- **前端 `/api/*` 调用 ↔ 后端路由定义一致性**（防前后端脱节；孤儿路由仅提示不报错）

后端契约测试另见 `backend/test_app.py`（`pytest -q`）。

---

## 启动与停止（本地双击模式）

启动后会出现**两个 cmd 窗口**，各司其职，**别关错**：

| 窗口 | 标题 | 作用 | 关掉影响 |
|---|---|---|---|
| Launcher | `C:\windows\system32\cmd.exe`（路径见标题栏） | 一次性启动器：装依赖、起 backend、刷数据、开浏览器 | ✅ 可随时关，**不影响** App 跑 |
| **HubBackend** | `🟢 App Hub Backend ⏐ 别关！…` | Flask 后端真在跑的进程（13 个 `/api/*` 在此） | ❌ **关掉 = 所有依赖后端的 App 立刻断数据** |

**正确停止后端**（二选一）：
- 双击项目根目录的 **`stop.bat`** —— 按端口 `8787` 找到 Flask 进程并杀，安全精准
- 或在 HubBackend 窗口里按 **`Ctrl + C`** —— Flask 自己干净退出

**刷数据**：双击 `refresh_data.bat`（重抓真实行情改写 `backend/data/*.json` 缓存）。

---

## 分享与部署

- **发 zip 给别人本地跑**：`python package_for_share.py` → 产出 `app_dist/AppHub.zip`（约 1.1MB，
  内嵌 70 个真实数据缓存）。对方解压后双击 `start.bat` / `start.sh` 即可；
  未装 akshare 时自动降级为离线模式，仍能看到内置的真实历史数据。
- **部署成一个网站（只分享网址）**：见 [`DEPLOY.md`](DEPLOY.md)。后端**同源托管前端**，
  打开 `http://<host>/` 即进入大厅，各 App 自动走同源 API（免填地址、无 CORS），
  并按 `REFRESH_HOURS` 后台自动刷新真实数据，访客零操作即可看到最新数据。
