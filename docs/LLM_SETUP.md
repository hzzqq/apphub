# App Hub · 真 LLM 接入指南（AI 生成微应用）

> 面向 `/api/gen_app`（AI 生成微应用）与 `/api/llm`（通用对话）。
> 目标：让「描述 → 生成零依赖单文件 HTML」真正由大模型驱动；**LLM 不可用时自动降级为规则模板，闭环永不中断**。

---

## 1. 三条接入路径（从省事到强力）

### ① 本地 Ollama（默认 · 免费 · 免 Key · 断网可用）

```bash
# 1) 安装并启动
ollama serve

# 2) 拉取一个模型（默认期望 qwen2.5:3b）
ollama pull qwen2.5:3b

# 3) 直接启动后端即可，无需任何环境变量
python backend/app.py
```

`LLM_PROVIDER` 默认值就是 `ollama`，所以**装好模型后什么都不用配**。

> 若想换个已安装的模型：`set LLM_MODEL=llama3.2`（Windows）或 `export LLM_MODEL=llama3.2`（mac/Linux）。

### ② DeepSeek（便宜 · 需 Key）

```bash
set LLM_PROVIDER=deepseek
set LLM_API_KEY=sk-xxxxxxxx
set LLM_MODEL=deepseek-chat
python backend/app.py
```

### ③ OpenAI 兼容网关（通义 / 自建 vLLM / llama.cpp / OpenRouter …）

```bash
set LLM_PROVIDER=custom
set LLM_BASE_URL=https://your-gateway.example.com/v1
set LLM_API_KEY=xxxxxxxx
set LLM_MODEL=qwen-plus
python backend/app.py
```

`LLM_BASE_URL` **只写到 `/v1`**，不要带 `/chat/completions`（后端会自动拼）。
`LLM_PROVIDER=openai` 时同理，不设 `LLM_BASE_URL` 则默认 `https://api.openai.com/v1`。

---

## 2. 环境变量总表

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` / `deepseek` / `openai` / `custom` / `disabled` |
| `LLM_BASE_URL` | 空（ollama 用 `http://localhost:11434/v1`） | 自定义网关根地址 |
| `LLM_API_KEY` | 空 | 云端 Key；`ollama` 下无需设置 |
| `LLM_MODEL` | `qwen2.5:3b` | 模型名，必须与服务端实际可用模型一致 |
| `LLM_CACHE_TTL` | `3600` | 相同（model+messages）结果缓存秒数，省 token |
| `LLM_CACHE_MAX` | `256` | 缓存条目上限（FIFO 淘汰），防长时间运行 OOM |

> `LLM_PROVIDER=disabled` 会**完全跳过 LLM 调用**，只走规则模板（离线演示/排查用）。

---

## 3. 状态自检：`GET /api/llm/status`

```bash
curl http://127.0.0.1:8787/api/llm/status
```

返回字段：`provider` `model` `base_url` `keyed` `disabled` `available` `reachable` `reason` `hint`

三种典型结果：

| available | reachable | 含义 | 处理 |
|---|---|---|---|
| `true` | `true` | 真 LLM 已连接，可正常生成 | — |
| `false` | `true` | 服务**在**，但请求失败（最常见：模型未拉取 / Key 无效） | 看 `hint`，例如执行 `ollama pull <model>` |
| `false` | `false` | 服务**不可达**（Ollama 没启动 / 域名或 Key 错） | 看 `reason` 与 `hint` |

示例（Ollama 已启动但未拉模型）：

```json
{
  "available": false,
  "reachable": true,
  "provider": "ollama",
  "model": "qwen2.5:3b",
  "reason": "LLM 服务已响应但请求失败（HTTP 404）：{\"error\":{\"message\":\"model \\\"qwen2.5:3b\\\" not found, try pulling it first\"}}",
  "hint": "模型未拉取：先执行 `ollama pull qwen2.5:3b`（或把 LLM_MODEL 改成已安装的模型）"
}
```

大厅「🤖 AI 生成」模态框打开时会自动请求该端点，并在顶部显示徽章：
🟢 真 LLM 已连接 / 🟡 未就绪（将降级）/ ⚪ 离线规则模式。

---

## 4. 降级行为（`POST /api/gen_app`）

返回 `source` 与 `source_detail`：

| source | source_detail | 含义 |
|---|---|---|
| `llm` | `llm_ok` | 真 LLM 产出，且已通过零依赖门禁 |
| `rule` | `rule:llm_disabled` | `LLM_PROVIDER=disabled` |
| `rule` | `rule:llm_unavailable:<错误>` | LLM 调用异常（不可达/超时/报错） |
| `rule` | `rule:llm_output_invalid` | LLM 有返回，但内容未通过零依赖门禁 |

**零依赖门禁**（`_gate_zero_dep`）对 LLM 产出与人工产出同一标准：
- 禁止 `<script src=...>`（必须内联）
- 必须含 `<html>` / `<body>` 结构
- 内容不得短于 200 字符

> 关键：**无论走哪条路都产出可用的 HTML**，只是退化为规则模板，闭环不会断。
> 前端会把 `rule:` 开头的 `source_detail` 显式提示为「已降级为规则模板」。

---

## 5. 安全约定

- **Key 只存服务端环境变量**，绝不下发到浏览器；浏览器 App 永远不直连 LLM（会暴露 Key 且被 CORS 拦）。
- 本地地址（`localhost` / `127.0.0.1`）的请求**自动绕过 HTTP 代理**，避免公司代理接管后返回 404/502 导致本地 Ollama 被误判为不可达。
- 所有用户输入经 `cap_len` 截断后再拼进 prompt，防止超长输入打爆 token。

---

## 6. 排障清单

| 现象 | 原因 | 解决 |
|---|---|---|
| 提示「模型未拉取」 | Ollama 起来了但没模型 | `ollama pull qwen2.5:3b` |
| `reason` 是 Connection refused | Ollama 没启动 | `ollama serve` |
| HTTP 401/403 | Key 无效或过期 | 换 `LLM_API_KEY` |
| 一直 `source=rule` 且 `llm_output_invalid` | 模型太小/指令遵循差，产出不是完整 HTML | 换更大的模型（如 7B+ 或云端模型） |
| 公司网络连不上云端 | 代理拦截 | 云端 Key 走 HTTPS 一般正常；本地 Ollama 已自动绕过代理 |
