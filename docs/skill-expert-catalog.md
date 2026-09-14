# App Hub 功能板块 × Skill × 专家 · 全量分派目录

> 用途：把 App Hub（`E:\project\app`）大厅 **57 个微应用**按其真实功能拆成 **10 大板块 / 40+ 细分功能**，
> 每个细分功能对应到**可直接调用的 Skill**与**可调用的专家（Agent / 专家包）**，并给出**可直接复制的分派 prompt**。
> 你（老板）拿这份目录去「点将跑任务」即可——每个 prompt 都可直接贴给对应 Skill/专家执行。
>
> - **Skill** = 已安装技能（用户级 `C:\Users\Administrator\.workbuddy\skills\...` 或插件市场 skills）。
> - **专家** = 专家中心里的 Agent/专家包（`a-share-analysis`、`ai-hedge-fund`、`design-to-code`、`ardot-design-generator` 等）。
> - 标注 ⭐ 的为该细分功能的**首选**入口；`（需 conn）`= 需连接对应 connector（westock-mcp / github 等）。

---

## 0. 板块总览（先看这张）

| # | 功能板块 | 涉及微应用（数量） | 核心 Skill | 核心专家 |
|---|---|---|---|---|
| 1 | 行情与报价 | quote-board, watch-board, futures-board, spread-viewer, variety-screener, corr-explorer（6） | `westock-data` ⭐ `a-stock-data` `wb-finance-skill` | `a-share-advisor` `technicals-analyst` |
| 2 | 板块与轮动 | sector-heat, sector-rotation, sector-matrix, market-brief（4） | `style-rotation` ⭐ `sector-comparison` `market-mainline` | `sector-screening` `smart-money-tracker` |
| 3 | 期货与产业链 | futures-inventory（期库镜）, futures-spread, futures-chain, futures-events, eia-watch, inventory-watch, inv-refresh（7） | `futures-combo` ⭐ `industry-chain` `invest-calendar` | `a-share-advisor` `thematic-hunter` |
| 4 | 个股与持仓 | stocknote, holdings-check, holdings-health, earnings-calendar, etf-picker（5） | `stock-deep-dive` ⭐ `financial-report` `valuation-framework` | `stock-research` `portfolio-diagnosis` |
| 5 | 风险与情绪 | blackswan, mood-meter, shepherd-index, market-mood, smart-order, price-alert（6） | `macro-research` ⭐ `northbound-flow` `a-share-daily-review` | `nassim-taleb` `risk-manager` `morning-briefing` |
| 6 | 多智能体投研 | trading-agents, market-qa, trader-avatars（3） | `wb-finance-skill` ⭐ `westock-data` | `ai-hedge-fund` 全套（21 个）⭐ |
| 7 | 数据可观测 | cache-insight, data-status-dash, data-explorer, health-board, info-board, search-box（6） | `microapp-data-hub` ⭐ `offline-realdata-cache` | （工程向，走通用 dev） |
| 8 | 生活与效率 | desktop-pet, itinerary, health-check, habit-tracker, focus-timer, recipe-box, workout-log, bookmark-manager, password-vault, expense-ledger, todo-list, countdown, unit-converter, cube-trainer（14） | `interactive-dashboard-builder` `frontend-design` | （通用；创意类见板块 9） |
| 9 | 创意 · 3D · 主题 | dim-convert, theme-studio, code-teacher（3） | `3D模型与视频特效` ⭐ `ardot-design-assistant` `ui-ux-pro-max` | `ardot-design-generator` `design-to-code` |
| 10 | 工程与交付（跨板块底座） | 整个大厅（index.html）+ backend + verify_all | `apphub-microapp-pipeline` ⭐ `silent-failure-defect-hunt` `flask-secure-json-api` | （工程向，走通用 dev） |

---

## 1. 行情与报价板块

**微应用**：`quote-board`（实时报价板）、`watch-board`（自选行情看板）、`futures-board`（期货总览）、`spread-viewer`（期货跨期价差）、`variety-screener`（期货品种筛选）、`corr-explorer`（相关性探测器）

**细分功能拆解**
| 细分功能 | 对应端点/机制 | 相关 Skill | 相关专家 |
|---|---|---|---|
| A股个股实时报价 | `/api/quote` | `westock-data` ⭐ / `a-stock-data` / `quote-board` 消费 | `technicals-analyst` |
| 自选股实时监控（红涨绿跌） | `/api/quote` + localStorage | `a-stock-data` / `ashare-short-term-trading` | `a-share-advisor` |
| 期货品种总览行情 | `/api/futures` | `westock-data` / `futures-combo` | `a-share-advisor` |
| 跨期价差（近月-远月） | `/api/futures_spread` | `futures-combo` ⭐ | `thematic-hunter` |
| 期货品种筛选/列表 | `/api/futures_varieties` | `a-stock-data` | — |
| 相关性 Top 对 | `/api/corr_top` | `a-stock-data` / `westock-data` | `smart-money-tracker` |

**分派 prompt（直接复制）**
- 行情速览 → `「用 westock-data 拉取沪深300+我自选股票的实时价/涨跌/量，输出成红涨绿跌的表格」`
- 价差结构 → `「用 futures-combo 分析当前玻璃/纯碱/纸浆的跨期价差结构，判断 contango/backwardation 与套利空间」`
- 相关性 → `「用 a-stock-data 计算我关注的这几个品种近 20 日相关性矩阵，找出最强/最弱对」`

---

## 2. 板块与轮动板块

**微应用**：`sector-heat`（板块强弱热力）、`sector-rotation`（板块轮动仪）、`sector-matrix`（板块共振全景）、`market-brief`（盘前收盘速读）

**细分功能拆解**
| 细分功能 | 端点/机制 | 相关 Skill | 相关专家 |
|---|---|---|---|
| 板块涨跌热力 | `/api/sector` | `sector-comparison` ⭐ / `westock-data` | `sector-screening` |
| 申万行业轮动强度 | `/api/sector` | `style-rotation` ⭐ / `market-mainline` | `sector-screening` `smart-money-tracker` |
| 品种×板块共振热力图 | `/api/sector` + 相关性 | `macro-to-stock` / `sector-comparison` | `sector-screening` |
| 盘前/收盘要点 | `/api/shepherd` + 静态 | `market-overview` ⭐ / `a-share-daily-review` | `morning-briefing` |

**分派 prompt**
- 板块选择 → `「用 sector-screening 专家：当前最值得关注的 3 个板块 + 核心标的，给理由」`
- 风格轮动 → `「用 style-rotation skill 判断当前市场偏成长还是价值，并给出轮动路径」`
- 盘前简报 → `「用 morning-briefing 生成今日晨报：宏观→市场→主线→仓位」`

---

## 3. 期货与产业链板块

**微应用**：`futures-inventory`（期库镜 · 期货K线×库存）、`futures-spread`（期货价差望远镜）、`futures-chain`（产业链联动分析）、`futures-events`（期货事件台）、`eia-watch`（原油库存周报）、`inventory-watch`（库存概览）、`inv-refresh`（库存刷新台）

**细分功能拆解**
| 细分功能 | 端点/机制 | 相关 Skill | 相关专家 |
|---|---|---|---|
| 期货K线×库存双轴 + 皮尔逊相关 | `/api/futures` + `inventory` | `futures-combo` ⭐ | `a-share-advisor` |
| 跨月价差望远镜 | `/api/futures_spread` | `futures-combo` | `thematic-hunter` |
| 产业链传导（剔除大盘β偏相关） | `/api/futures_chain` | `industry-chain` ⭐ | `industry-chain`（skill） |
| 期货事件/拐点 | `/api/futures_events` | `invest-calendar` ⭐ | `a-share-advisor` |
| 美国 EIA 原油库存 | `/api/eia_crude`（需 EIA_API_KEY） | `a-stock-data` / `westock-data` | `macro-research` |
| 库存刷新（东方财富） | `/api/refresh` → `_bake_inv_em` | `a-stock-data` | — |

> ⭐ 你的实盘 6 品种（玻璃 FG / 纸浆 SP / 纯碱 SA / 鸡蛋 JD / 白糖 SR / 乙二醇 EG）→ **`futures-combo` 是定制首选**。

**分派 prompt**
- 单品种研判 → `「用 futures-combo 分析纸浆 SP：基本面/库存/价格 + 2026 驱动 + 下跌转折点 + 事件催化」`
- 产业链 → `「用 industry-chain skill 从纯碱出发，映射上下游产业链与受益标的」`
- 库存拐点 → `「用 futures-combo 结合期库镜库存数据，找出玻璃/纯碱的库存拐点与价格背离」`

---

## 4. 个股与持仓板块

**微应用**：`stocknote`（股事贴 · 事件速记）、`holdings-check`（持仓体检）、`holdings-health`（持仓估值）、`earnings-calendar`（财报跟踪器）、`etf-picker`（ETF筛选器）

**细分功能拆解**
| 细分功能 | 端点/机制 | 相关 Skill | 相关专家 |
|---|---|---|---|
| 个股事件速记 | localStorage | `a-share-daily-review` | `news-sentiment-analyst` |
| 持仓 4 维诊断（集中度/行业/浮亏） | 前端计算 + `/api/quote` | `risk-checkup` ⭐ / `position-management` | `portfolio-diagnosis` `risk-manager` |
| 持仓实时估值 | `/api/quote` | `institutional-holdings` / `westock-data` | `portfolio-manager` |
| 财报日历/往年财报 | 静态 + 钩子 | `financial-report` ⭐ / `invest-calendar` | `fundamentals-analyst` |
| 财报质量/公告影响力 | — | `financial-report` ⭐ | `fundamentals-analyst` `news-sentiment-analyst` |
| ETF 筛选（类型/规模/收益） | 静态样本 | `westock-tool` ⭐ / `neodata-financial-search` | — |
| 个股估值与定价 | — | `valuation-framework` ⭐ / `company-quality` | `valuation-analyst` `aswath-damodaran` |

**分派 prompt**
- 个股深度 → `「用 stock-research 专家深度研究 深科技 000021.SZ：先结论后依据，含基本面/财务/估值/机构动向」`
- 持仓体检 → `「用 portfolio-diagnosis 诊断我的持仓：风险检查+泡沫识别+拥挤度+北向态度」`
- 估值 → `「用 valuation-framework skill 给某股做 DCF + 可比估值，判断高估/低估」`

---

## 5. 风险与情绪板块

**微应用**：`blackswan`（黑天鹅预警）、`mood-meter`（市场情绪温度计）、`shepherd-index`（牧羊人指标）、`market-mood`（市场情绪台）、`smart-order`（智能条件单）、`price-alert`（价格预警）

**细分功能拆解**
| 细分功能 | 端点/机制 | 相关 Skill | 相关专家 |
|---|---|---|---|
| 宏观黑天鹅时间轴/个股业绩雷扫描 | 静态库 + 关键词 | `macro-research` ⭐ | `nassim-taleb` |
| 牛熊情绪打分（2008 起） | `/api/shepherd` | `a-share-daily-review` ⭐ | `sentiment-analyst` |
| 牧羊人 8 项指标 | `/api/shepherd` | `market-overview` / `a-share-daily-review` | `morning-briefing` |
| 风险扫描/预警 | 前端 | `risk-checkup` ⭐ | `risk-manager` |
| 条件单/价格提醒 | 前端 Notification + 企微 | `wechat-bridge`（推送） | — |
| 北向资金态度 | `/api/north_holding`（若接） | `northbound-flow` ⭐ | `smart-money-tracker` |

**分派 prompt**
- 泡沫/尾部风险 → `「用 bubble-detection skill + nassim-taleb 专家评估当前市场的反身性与尾部风险」`
- 情绪研判 → `「用 a-share-daily-review 输出今日情绪面：涨停梯队+资金流+情绪打分」`
- 资金主线 → `「用 smart-money-tracker 专家：北向+机构+公募三路资金共识方向」`

---

## 6. 多智能体投研板块

**微应用**：`trading-agents`（TradingAgents · 模拟投行投研团队）、`market-qa`（AI 投研问答 · LLM 网关）、`trader-avatars`（交易大师·虚拟对话）

**细分功能拆解**
| 细分功能 | 端点/机制 | 相关 Skill | 相关专家 |
|---|---|---|---|
| 多空/风控协同出结论 | `/api/llm` 多轮 | `wb-finance-skill` ⭐ | `ai-hedge-fund` 全套 ⭐ |
| AI 投研问答 | `/api/llm`（Ollama/DeepSeek/OpenAI） | `westock-data` / `wb-finance-skill` | `a-share-advisor` |
| 交易人格对话（方法摘要/战例/语录） | 静态人格 + `/api/llm` | `prompt-master`（造人格 prompt） | 各投资大师 Agent |

**专家明细（ai-hedge-fund 团队，21 个）**
- 分析线：`fundamentals-analyst` · `technicals-analyst` · `valuation-analyst` · `sentiment-analyst` · `growth-analyst` · `news-sentiment-analyst`
- 风控/组合：`risk-manager` · `portfolio-manager`
- 大师线：`warren-buffett` · `charlie-munger` · `peter-lynch` · `michael-burry` · `nassim-taleb` · `cathie-wood` · `ben-graham` · `bill-ackman` · `stanley-druckenmiller` · `mohnish-pabrai` · `phil-fisher` · `aswath-damodaran` · `rakesh-jhunjhunwala`

**分派 prompt**
- 多智能体投研 → `「用 ai-hedge-fund 团队对 XX 标的并行跑基本面/技术/估值/情绪/风控，最后给 BUY/SELL/HOLD」`
- 人格对话 → `「用 warren-buffett + charlie-munger 两位大师视角点评 XX 股票」`

---

## 7. 数据可观测板块

**微应用**：`cache-insight`（缓存洞察）、`data-status-dash`（数据状态总览）、`data-explorer`（数据浏览器）、`health-board`（后端健康台）、`info-board`（API 一览）、`search-box`（智能搜索）

| 细分功能 | 端点 | 相关 Skill | 相关专家 |
|---|---|---|---|
| 后端进程内缓存可观测 | `/api/cache_stats` | `microapp-data-hub` ⭐ | — |
| 数据覆盖/质量/新鲜度 | `/api/data_status` | `offline-realdata-cache` ⭐ | — |
| 后端在线/端点/运行时长 | `/api/health` | `apphub-microapp-pipeline` | — |
| 端点清单/数据条目浏览 | `/api/info`、`/api/data` | `microapp-data-hub` | — |
| 全局搜索 | `/api/search` | `a-stock-data` / `westock-data` | — |

**分派 prompt** → `「用 microapp-data-hub 检查后端各数据源覆盖与新鲜度，列出降级/断点」`

---

## 8. 生活与效率板块

**微应用**：`desktop-pet`、`itinerary`（行程规划）、`health-check`（健康体检单）、`habit-tracker`、`focus-timer`、`recipe-box`、`workout-log`、`bookmark-manager`、`password-vault`、`expense-ledger`、`todo-list`、`countdown`、`unit-converter`、`cube-trainer`

| 细分功能 | 相关 Skill | 相关专家 |
|---|---|---|
| AI 行程生成（城市+天数+风格） | `itinerary` 自带 + `/api/itinerary/generate` | — |
| 本地数据工具（打卡/记账/待办/书签） | `interactive-dashboard-builder` / `frontend-design` | — |
| 3D 虚拟魔方（2/3/4/5 阶） | `frontend-spec` / `three.js` 内联 | — |
| 清单/热点数据可视化 | `data-visualization` / `interactive-dashboard-builder` | — |

**分派 prompt** → `「用 frontend-design 给「行程规划」做一版更精致的零依赖单文件 UI」`

---

## 9. 创意 · 3D · 主题板块

**微应用**：`dim-convert`（2D⇄3D 互转台）、`theme-studio`（主题工坊）、`code-teacher`（小狐狸讲代码）

| 细分功能 | 相关 Skill | 相关专家 |
|---|---|---|
| 2D 图→3D 立体（轮廓挤出）+ 云端图生3D（HuggingFace） | `3D模型与视频特效` ⭐ | `ardot-design-generator` |
| 3D 场景→导出 PNG/GLB | `3D模型与视频特效` / `frontend-design` | — |
| 主题配色切换/导出 | `ui-ux-pro-max` ⭐ / `frontend-design` | `design-to-code` |
| 代码讲解（生活类比/童趣版） | `prompt-master` / `humanizer` | — |
| 截图/设计稿→UI | `image-to-ui` / `design-to-code-workflows` | `design-to-code` |

**分派 prompt** → `「用 3D模型与视频特效 把这张图生成 3D 模型」` / `「用 ui-ux-pro-max 给主题工坊新增 3 套配色」`

---

## 10. 工程与交付板块（跨板块底座）

**对象**：整个大厅 `index.html` + `backend/app.py` + `verify_all.py` + 57 个微应用

| 细分功能 | 相关 Skill | 相关专家 |
|---|---|---|
| 新增微应用流水线（注册+生成+测试） | `apphub-microapp-pipeline` ⭐ | — |
| 真实数据中枢（Flask 统一后端） | `microapp-data-hub` ⭐ | — |
| 离线真实缓存（关后端也能看真数据） | `offline-realdata-cache` ⭐ | — |
| 找真缺陷/静默失败（锐评迭代） | `silent-failure-defect-hunt` ⭐ | — |
| 源码级防回退护栏（AST） | `ast-invariant-guard` | — |
| 安全 JSON API（防 HTML/堆栈泄露） | `flask-secure-json-api` ⭐ | — |
| SDD+TDD 规范驱动开发 | `sdd-tdd` | — |
| 巨型模块拆分 | `split-god-module` | — |
| Python AST 安全批量编辑 | `ast-safe-edit` | — |
| Windows 无窗口启动器 | `windows-bat-windowless-launcher` | — |
| 双机 git 安全红线 | `dual-machine-git-safety` | — |
| GitHub 操作 | `github`（需 conn） | — |
| 交付前真阻断闸门 | `delivery-no-pseudoblock` | — |
| 自驱开发循环 | `self-driving-dev` | — |
| 进度文档 / 交接文档 | `progress-doc` / `handoff-doc` | — |
| 数据可视化 / 看板 | `data-visualization` / `interactive-dashboard-builder` | — |
| 前后端全栈 | `fullstack-dev` / `frontend-spec` | — |

**分派 prompt**
- 锐评迭代 → `「用 silent-failure-defect-hunt 对 App Hub 做 N 轮：每轮找一真缺陷→修复→验证→提交」`
- 加新微应用 → `「用 apphub-microapp-pipeline 新增一个 XXX 微应用并接入后端真实数据」`
- 护栏 → `「用 ast-invariant-guard 给这个项目加一条源码级防回退护栏」`

---

## 附：跨板块「金融数据 / 文档」通用 Skill 池

| 类别 | Skill |
|---|---|
| 金融数据（首选） | `westock-data` ⭐ / `wb-finance-skill` / `neodata-financial-search` / `westock-tool` |
| A股数据工具包 | `a-stock-data` ⭐ / `a-share-daily-review` / `ashare-short-term-trading` |
| 期货 | `futures-combo` ⭐ |
| 日历/事件 | `invest-calendar` |
| 财经资讯 | `daily-financial-news` / `wechat-article-search` |
| 量化回测 | `onequant-backtest`（quant-backtest-strategy） / `quant-signal-landing-sop` |
| 文档交付 | `tencent-docx` / `tencent-pptx` / `tencent-docs-sheetagent` / `pdf` / `markitdown` / `xlsx` |
| 图表/流程图 | `data-visualization` / `mermaid-diagram` |

---

## 附：专家中心（Expert）全量清单（可直接点名）

| 专家包 | 专家（Agent） | 适用板块 |
|---|---|---|
| `a-share-analysis` | `a-share-advisor`⭐ 总入口 / `morning-briefing` / `portfolio-diagnosis` / `sector-screening` / `smart-money-tracker` / `stock-research` / `thematic-hunter` | 1–5 |
| `ai-hedge-fund` | 21 个（见板块 6 明细） | 6 |
| `ardot-design-generator` | ardot 设计助手 / image-to-ui / image-understanding | 9 |
| `design-to-code` | design-to-code-workflows / design-critique / design-handoff / design-system / user-research / ux-copy | 9 |
| `ppt-implement` | PPT 实现 | 10 |
| `finance-data` | westock-data / neodata / westock-tool / wb-finance | 1–6 |
| `data` | data-visualization / data-analysis-workflows / data-exploration / statistical-analysis / interactive-dashboard-builder / sql-queries | 7、10 |

---

*生成：App Hub 自主迭代 R88 ｜ 口径：以大厅 `APPS` 数组 + 后端真实端点 + 已安装 Skill/专家清单为准。*
