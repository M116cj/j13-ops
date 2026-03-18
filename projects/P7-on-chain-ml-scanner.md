# P7: on-chain-ml-scanner

## 一句話說明
將 zangetsu 的 ML 流水線應用於 BSC 鏈上交易數據，自動偵測鯨魚動向與聰明錢模式。

## 核心想法
OHLCV 是 zangetsu 的原始輸入，但鏈上數據有更原始的信號：大額錢包轉移、DEX 鏈上流動性變化、智能合約交互模式。
將這些特徵工程化後，套用 zangetsu 的 LightGBM + ELO 架構訓練鏈上版本。
輸出：「地址 0xABC 在過去 1 小時累積 500 BNB 進入某代幣，置信度 73% 可能引發 5% 以上漲幅」。

## 用到的現有技能
- zangetsu ML 流水線（特徵工程 + LightGBM + ELO）
- BSC 合約互動（ethers.js / web3.py）
- Solidity 理解（解析 ABI 事件）
- Telegram bot（告警推送）
- ATR（波動度基準）

## 技術棧
- Python 3.12
- web3.py（BSC 節點訂閱）
- BSC Archive Node 或 QuickNode（歷史數據查詢）
- LightGBM（分類模型）
- Pandas + feature engineering pipeline
- PostgreSQL（地址行為歷史）
- Redis（即時事件緩衝）
- Telegram bot（告警）

## MVP 範圍（最小可行版本）
1. 監控 BSC 上 TOP 10 代幣的大額轉移（> 100 BNB 等值）
2. 特徵：轉移金額、發起地址歷史行為、時間序列積累速率
3. LightGBM 訓練（目標：3 小時內價格上漲 > 3%）
4. 置信度 > 60% → Telegram 告警
5. 回測：過去 90 天數據，精準率 > 55%

## 架構圖（文字版）
```
[BSC Node WebSocket]
    |
[Event Filter: Transfer, Swap, AddLiquidity]
    |
[Feature Extractor]
    |-- wallet age, tx history
    |-- accumulated flow (1h, 4h, 24h)
    |-- DEX liquidity delta
    |
[LightGBM Scanner Model]
    |
[ELO Model Selector] (多幣種模型評分)
    |
confidence > threshold?
    |
[Telegram Alert] + [Log to DB]
    |
[Backtester] (offline, 90d historical)
```

## 難度評估
- 複雜度: 4/5
- 預估時間: 2-3 週
- 技能缺口: BSC Archive Node 數據獲取成本（QuickNode 費用）；鏈上特徵工程（新領域，需研究）

## 潛在價值
- 商業: 鏈上告警訂閱 $30-100/月；與 P2 捆綁為「加密全方位情報」
- 技術: OHLCV → 鏈上數據的 ML 遷移，技能大幅擴展
- 組合效應: 信號可進入 P5 signal-router；可強化 P4 DAO 的 DeFi 決策

## 相依項目
- zangetsu ML 架構（複用特徵工程框架）
- BSC 節點訪問（QuickNode 或自建）
- P4 ai-chain-trader-dao（數據互補）
