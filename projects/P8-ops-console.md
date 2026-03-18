# P8: ops-console

## 一句話說明
j13 基礎設施的統一 Web 儀表板：所有項目狀態、交易 PnL、模型訓練進度、ops-agent 告警，由本地 Ollama AI 助理回答問題。

## 核心想法
隨著項目增多（zangetsu、P1-P7），j13 需要一個「指揮中心」來鳥瞰全局。
ops-console 聚合所有服務的 Prometheus metrics + 日誌 + 狀態，呈現在單一 Web UI。
內嵌 Ollama 聊天框：「zangetsu 今天盈虧多少？」→ AI 查詢數據庫並回答，不需手動翻報表。

## 用到的現有技能
- Ollama（本地 LLM，已有）
- Docker + Portainer（現有基礎設施）
- Prometheus（現有監控基礎）
- ops-agent（現有告警系統）
- Telegram bot（可作為 ops-console 的移動端入口）

## 技術棧
- Next.js 14（Web UI）
- FastAPI（後端 API 聚合層）
- Ollama + qwen2.5:7b（本地 AI 助理）
- Prometheus + Grafana Embed（指標圖表）
- WebSocket（即時狀態更新）
- PostgreSQL（聚合歷史數據）
- Docker Compose（全棧部署）
- Tailscale（僅局域網訪問，不對外暴露）

## MVP 範圍（最小可行版本）
1. 首頁儀表板：4 個狀態卡片（zangetsu PnL、P1 執行狀態、P6 API 請求量、系統健康）
2. AI 聊天框：連接 Ollama，帶有數據庫查詢工具調用能力
3. 告警頁面：ops-agent 的歷史告警列表
4. 僅 Tailscale 網段可訪問（安全優先）
5. 移動端響應式（手機瀏覽）

## 架構圖（文字版）
```
[Browser / Mobile]
    |
[Next.js Frontend]
    |
[FastAPI Backend]
    |------[PostgreSQL: 聚合數據]
    |------[Prometheus API: 即時指標]
    |------[ops-agent: 告警數據]
    |------[zangetsu DB: PnL 數據]
    |------[P6 API metrics]
    |
[Ollama qwen2.5:7b]
    |
[Tool Calls: SQL query, metrics fetch, log search]
    |
[AI Response] --> [Frontend Chat]

[Tailscale VPN] -- 隔離所有外部訪問
```

## 難度評估
- 複雜度: 3/5
- 預估時間: 1.5-2 週
- 技能缺口: Next.js（若偏好 Python 可改 Streamlit，降低複雜度到 2/5）；Ollama Tool Calling 設定

## 潛在價值
- 商業: 不直接變現，但大幅降低 j13 運營認知負擔
- 技術: 全棧 AI-native 儀表板，RAG + tool-calling 完整實踐
- 組合效應: P1-P7 所有項目的監控終點；可擴展為多租戶 SaaS（給其他量化交易者）

## 相依項目
- Ollama 本地服務（已有）
- Prometheus（ops-agent 現有基礎）
- 所有 P1-P7 項目（數據來源）
- Tailscale（安全訪問）
