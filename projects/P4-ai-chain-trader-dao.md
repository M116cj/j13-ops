# P4: ai-chain-trader-dao

## 一句話說明
在 BSC 上部署 DAO 合約，AI Agent 自動管理 DeFi 金庫，以 zangetsu 信號驅動鏈上交易決策。

## 核心想法
DAO 成員存入資金，AI Agent（鏈下 zangetsu + 鏈上執行器）根據信號在 PancakeSwap 或 GMX 上操作。
決策透明化：每筆交易附帶信號置信度哈希上鏈，成員可驗證 AI 的決策依據。
收益按份額分配，管理費 2% 作為 j13 收入。

## 用到的現有技能
- Solidity + Hardhat（BSC 部署）
- diamond-lottery 合約經驗（多合約架構）
- zangetsu ML 信號（決策來源）
- BSC 生態（Gas、PancakeSwap Router）
- Telegram bot（DAO 成員通知）

## 技術棧
- Solidity 0.8.x（Vault + DAO 合約）
- Hardhat（測試 + 部署）
- BSC Mainnet / Testnet
- PancakeSwap V3 Router（DEX 執行）
- ethers.js（鏈下 Agent 與鏈上互動）
- OpenZeppelin（AccessControl, ReentrancyGuard）
- Python（zangetsu 信號 → 觸發鏈上 TX）

## MVP 範圍（最小可行版本）
1. SimpleVault 合約：存入/提出 USDT，記錄份額
2. 鏈下 Agent：zangetsu 信號 → 呼叫 Vault.execute(swap params)
3. 白名單執行器模式（只有 Agent 地址可觸發交易）
4. 每筆交易事件帶 signalHash（置信度 + 時間戳 keccak256）
5. BSC Testnet 完整跑通，Mainnet 小倉位測試

## 架構圖（文字版）
```
[zangetsu signal] --> [Agent (Python/ethers.js)]
                              |
                    [BSC Vault Contract]
                      /            \
          [DAO Members]      [PancakeSwap Router]
          (deposit/withdraw)      (swap execution)
                              |
                    [onchain event: signalHash]
                              |
                    [Telegram: trade notify]
```

## 難度評估
- 複雜度: 5/5
- 預估時間: 3-4 週
- 技能缺口: DeFi 金庫合約安全審計（重入、Oracle 操縱、滑點攻擊）；GMX V2 整合（若選 perp）

## 潛在價值
- 商業: 管理費 2% + 績效費 20%；若 TVL 達 $100K = $2K/月管理費
- 技術: DeFi + AI Agent 完整鏈上閉環
- 組合效應: P1 的鏈下版本鏡像；P7 的鏈上數據可反饋給此項目

## 相依項目
- zangetsu (信號來源)
- diamond-lottery 合約架構經驗
- BSC 部署環境
