# App Hub · 零依赖微应用集合

26 个**单文件 HTML** 小工具，双击即开、数据本地存储（localStorage），零外部依赖、零构建。
覆盖金融投研与生活效率两大类，并配一个**统一后端**为金融类 App 提供真实行情/数据。

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
3. 后端默认 `OFFLINE_MODE=True`（沙箱禁网环境返回结构化静态样本，可离线跑/验证）；
   在**有网机器**上把 `app.py` 顶部的 `OFFLINE_MODE` 改为 `False`，即自动抓取 akshare/新浪真实数据。

---

## 应用清单（26 个）

### 金融类（13）
| 应用 | 说明 |
|---|---|
| 股事贴 stocknote | 个股利好/利空事件卡片，按股票分组、搜索、JSON 导入导出 |
| 价格预警 price-alert | 监控股票价格，突破阈值浏览器弹窗 + 微信/企业微信提醒 |
| K线形态速查卡 kpattern | 14 种 K 线形态图解与多空信号 |
| 市场情绪温度计 mood-meter | 从 2008 起 A股牛熊基准叠加每日情绪打分 |
| 财报跟踪器 earnings-calendar | 财报披露日历，临近高亮，可查往年财报 |
| 期库镜 futures-inventory | 期货 K线×库存双轴透视，皮尔逊相关性 + 全球合计 |
| 盘前收盘速读 market-brief | A股盘前策略与收盘复盘要点卡 |
| 牧羊人指标 shepherd-index | 复刻股海牧羊人 8 项情绪指标 + 温度计打分 |
| 黑天鹅预警 blackswan | 宏观黑天鹅时间轴 + 个股业绩雷/监管异动扫描 |
| 板块轮动仪 sector-rotation | 申万行业涨跌与轮动强度可视化 |
| ETF筛选器 etf-picker | 按类型/规模/收益筛选 ETF |
| 持仓体检 holdings-check | 持仓集中度/行业集中/浮亏 4 维诊断 |
| 智能条件单 smart-order | 涨破/跌破触发规则，浏览器 Notification 弹窗 |

### 生活 / 效率类（13）
| 应用 | 说明 |
|---|---|
| 桌面宠物豆豆 desktop-pet | 心情/饱食/精力三态宠物，喂食玩耍 |
| 行程规划卡 trip-planner | 按城市+天数+风格生成每日骨架 |
| 健康体检单 health-check | 个人/品牌 4 维自检清单 + 短板诊断 |
| TradingAgents trading-agents | 模拟投行投研团队多智能体协同出结论 |
| 主题工坊 theme-studio | 类似 Miku Codex 的主题更换器，一键切换并导出配色 |
| 小狐狸讲代码 code-teacher | 输入代码，输出妈妈版/弟弟版/标准版解释 |
| 习惯打卡 habit-tracker | 每日打卡 + 连续天数 + 30 天热力图 |
| 专注番茄钟 focus-timer | 25/5/15 分钟番茄钟，统计番茄数 |
| 菜谱收藏盒 recipe-box | 收藏菜谱，按分类与食材搜索 |
| 健身记录 workout-log | 记录训练组数/重量，统计近 7 天容量 |
| 书签收藏家 bookmark-manager | 收藏网页/工具/论文，按标签检索 |
| 密码保险库 password-vault | 本地生成强密码 + 保存账号，数据不上传 |
| 随手记账本 expense-ledger | 记录收支，分类统计，月度结余 |

---

## 统一后端（`backend/`）

Flask 服务，为前端微型 App 提供真实数据。行情源模仿 StockSignal（新浪 `hq.sinajs.cn` + akshare 兜底）。

**主要端点**（完整清单见 `/` 或 `backend/README.md`）：
- `/api/futures` 期货 K线×库存（单品种 / 全球合计）
- `/api/corr_top` 全品种皮尔逊相关性 Top N（自动选最相关库存口径）
- `/api/quote` 股票实时行情
- `/api/shepherd` 牧羊人 8 项情绪指标 + 综合温度
- `/api/blackswan` 黑天鹅事件 + 个股业绩雷扫描
- `/api/earnings` 往年财报
- `/api/search` 股票/基金/期货/指数搜索
- `/api/etf` `/api/sector` ETF/板块行情
- `/api/data` 工具类 App 的本地结构化 JSON（白名单防穿越）
- `/api/trading_agents` `/api/code_teacher` `/api/theme` 新 App 数据
- `/api/health` 存活检查

**三级数据加载（前端约定）**：真实后端 → 本地静态样本（`backend/data/*.json`）→ 内置兜底，永不空白/随机。

**安全**：`/api/data` 仅允许白名单文件，目录穿越/越权均返回 400；CORS 已放开供本地前端调用。

---

## 开发新 App

1. 在大厅 `index.html` 的 `APPS` 数组加一行（`dir`/`name`/`ico`/`cat`/`tag`/`desc`）。
2. 新建 `<dir>/index.html`，**单文件内联 CSS/JS**，不引用任何外部资源。
3. 如需真实数据：读取 `localStorage.getItem("hub_api")` 作为后端根地址，拼对应 `/api/*` 端点；
   失败时回退本地静态样本或内置演示，保证离线可用。

---

## 质量门禁

```bash
python verify_all.py
```

一键校验：
- 前端 26 个 App 的内联 JS 语法（`node --check`）
- 各 App 的 `test/run.js` 前端逻辑单测（如 futures-inventory、stocknote、blackswan）
- 后端全部端点冒烟（离线模式）
- `backend/data/*.json` 与 `/api/data` 白名单一致性

后端契约测试另见 `backend/test_app.py`（`pytest -q`）。
