# 02 — Generation-Profile Intervention Taxonomy

範圍：把所有可能的 sparse-candidate intervention 分類。每一類標註
**design-only / dry-run only / safe future implementation candidate /
high-risk implementation candidate / forbidden without explicit j13
order**。

未審核透過任何 intervention class，本檔僅為設計目錄。

## 1. Class definitions

### 1.1 Profile budget shift（PB-SHIFT）

**意圖**：將 actual generation budget 在 profile 之間重新分配，例如
讓 sparse-prone profile 的 budget 降低、density-friendly profile
budget 提高。

- 機制：在 GP loop 啟動前（`arena_pipeline.py` 的 round dispatch）
  根據 dry-run allocation 結果調整 per-profile 的 generation share。
- 變動模組：`arena_pipeline.py`（generation budget allocation）、
  `alpha_engine` 的 round-level budget 設定。
- **Class**：HIGH_RISK_IMPL_CANDIDATE — 0-9R-IMPL 的核心對象，
  **必須**走 dry-run → CANARY → production gate sequence。
- **Forbidden until**：j13 explicit order + 0-9S CANARY pass。

### 1.2 Profile suppression（PB-SUPPRESS）

**意圖**：暫時把 SIGNAL_TOO_SPARSE_DOMINANT profile 的 budget 降到
exploration_floor，但不完全 kill。

- 機制：dry-run allocator 已能輸出 floor-only weight；實際 apply 仍需
  runtime consumer。
- 變動模組：與 PB-SHIFT 同。
- **Class**：HIGH_RISK_IMPL_CANDIDATE — 比 PB-SHIFT 更激進；
  **必須**保留 cooldown / re-entry rule（見 PB-RESURRECT）。
- **Forbidden until**：同 PB-SHIFT。

### 1.3 Profile exploration floor preservation（PB-FLOOR）

**意圖**：確保任何 intervention 都遵守 EXPLORATION_FLOOR=0.05。

- 機制：在 future runtime consumer 中強制 floor，與 0-9O-B 的
  `_normalize_with_floor` 對齊。
- 變動模組：future runtime consumer（暫不存在）。
- **Class**：SAFE_IMPL_CANDIDATE — 不會弱化 Arena；只是 PB-SHIFT /
  PB-SUPPRESS 的 invariant guard。
- **Forbidden until**：runtime consumer 本身被授權前不可實作。

### 1.4 Profile quarantine（PB-QUARANTINE）

**意圖**：對連續多個 round 表現極差（sparse + OOS_FAIL 雙高）的
profile 強制進入 cooldown，期間不接受 budget。

- 機制：runtime consumer + state store（Redis 或 PG table），記錄
  quarantine_until timestamp。
- 變動模組：runtime consumer + storage layer。
- **Class**：HIGH_RISK_IMPL_CANDIDATE — 易誤殺有用的 rare-event alpha。
- **Forbidden until**：j13 + CANARY + 顯式 cooldown / re-entry rule。

### 1.5 Profile resurrection after cooldown（PB-RESURRECT）

**意圖**：被 quarantine 的 profile 在 cooldown 期滿後重回 floor-only
budget，給予 re-entry 機會。

- 機制：scheduled re-entry，每 quarantine_window 結束後 unlock。
- 變動模組：runtime consumer + scheduler。
- **Class**：SAFE_IMPL_CANDIDATE（但僅在 PB-QUARANTINE 已實作後）；
  防止「永久殺 profile」這種不可逆狀態。
- **Forbidden until**：PB-QUARANTINE 通過 + j13 顯式 order。

### 1.6 Profile mutation pressure adjustment（PB-MUT）

**意圖**：調整 GP loop 對 sparse-prone profile 的 mutation /
crossover probability。

- 變動模組：`alpha_engine` GP knobs。
- **Class**：HIGH_RISK_IMPL_CANDIDATE — 改的是 `Hard rules`
  protected 的 generator behavior（global §3 / project §1）；
  容易製造 over-fitting。
- **Forbidden until**：j13 顯式 generation-policy order。

### 1.7 Density-aware generation profile preset（PB-DENSITY）

**意圖**：為 generator 加入新的 profile 模板，預設較高的 signal
density（例如更短的 min_hold、較低的 entry_threshold range）。

- 變動模組：`zangetsu/config/`、`alpha_engine` profile loader。
- **Class**：HIGH_RISK_IMPL_CANDIDATE — 加新 profile 比改舊 profile 更
  保守（不破壞既有），但仍是 generation policy change。
- **Forbidden until**：j13 顯式 order。

### 1.8 Profile diversity-preserving sampling（PB-DIV）

**意圖**：強制 sampling weight 維持最小的 profile diversity，避免
allocator 收斂到單一 profile（profile collapse）。

- 機制：runtime consumer 在 normalize 後再做 diversity floor。
- 變動模組：runtime consumer。
- **Class**：SAFE_IMPL_CANDIDATE（與 PB-FLOOR 同層）。
- **Forbidden until**：runtime consumer 被授權前不可實作。

### 1.9 Candidate pre-A2 density screen（PRE-A2-SCREEN）

**意圖**：在 candidate 進入 Arena A2 之前，先做 light-weight density
check，密度不足者直接過濾掉，不浪費 A2 GPU。

- 變動模組：candidate creation pipeline / pre-A2 hook。
- **Class**：HIGH_RISK_IMPL_CANDIDATE — 改 candidate creation 即改
  generation policy；容易過濾掉真正有價值的 rare-signal alpha。
- **Forbidden until**：j13 顯式 order；**必須**保留「不通過
  pre-screen 的也仍會進入低 budget pool」的 fallback。

### 1.10 Profile score smoothing（PB-SMOOTH）

**意圖**：用 EMA / rolling 平滑 profile_score，減少 per-batch noise。

- 變動模組：`generation_profile_metrics`（read-only diagnostic 不變
  仍 OK；只在 allocator interpretation 端做平滑）。
- **Class**：SAFE_IMPL_CANDIDATE if scoped to dry-run allocator
  interpretation；HIGH_RISK if 改寫 stored profile_score。
- **Forbidden until**：界線清楚 + j13 確認 scope。

### 1.11 Profile variance penalty（PB-VAR）

**意圖**：penalize 高 instability_penalty 的 profile，再加入
profile_score 計算。

- **Class**：DESIGN_ONLY — 既有 `compute_profile_score` 已含
  `w8_instability_penalty`；本 class 屬於對既有公式的調整建議。
- **Forbidden until**：governance 認定為 dry-run-only allocator
  diagnostic update（屬於 0-9O-B 範圍的擴充而非 0-9R-IMPL）。

## 2. Class summary table

| Class | Code | Status | Module(s) | Risk |
| --- | --- | --- | --- | --- |
| Profile budget shift | PB-SHIFT | HIGH_RISK_IMPL_CANDIDATE | runtime consumer + arena_pipeline | High |
| Profile suppression | PB-SUPPRESS | HIGH_RISK_IMPL_CANDIDATE | runtime consumer | High |
| Exploration floor preservation | PB-FLOOR | SAFE_IMPL_CANDIDATE | runtime consumer | Low |
| Profile quarantine | PB-QUARANTINE | HIGH_RISK_IMPL_CANDIDATE | runtime + state store | High |
| Profile resurrection | PB-RESURRECT | SAFE_IMPL_CANDIDATE (depends on QUARANTINE) | scheduler | Medium |
| Mutation-pressure adjust | PB-MUT | HIGH_RISK_IMPL_CANDIDATE | alpha_engine | High |
| Density-aware preset | PB-DENSITY | HIGH_RISK_IMPL_CANDIDATE | config + alpha_engine | High |
| Diversity-preserving sampling | PB-DIV | SAFE_IMPL_CANDIDATE | runtime consumer | Low |
| Pre-A2 density screen | PRE-A2-SCREEN | HIGH_RISK_IMPL_CANDIDATE | candidate creation | High |
| Profile score smoothing | PB-SMOOTH | SAFE/HIGH (scope-dependent) | metrics interpretation | Low/High |
| Profile variance penalty | PB-VAR | DESIGN_ONLY | profile_metrics scoring | Medium |

## 3. Recommended implementation sequence

如果 j13 未來授權 0-9R-IMPL，建議以下順序（最低風險先 → 最高風險後）：

1. PB-FLOOR + PB-DIV（runtime consumer 的不變式）— 與 0-9O-B
   既有契約對齊。
2. PB-SHIFT（dry-run only first）— 啟動 runtime consumer 但 apply=false。
3. PB-SHIFT（CANARY apply）— 取得 j13 + 0-9S 授權後切換 apply=true，
   局部 cohort。
4. PB-SUPPRESS（CANARY apply）。
5. PB-QUARANTINE + PB-RESURRECT（CANARY apply）。
6. PB-DENSITY（新增 profile preset，需另一道 generation-policy order）。
7. PB-MUT / PRE-A2-SCREEN（最高風險；需獨立 j13 order）。

每一步必須通過 §05_ab_evaluation_and_canary_readiness 的 success
criteria，否則 rollback。

## 4. Forbidden classes（不在 0-9R / 0-9R-IMPL 範圍）

以下 intervention 即便看似能改善 sparse rate 也**不可採用**：

- 降低 `A2_MIN_TRADES`（25 → 任意更低）。
- 弱化 `arena2_pass` / `arena3_pass` / `arena4_pass` 條件。
- 改 A3 OOS threshold（`segment_min_trades`、`val_pos < 2`）。
- 改 champion promotion criteria（CANDIDATE → DEPLOYABLE gate）。
- 改 deployable_count semantics（包含 CANDIDATE 或包含
  ARENA3_COMPLETE）。
- 為 sparse profile 提供「免測試」exemption。

任一項都需獨立的 threshold / Arena order，並由 j13 顯式授權，
**不屬於** sparse-candidate intervention 的合法解。
