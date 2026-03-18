# P6: zangetsu-api

## 一句話說明
將 zangetsu 冠軍模型信號封裝為 REST API，外部 bot 和應用可付費查詢即時交易建議。

## 核心想法
zangetsu 的 ML 推理已在本地跑通，但每次查詢都要直接存取模型太重。
zangetsu-api 是一個輕量推理服務：接受 symbol 查詢，返回標準化信號 JSON。
API Key 訂閱制：免費層（每天 10 次），付費層（每天 1000 次，$20/月），企業層（無限，$200/月）。

## 用到的現有技能
- zangetsu LightGBM 錦標賽 + ELO 校準（推理核心）
- Isotonic calibration（置信度輸出）
- Kelly 公式（槓桿建議）
- Docker（容器化部署）
- Tailscale + CF Tunnel（安全暴露服務）

## 技術棧
- FastAPI（API 框架）
- Python 3.12
- zangetsu 推理模型（.pkl / .lgbm）
- Redis（API Key 限流 + 快取近期信號）
- PostgreSQL（用戶 + API Key 管理）
- Stripe API（訂閱計費）
- Docker + Cloudflare Tunnel（部署）
- Prometheus（請求量監控）

## MVP 範圍（最小可行版本）
1. `GET /signal?symbol=BTCUSDT` → `{side, confidence, leverage_suggestion, stop_loss_pct, timestamp}`
2. API Key 驗證（Header: `X-API-Key`）
3. Redis 限流（免費 10 次/天）
4. /dashboard 頁面：查看自己的 API Key 用量
5. Stripe checkout：升級付費方案
6. 本地 Ubuntu 部署 + CF Tunnel 暴露

## 架構圖（文字版）
```
Client (bot/app)
    |
    | GET /signal?symbol=BTC
    v
[FastAPI Server]
    |           \
[API Key Check]  [Redis Rate Limiter]
    |
[zangetsu Inference Engine]
    |-- LightGBM ensemble
    |-- ELO champion selection
    |-- Isotonic confidence
    |-- Kelly leverage
    |
[Response JSON] --> client
    |
[Prometheus metrics] --> [P8 ops-console]
```

## 難度評估
- 複雜度: 3/5
- 預估時間: 1-2 週
- 技能缺口: FastAPI 生產部署最佳實踐（rate limiting、auth middleware）；Stripe Subscription webhooks

## 潛在價值
- 商業: 50 付費用戶 × $20 = $1,000/月 MRR；B2B 企業方案可到 $200+
- 技術: API 產品化完整流程，可複用給 amadeus-api
- 組合效應: P2 訂閱可包含 API 訪問；P5 signal-router 可作為默認客戶端；P8 監控此服務健康

## 相依項目
- zangetsu (推理模型文件)
- ops-agent 基礎設施
- CF Tunnel 現有配置
