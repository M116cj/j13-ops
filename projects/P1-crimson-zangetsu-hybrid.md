# P1: crimson-zangetsu-hybrid

## 一句話說明
結合 King Crimson HFT 閃電執行引擎與 zangetsu ML 信號，在 Binance 進行毫秒級真實交易。

## 核心想法
zangetsu 產出高置信度信號（方向 + Kelly 倉位 + ATR 止損），King Crimson 負責 CLOB 掛單、滑點最小化與執行確認。
兩者透過共享 Redis 隊列解耦——信號層與執行層完全獨立，各自可單獨測試與替換。
目標：將 zangetsu 的預測優勢轉化為真實 PnL，消除手動執行延遲。

## 用到的現有技能
- zangetsu: LightGBM 錦標賽、ELO 校準、Kelly 倉位、Isotonic calibration
- CLOB/Binance API: 限價單、市價單、WebSocket 訂單流
- ATR 動態止損
- Docker + Tailscale 部署
- Telegram bot（執行通知）

## 技術棧
- Python 3.12（信號端）
- Rust 或 asyncio（執行端，低延遲）
- Redis Streams（信號隊列）
- Binance Futures REST + WebSocket API
- Docker Compose（信號 + 執行 + Redis 三容器）
- Prometheus + Grafana（執行延遲監控）

## MVP 範圍（最小可行版本）
1. zangetsu 輸出信號 → 寫入 Redis Stream
2. 執行引擎讀取信號 → Binance 下限價單
3. 成交後 → Telegram 通知（入場價、倉位、止損價）
4. 風控閘門：單筆最大損失 $X，日累計損失上限

## 架構圖（文字版）
```
[zangetsu ML] --signal--> [Redis Stream] --consume--> [King Crimson Executor]
                                                              |
                                              [Binance Futures API]
                                                              |
                                          [Position Manager + ATR Stop]
                                                              |
                                              [Telegram Alert] + [Prometheus]
```

## 難度評估
- 複雜度: 4/5
- 預估時間: 2-3 週
- 技能缺口: Rust asyncio 執行層（可先用 Python aiohttp，之後換 Rust）

## 潛在價值
- 商業: 直接交易獲利；若穩定可包裝成 P2 訂閱信號來源
- 技術: 端對端量化交易閉環，執行延遲工程
- 組合效應: P2 的信號來源、P6 的 API 後端、P8 的監控數據來源

## 相依項目
- zangetsu (regime_system v2.0.0)
- Binance CLOB 現有整合
- ops-agent 基礎設施
