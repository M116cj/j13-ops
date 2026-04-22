# ADR 2026-04-22 — Family-Aware Strategy Policy Layer v0

## What was decided
建立 thin policy layer 將 family → signal-generation parameter 的映射固化為單一 source of truth，取代「每次實驗手動輸入正確 ARM_\*」的記憶管理。

## Why
- 前輪實驗已建立 family-specific parameter truths (Volume 250×0.90 / Breakout 500×0.80)
- 若繼續以 ARM_\* env 作主要控制面，多家族並存時會有 silent routing drift 風險
- 必須把驗證過的參數固化進 registry，future 實驗透過 policy layer 路由

## Design (three thin components)
1. **Registry** (`config/family_strategy_policy_v0.yaml`) — 唯一 SoT
2. **Resolver** (`engine/policy/family_strategy_policy_v0.py`) — 純函數 (registry, family_id, mode) → policy dict
3. **Integration wrapper** (`family_strategy_policy_integration_v0.py`) — CLI + patch `css.generate_alpha_signals` + 3-layer proof (banner + first-call + JSONL)

## What was rejected
- 第二個 runner（會重複執行邏輯）→ 改為 thin policy layer
- Fuzzy / contains / partial family name matching → 改為顯式 alias table
- Wrapper 內嵌 family→param 常數 → 改為 registry-only (wrapper 拒 ARM_\*)
- Auto-promote 重複命中的 candidate_test 為 active → 保留 manual registry promotion，決策分離

## Adversarial (Q1 五維)
- **Input boundary**: alias 表顯式、mode ∈ {research, production} 閉集、family_id 不在表內 → 'unknown' placeholder
- **Silent failure**: schema validation on load; resolver 在非法 route_status 上 raise
- **External dep**: yaml parse 失敗 → `PolicyRegistryError` abort
- **Concurrency**: registry 不可變；resolver 純函數，無共享狀態
- **Scope creep**: decision layer only — 不跑 runner / backtest

## Research
- 421-3 prior truth (Volume YES / Breakout NO) → registry 正當
- min_hold ablation 確認 60 是正確 floor → registry 寫死 60
- 不做新 sweep，僅將已驗證結果固化

## Q1 / Q2 / Q3
- Q1: 7/7 resolver 測（A/B/C/D + E/F alias + G unknown） + 8/8 exception overlay 測
- Q2: schema validation + collision check + fallthrough integrity
- Q3: 三檔合計 ~500 行，無第二套執行邏輯

## Consequences
- 所有 future 實驗用 `--family-id X --policy-mode research` 啟動
- 加 family 只需動 registry，不動 execution code
- candidate_test / candidate_exception overlay 機制可延伸至任何家族實驗
