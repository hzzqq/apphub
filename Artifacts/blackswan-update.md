# 黑天鹅预警 App 升级交付（第十轮）

## 已完成
按老板要求把「黑天鹅预警」从离线样本升级为可接入真实数据的工具，并新增全品类搜索。

### 后端 `E:\project\app\backend\app.py`（已增强）
- **`/api/blackswan?code=xxx`**：传入个股代码即触发**实时风险扫描**。真网时调 akshare 真抓：
  - 个股公告 `stock_individual_notice_report` + 业绩预告 `stock_yjyg_em` + 个股新闻 `stock_news_em`
  - 用风险词库（业绩雷/监管异动/减持/诉讼）识别命中，按「高危×35 + 中危×12」加权出 `risk_score` 与 `risk_level`（高危/中危/平稳）
  - 离线（沙箱禁网）回退演示扫描，保证可跑
- **`/api/search?q=&type=`**：支持 **股票 / 基金 / 期货 / 指数** 四类搜索
  - 真网：`stock_zh_a_spot_em` / `fund_etf_spot_em` 过滤全市场
  - 离线：内置示例库回退（茅台/沪铜等热门）
- 现有 6 端点：futures / corr_top / quote / shepherd / blackswan / search

### 前端 `E:\project\app\blackswan\index.html`（已增强）
- 新增「🔍 标的搜索 & 黑天鹅预警」面板：四类切换 + 输入框 + 搜索
- 搜索结果每行带「⚠️ 黑天鹅扫描」按钮，点后拉 `/api/blackswan?code=` 展示该标的风险等级、评分、命中公告/新闻明细
- 无后端时回退离线示例库，提示「配置后端可真实风控」
- 原有宏观事件时间轴、个股示例库、预警仪表盘、自定义录入均保留

### 验证
- 后端 test_client：四端点全通；`blackswan?code=600519` 返回 risk_level=中危；`search?q=茅台` 命中贵州茅台；`search?q=cu&type=futures` 命中沪铜
- 前端：JS 语法、搜索 UI、四类型切换、scanTarget、接口、离线回退 全部 PASS

## 工程边界（透明）
- 沙箱 Bash 禁网 → 后端默认 `OFFLINE_MODE=True`（离线样本/示例库）。**本地有网机器把 `OFFLINE_MODE=False` 跑后端**，`/api/search` 才真搜全市场、`/api/blackswan?code=` 才真抓公告/财报/新闻。

## 作品集现状
微型 App 累计 **16 个** + 统一后端（6 端点）。

## 后续可选项
- 后端接真实公告/新闻后，扩展「个股黑天鹅历史命中率」统计
- 继续抽 StockSignal 剩余页面（资金流向/策略回测/模拟交易/智能选股）
- 给搜索结果加「加入自选 + 持续监控」能力
