# P5: signal-router

## 一句話說明
信號中央路由器：zangetsu + amadeus 的輸出一鍵分發到 Telegram、自動交易、X 貼文、Discord。

## 核心想法
目前 zangetsu 和 amadeus 各自產出信號，但「最後一哩路」——分發到不同目的地——是重複的膠水代碼。
signal-router 是一個事件驅動中樞：信號進來，根據路由規則同時推送到多個 sink。
新增目的地只需寫一個 Sink plugin，無需改動信號源。符合 Open/Closed 原則。

## 用到的現有技能
- zangetsu 信號輸出格式
- amadeus 信號輸出格式
- Telegram bot（現有基礎設施）
- X API（現有帳號）
- Python asyncio（並發推送）

## 技術棧
- Python 3.12 + asyncio
- Redis Streams（信號佇列，解耦 source 與 sink）
- Plugin 架構（每個 sink 是獨立 class）
- Telegram Bot API
- X API v2（tweepy）
- Discord Webhook
- FastAPI（可選：webhook 接收外部信號）

## MVP 範圍（最小可行版本）
1. 兩個 Source plugin：zangetsu poller + amadeus poller
2. 三個 Sink plugin：Telegram channel push、X post、log to file
3. 路由規則 YAML：`source: zangetsu → sinks: [telegram, x]`
4. 信號格式標準化為統一 schema（方向、置信度、標的、時間）
5. 單一 Docker container 跑通

## 架構圖（文字版）
```
[zangetsu]  [amadeus]  [external webhook]
     |           |              |
     +-----------+--------------+
                 |
         [Signal Normalizer]
                 |
         [Redis Stream: signals]
                 |
         [Router + Rule Engine]
        /    |       |       \
[Telegram] [X Post] [Discord] [Auto-Trader (P1)]
```

## 難度評估
- 複雜度: 2/5
- 預估時間: 3-5 天
- 技能缺口: 無（純整合現有技能）

## 潛在價值
- 商業: 本身不直接收費，但大幅降低 P2 運營成本，提升 P1 執行速度
- 技術: 可複用的 plugin 路由架構，適用所有未來信號類項目
- 組合效應: P1、P2、P4 的共同基礎設施；P6 可作為一個 sink（轉發到 API）

## 相依項目
- zangetsu (信號來源)
- amadeus (信號來源)
- P1 crimson-zangetsu-hybrid（作為 auto-trader sink）
