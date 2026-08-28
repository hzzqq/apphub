# ETF 筛选器 · ETFPicker

零依赖、零构建、双击 `index.html` 即开的指数 ETF 筛选工具。

## 功能
- **多维筛选**：类型 / 行业（随类型联动）/ 最小规模 / 今年收益区间 / 最大费率 / 最大跟踪误差 / 关键词（名称或代码）。
- **排序**：点击表头按 代码/名称/类型/行业/规模/收益/费率/跟踪误差 排序，再次点击切换升/降序；筛选条件自动持久化。
- **自选**：★ 收藏，存 `localStorage`，可切「仅看自选」。
- **对比**：勾选 ☑ 加入对比，并排比较各字段，数值最优/最差高亮；支持「清空对比」。
- **导出**：当前结果、自选、对比均可导出 **CSV**（防公式注入）/ **JSON**（含导出时间等元数据）。
- **健壮性**：输入校验（收益下限>上限自动交换、负费率/误差归零）、空态提示、XSS 白名单转义（用户文案仅放开 `<b><i><u><em><strong><br>` 及安全 http(s) 链接）、无障碍（`label` / `aria-label` / `aria-sort` / `role=alert|status`）。

## 接真实数据（可选）
默认使用内置演示样本。若有后端，在 `index.html` 顶部把 `API_ROOT` 指向提供以下契约的服务即可，失败会自动降级到内置样本：

```
GET {API_ROOT}/api/etf  ->  { "ok": true, "offline": false,
  "rows": [ {code,name,type,industry,size,ret,fee,trackErr,issuer}, ... ] }
```

## 自测
```
node test/run.js
```
零依赖（仅 Node 内置 `vm`/`fs`），加载 `index.html` 内联脚本在最小 DOM 桩中断言纯逻辑，全绿即通过。
