# P3: qbeyer-trader-persona

## 一句話說明
Fine-tune 出一個懂量化交易的 LLM 人格，部署為 Telegram 交易教練聊天機器人。

## 核心想法
以 zangetsu 的歷史交易記錄、決策日誌、回測報告為訓練語料，搭配量化交易領域知識，
LoRA fine-tune Qwen2.5-7B，打造「Q. Beyer」——一個能解釋自己每個信號背後邏輯的交易人格。
用戶問「為什麼今天做多 BTC？」→ 它能用 ELO、ATR、regime 等概念回答，而非黑盒。

## 用到的現有技能
- LoRA fine-tune（已有 Qwen2.5 + llama.cpp 流程）
- Qwen2.5-7B 本地模型
- RTX 3080（訓練硬體）
- Telegram bot（部署界面）
- zangetsu 決策數據（訓練語料來源）

## 技術棧
- Qwen2.5-7B-Instruct（基礎模型）
- LoRA / QLoRA（fine-tuning，via Unsloth 或 LLaMA-Factory）
- llama.cpp 或 Ollama（推理服務）
- python-telegram-bot（用戶界面）
- JSONL 格式訓練數據（問答對）
- Weights & Biases（訓練監控，可選）

## MVP 範圍（最小可行版本）
1. 收集 50-100 條高質量訓練數據（信號解釋 Q&A 格式）
2. LoRA fine-tune Qwen2.5-7B，loss < 0.3
3. Ollama 本地部署
4. Telegram Bot：用戶發問 → 調用本地 Ollama API → 回覆
5. 限制：每用戶每天 10 條免費，付費解鎖無限

## 架構圖（文字版）
```
[zangetsu logs] + [trading Q&A corpus]
        |
   [JSONL Dataset]
        |
   [LoRA Fine-tune on RTX 3080]
        |
   [Qwen2.5-7B-qbeyer.gguf]
        |
   [Ollama Server (local)]
        |
[Telegram Bot] <-- user questions
        |
[Rate Limiter] --> [Stripe paywall for unlimited]
```

## 難度評估
- 複雜度: 3/5
- 預估時間: 1.5-2 週
- 技能缺口: 訓練數據工程（量化 Q&A 對的質量決定效果）；Unsloth/LLaMA-Factory 框架選擇

## 潛在價值
- 商業: 訂閱加值（P2 高階方案）；獨立收費教練 bot $30-100/月
- 技術: 領域 LLM fine-tune 完整流程，可複用至其他人格
- 組合效應: 可整合進 P8 ops-console 作為 AI 助理；與 P2 捆綁銷售

## 相依項目
- zangetsu 歷史數據與決策日誌
- RTX 3080 本地訓練環境
- Ollama 推理服務
