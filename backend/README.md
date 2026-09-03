# 期库镜 / 价格预警 统一后端

为前端微型 App 提供**真实数据**的 Flask 服务。行情源模仿 StockSignal（新浪 `hq.sinajs.cn` + akshare 兜底）。

## 运行（在本机 / 有网环境）

```bash
cd E:/project/app/backend
pip install -r requirements.txt        # 首次安装依赖(Flask/flask-cors/akshare/pytest)
# 用隔离 venv 的 python
E:/.workbuddy/binaries/python/envs/default/Scripts/python.exe app.py
# 默认监听 http://127.0.0.1:8787
```

## 开发 / 测试

```bash
pip install -r requirements.txt
pytest -q test_app.py                  # 离线模式下接口契约测试(无需联网)
```

> 沙箱 Bash 默认禁网，故代码内置 `OFFLINE_MODE = True` 返回准真实样本（可离线跑、验证接口）。
> **在有网机器上把 `OFFLINE_MODE` 改为 `False`**，即自动调用 akshare 真抓 SHFE/LME/COMEX 库存 + 期货K线 + 股票实时行情。

## 接口

| 端点 | 参数 | 说明 |
|---|---|---|
| `/api/futures` | `symbol` `exchange` `start` `end` `mode=single\|global` | 期货K线收盘价 + 库存双轴数据；`global`=SHFE+LME+COMEX 全球合计 |
| `/api/corr_top` | `n` | 全品种皮尔逊相关性排名 Top N（按 \|r\| 降序） |
| `/api/futures_chain` | `symbol` `exchange` | 给定期货品种，返回跨品种相关性（原始+偏相关剔除大盘）+ 产业链传导报告（HTML） |
| `/api/quote` | `code`（带前缀，如 `sh600519`） | 股票实时行情（新浪+GBK+Referer，akshare 兜底） |

返回统一 JSON：`{ok, offline, data:[{date,close,inventory}], corr?, note?}`

## 期货库存 akshare 接口（已按 1.18.64 核对）

- 上期所：`futures_shfe_warehouse_receipt(symbol=...)`
- 大商所/郑商所：`futures_inventory_em(symbol=...)`
- COMEX：`futures_comex_inventory(symbol=...)`
- LME 外盘：`futures_foreign_hist(symbol=..., market="LME")`
- 期货K线：`futures_zh_daily_sina` / `futures_hist_em`

## 前端如何接

在 `futures-inventory/index.html` 与 `price-alert/index.html` 的「真实数据接口」里填 `http://127.0.0.1:8787`，
前端会请求 `/api/futures` 与 `/api/quote` 替换演示数据。

## 关于"强相关"的诚实说明

库存与价格通常呈**负相关**（库存降→利多→价涨），且不同品种/周期强弱不一。
本后端用皮尔逊 r 如实计算并排名，**绝不硬编强相关结论**。离线样本也按真实规律生成（铜类相关性最强）。
