# P2: quant-signals-sub

## 一句話說明
透過 Telegram 頻道販售 zangetsu + amadeus 的量化交易信號訂閱，月費 $10-50。

## 核心想法
將 zangetsu（加密貨幣）與 amadeus（預測市場）的日常信號封裝成付費 Telegram 頻道。
訂閱者每天收到格式化信號卡：方向、置信度、建議槓桿、止損位、預期持倉時長。
Stripe 或 TON 付款 → Bot 自動管理頻道訪問權限（到期自動踢出）。

## 用到的現有技能
- zangetsu 信號產出（已有）
- amadeus 預測市場信號（已有）
- Telegram bot (@macmini13bot 基礎設施)
- X API（同步發部分免費預覽信號）

## 技術棧
- Python（Bot 核心）
- python-telegram-bot v21
- Stripe API / TON Connect（付款）
- SQLite 或 PostgreSQL（訂閱者管理）
- APScheduler（定時推送信號）
- Telegram Channel + Invite Link 管理 API

## MVP 範圍（最小可行版本）
1. 免費公開頻道：每天 1 條信號預覽（含置信度模糊化）
2. 付費私人頻道：每天完整信號（BTC + ETH + 1 預測市場）
3. /subscribe 指令 → 產生付款連結 → 付款成功 → Bot 自動發邀請連結
4. 到期前 3 天提醒 → 未續費則踢出

## 架構圖（文字版）
```
[zangetsu] + [amadeus]
        |
   [Signal Formatter]
        |
   +----|----+
   |         |
[Free TG] [Paid TG Channel]
   |         |
[X post]  [Subscriber DB]
              |
         [Stripe/TON] <-- /subscribe
              |
         [Auto Invite / Kick Bot]
```

## 難度評估
- 複雜度: 2/5
- 預估時間: 1 週
- 技能缺口: Stripe Webhooks 或 TON Connect 整合（新，但文件完整）

## 潛在價值
- 商業: 100 訂閱者 × $20 = $2,000/月 MRR；低邊際成本
- 技術: 付費產品完整閉環（付款、訪問控制、自動化）
- 組合效應: P1 是信號來源，P3 可作為「AI 教練」加值，P6 是 API 版本

## 相依項目
- zangetsu (現有信號輸出)
- amadeus (現有信號輸出)
- Telegram bot 基礎設施
