# ADR 2026-04-22 — Volume C6 Exception Overlay (β path)

## What was decided
用 policy-layer overlay（`candidate_exception` 型態）把 Wilson WR 0.48 trial 驗出的 2 個 (symbol, formula) pair 做 narrow allow-list 放行：BTCUSDT + DOTUSDT × `decay_20(volume)`。**不** 動 global Wilson 0.52 floor，**不** 動 main registry 的 volume active route。

## Why
- 這 2 cells 符合 4/6 YES 條件（100% Acceptable、+2.27 val sharpe、100% train-val 一致），僅差 count + breadth
- 全 gate 放寬（G7）會吸收 46% junk（見 valgate audit）
- 個別放行（narrow allow-list）是品質 vs 風險 trade-off 最低的方案

## Design（6 個 hard boundary 全守）

1. **overlay_kind = candidate_exception**（新 route_status，區分於 candidate_test）
2. **allow_list 雙軌 key**：formula string 為 primary，alpha_hash 為 defensive。Hash-only 不成立；formula 命中但 hash mismatch → warning
3. **Dual-track expiry**：`expires_at = 2026-07-22T00:00:00Z`（absolute、resolver fail-close）+ `review_by_date_hint = 2026-05-22`（informational）+ `review_after_event / expiry_after_event`（human-readable，warning only）
4. **overlay 不可 shadow main registry**（collision check 強制，U7 test 拒絕把 exception family 當 `--family-id` 直接跑）
5. **命中條件嚴格**：只有當 `first_gate_reached == a1_val_low_wr` 才 override；其他 gate 不啟動 override
6. **完整 JSONL proof**：hit / miss 皆寫 `exception_allow_list_hit / overlay_name / pair_key / evidence_tag / override_applied / fallthrough_to_main` 8 個欄位

## What was rejected
- Global Wilson floor 放寬 → 風險擴散至所有 family
- 自動升級 candidate_exception 為 active → 避免 silent promotion；升級須走獨立 ADR
- Fuzzy / contains family-id matching → 顯式 alias table only

## Adversarial

Unit 8/8 PASS：
- U1-U3 命中 / 符號誤 / 公式誤
- U4-U5 hash 正確 / hash mismatch warning
- U6 hash-only 被擋（不自動放行）
- U7 直接 `--family-id volume_c6_approved_exceptions` PolicyRegistryError
- U8 模擬 expired → resolver 自動 fail-close + warning

Full 140-cell verify：
- 2/2 allow_list hit + override
- 138/138 non-allow fallthrough
- **0 unexpected hits**
- Gate-outcome delta 完全被 2 個宣告例外解釋（A1_PASSED 2→4，val_low_wr 17→15）

## Research
- 衍生自 wilson_wr_048 trial → MIXED
- 使用 421-4/421-5 既建的 overlay 機制，擴展 `candidate_exception` 為第 4 種 route_status

## Q1 / Q2 / Q3
- Q1 五維 + 8/8 unit
- Q2 schema validation + collision check + expiry check + hash defensive
- Q3 wrapper-only、registry 未動、production source 零改

## Consequences
- 2 cells 在後續 Volume family runs 直接 survived_a1=True，不需手動記憶
- 2026-07-22 後 resolver 自動 fail-close（無須手動清 overlay）
- 2026-05-22 前 j13 需 human-review 是否延長/移除
- 若品質 drift（val_sharpe -50% / wilson < 0.45 / train-val 符號背離）→ 直接 rm overlay yaml

## Follow-ups / outstanding
- 需 Calcifer cron / Telegram notifier 在 `review_by_date_hint` 前 3 天提醒 j13（目前沒排）
- 若未來同 formula `decay_20(volume)` 在更多 symbol 驗出 Acceptable，可走「正式升級為 `volume_decay20_subfamily` active route」路徑（**另外 task**，不走此 overlay）
