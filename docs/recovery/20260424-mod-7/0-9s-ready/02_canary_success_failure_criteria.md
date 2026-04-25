# 02 — CANARY Success and Failure Criteria (S1–S14, F1–F9)

> **重要前提**：本檔案為 PR-D / 0-9S-READY 之 design 交付物。
> S/F 條件僅在未來 0-9S-CANARY activation order 出現後生效；
> 0-9S-READY 本身不啟動 treatment、不 hot-swap weights、
> 不變更 Arena pass/fail、不變更 deployable_count semantics、
> 不修改 A2_MIN_TRADES / ATR / TRAIL / FIXED grids 任一條目。
>
> 0-9R `05_ab_evaluation_and_canary_readiness.md` 已定義 S1–S12 / F1–F8；
> 本檔（PR-D）擴展為 **S1–S14 / F1–F9**（+2 success / +1 failure），補
> 足 operator-grade thresholds、measurement window、data source、
> calculation 與 action 對應。

---

## 1. 範圍

| 項目 | 描述 |
| --- | --- |
| Cohort | baseline（current generation pipeline）vs treatment（0-9R-IMPL intervention） |
| Treatment 來源 | `feedback_budget_consumer.py`（PR-C / `fe3075f`）的 `SparseCandidateDryRunPlan` 28-field schema |
| Treatment 性質 | dry-run only —— 0-9S-CANARY 啟動後仍經 hot-swap 進入 baseline ↔ treatment 雙路；apply path 必經 §17.5 `bin/bump_version.py` 嚴守 |
| Strategy | `STRATEGY_ID = j01`（j02 平行運作但不混算） |
| Telemetry pipeline | P7-PR4B aggregate Arena pass-rate（A1/A2/A3） |
| Authority view | `<proj>_status` / `champion_pipeline.status='DEPLOYABLE'`（§17.1） |
| Audit verdict | `zangetsu/tools/profile_attribution_audit.py`（PR-B / `3219b805`） |

通報節律：每日 j13 review + Calcifer outcome watch（5 min poll）。

---

## 2. Composite scoring（restate from 0-9R）

```
composite = 0.40 * a2_pass_rate
          + 0.40 * a3_pass_rate
          + 0.20 * deployable_density

deployable_density = deployable_count_7d / a3_passed_7d
```

權重為設計提案；0-9S-CANARY activation order 啟動前由 j13 顯式確認最
終權重（CR15 evidence package 中註記）。

---

## 3. Success criteria — S1–S14

> 表格給 quick reference；每條於 §3.x 完整展開（threshold / window /
> data source / calculation / action）。

| # | Statement |
| --- | --- |
| S1 | A2 SIGNAL_TOO_SPARSE rate 相對 baseline 下降 ≥ 20% |
| S2 | A2 pass_rate 相對 baseline 改善 ≥ +3 pp absolute |
| S3 | A3 pass_rate 相對 baseline 不退化 > 2 pp absolute |
| S4 | OOS_FAIL rate 相對 baseline 不增加 > 3 pp absolute |
| S5 | deployable_count 7-day median 維持或改善 |
| S6 | UNKNOWN_REJECT < 0.05 (cross-stage, 7-day rolling) |
| S7 | profile collapse 未發生（actionable profile 數 ≥ 50% baseline） |
| S8 | exploration floor 維持 active（每 profile ≥ 0.05） |
| S9 | 無 threshold 變更（A2_MIN_TRADES / ATR / TRAIL / FIXED grids 不動） |
| S10 | 無 Arena pass/fail logic 變更 |
| S11 | 無 champion promotion criteria 變更 |
| S12 | 無 execution / capital / risk path 變更 |
| S13 | 每個 regime 的 deployable_count 不退化（per-regime stability） |
| S14 | composite score 相對 baseline ↑ ≥ 1σ above noise |

S1–S14 全部達成 → 一日宣告當日「success-day」；連續 14 個 success-day
→ 進入 0-9T production rollout 評估（per 0-9R `§10 Production readiness`）。

### 3.1 S1 — A2 SIGNAL_TOO_SPARSE rate 下降 ≥ 20% relative

- **Threshold**：treatment median ≤ baseline median × 0.80。
- **Window**：7-day rolling，per cohort。
- **Data source**：`arena_batch_metrics.signal_too_sparse_rate`
  （P7-PR4B 已上線）。
- **Calculation**：
  ```
  WITH base AS (
    SELECT median(signal_too_sparse_rate) AS m
    FROM arena_batch_metrics
    WHERE cohort='baseline' AND ts >= now() - interval '7 days'
  ), treat AS (
    SELECT median(signal_too_sparse_rate) AS m
    FROM arena_batch_metrics
    WHERE cohort='treatment' AND ts >= now() - interval '7 days'
  )
  SELECT 1 - (treat.m / base.m) AS relative_decrease FROM base, treat;
  -- pass: relative_decrease >= 0.20
  ```
- **Action**：success → 計入 success-day；fail → 不算 fail（這是
  intervention 的 PRIMARY KPI 但未達標仍須等 14-day window 結束才宣告
  整體失敗，搭配 F-criteria）。

### 3.2 S2 — A2 pass_rate 改善 ≥ +3 pp absolute

- **Threshold**：treatment − baseline ≥ +0.03（absolute pp）。
- **Window**：7-day rolling。
- **Data source**：`arena_batch_metrics.a2_pass_rate`（per cohort）。
- **Calculation**：treatment 7-day median − baseline 7-day median；同期間。
- **Action**：success → 計入 success-day；fail → 與 S1 同步比對：S1 也
  fail → 視為「intervention 無效」，14-day 視窗結束 → rollback。

### 3.3 S3 — A3 pass_rate 不退化 > 2 pp absolute

- **Threshold**：treatment − baseline ≥ −0.02（absolute pp）。
- **Window**：7-day rolling。
- **Data source**：`arena_batch_metrics.a3_pass_rate`。
- **Calculation**：同 S2 公式。
- **Action**：success → 計入 success-day；fail（≥ 2 pp drop）→ trigger
  governance review；若同時 ≥ 5 pp drop → F1 觸發 → 立即 rollback。

### 3.4 S4 — OOS_FAIL 不增加 > 3 pp absolute

- **Threshold**：treatment − baseline ≤ +0.03（absolute pp）。
- **Window**：7-day rolling。
- **Data source**：`arena_batch_metrics.oos_fail_rate`。
- **Calculation**：treatment 7-day median − baseline 7-day median。
- **Action**：success → 計入 success-day；fail（> 3 pp）→ governance
  review；若 ≥ 5 pp → F3 觸發 → 立即 rollback。

### 3.5 S5 — deployable_count 7-day median 維持或改善

- **Threshold**：treatment 7-day median ≥ baseline 7-day median。
- **Window**：7-day rolling，per cohort。
- **Data source**：`<proj>_status.deployable_count`（§17.1
  authoritative VIEW）；fallback `champion_pipeline.status='DEPLOYABLE'`。
- **Calculation**：
  ```
  SELECT cohort,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY daily_count) AS m7
  FROM (
    SELECT cohort, date_trunc('day', last_live_at) AS d,
           count(*) FILTER (WHERE status='DEPLOYABLE') AS daily_count
    FROM champion_pipeline
    WHERE last_live_at >= now() - interval '7 days'
    GROUP BY cohort, d
  ) t
  GROUP BY cohort;
  -- pass: treatment.m7 >= baseline.m7
  ```
- **Action**：success → 計入 success-day；fail → §17.4 watchdog 啟動
  auto-revert 評估；連 12h 不動 → 自動 rollback。

### 3.6 S6 — UNKNOWN_REJECT < 0.05

- **Threshold**：cross-stage 7-day rolling rate < 0.05。
- **Window**：7-day rolling。
- **Data source**：`arena_batch_metrics.unknown_reject_count /
  entered_count`，跨 A1/A2/A3。
- **Calculation**：每日聚合 → 7-day mean。
- **Action**：success → 計入 success-day；fail → F4 觸發 → 暫停 CANARY
  並修 taxonomy（0-9H/0-9I）。

### 3.7 S7 — profile collapse 未發生

- **Threshold**：actionable profile 數 ≥ 50% baseline actionable profile 數。
- **Window**：daily snapshot；7-day rolling 確認不是噪聲。
- **Data source**：`generation_profile_metrics.actionable=true`（per profile）。
- **Calculation**：
  ```
  count(distinct profile) FILTER (WHERE actionable AND cohort='treatment')
    >=
  0.5 * count(distinct profile) FILTER (WHERE actionable AND cohort='baseline')
  ```
- **Action**：success → 計入 success-day；fail → F5 觸發 → 立即 rollback。

### 3.8 S8 — exploration floor active

- **Threshold**：每 profile 的 budget weight ≥ 0.05（per `EMA_ALPHA_MAX`
  / `enforce_floor_and_diversity` contract）。
- **Window**：每次 dry-run plan 生成時即時檢查。
- **Data source**：`SparseCandidateDryRunPlan.budget_weights`（28-field
  schema 中的 floor 欄位）。
- **Calculation**：
  ```python
  all(w >= 0.05 for w in plan.budget_weights.values())
  ```
- **Action**：success → 計入 success-day；fail → F6 觸發 → 立即
  rollback；**不可** j13 override（與 0-9R-IMPL-DRY G7 一致）。

### 3.9 S9 — 無 threshold 變更

- **Threshold**：A2_MIN_TRADES / ATR / TRAIL / FIXED grids 任一條目
  在 CANARY window 中不被改動。
- **Window**：full CANARY window（從 activation order SHA 到 close
  SHA）。
- **Data source**：git diff（controlled-diff CI gate）。
- **Calculation**：
  ```
  git diff <activation_sha>..HEAD -- 'zangetsu/**/*threshold*' \
                                    'zangetsu/**/*atr*' \
                                    'zangetsu/**/*trail*' \
                                    'zangetsu/**/*fixed*'
  -- expect: empty
  ```
- **Action**：success → 計入 success-day；fail → CANARY 整體無效（這是
  governance 層級違規，需追究）。

### 3.10 S10 — 無 Arena pass/fail logic 變更

- **Threshold**：Arena pass/fail logic 不被改動。
- **Window**：full CANARY window。
- **Data source**：git diff `arena_pipeline.py` / `arena23_orchestrator.py` /
  `arena45_orchestrator.py` / `arena_gates.py`。
- **Calculation**：controlled-diff CI（0-9M）對該名單在 CANARY window
  中保持 `EXPLAINED` 或 `EXPLAINED_TRACE_ONLY`。
- **Action**：success → 計入 success-day；fail → CANARY 無效，governance
  review。

### 3.11 S11 — 無 champion promotion criteria 變更

- **Threshold**：champion promotion logic 不被改動。
- **Window**：full CANARY window。
- **Data source**：git diff `champion_pipeline.py` / champion 相關 SQL。
- **Calculation**：controlled-diff `EXPLAINED`。
- **Action**：success → 計入 success-day；fail → CANARY 無效，governance
  review。

### 3.12 S12 — 無 execution / capital / risk 變更

- **Threshold**：`alpha_signal_live.py` / `data_collector.py` /
  `alpha_dedup.py` / `alpha_ensemble.py` / `alpha_discovery.py` /
  capital allocator / risk module 不被改動。
- **Window**：full CANARY window。
- **Data source**：git diff + `05_runtime_isolation_audit.md` 名單。
- **Calculation**：grep + controlled-diff，確認名單無 import consumer。
- **Action**：success → 計入 success-day；fail → F9 觸發 → 立即 rollback
  + governance audit。

### 3.13 S13 — per-regime stability acceptable（NEW vs 0-9R）

- **Threshold**：每個 regime（bull / bear / range / vol-spike）的
  deployable_count 7-day median 較 baseline 同期 不退化（drop ≤ 0）。
- **Window**：7-day rolling，per regime。
- **Data source**：`champion_pipeline` join `regime_label`（or
  passport.regime if available）。
- **Calculation**：
  ```
  SELECT regime,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY daily) FILTER (WHERE cohort='treatment') AS t,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY daily) FILTER (WHERE cohort='baseline')  AS b
  FROM ( ... per-regime daily deployable count ... ) x
  GROUP BY regime;
  -- pass: t >= b for every regime
  ```
- **Action**：success → 計入 success-day；fail（任一 regime 退化）→ F8
  「結果由單一 regime 主導」對照觸發；governance review。
- **備註**：0-9R 將此放入 S11；本檔（PR-D）獨立為 S13 並要求 per-regime
  數值寫入 evidence package（baseline_snapshot.md）。

### 3.14 S14 — composite score ↑ ≥ 1σ above noise

- **Threshold**：treatment composite − baseline composite ≥ 1 × σ_noise，
  其中 σ_noise 由 baseline 過去 30 天 daily composite 的 std 估計。
- **Window**：7-day rolling composite + 30-day baseline noise floor。
- **Data source**：composite 計算自 §2 公式；輸入欄位
  `arena_batch_metrics.a2_pass_rate / a3_pass_rate`、
  `champion_pipeline.deployable_count`、`a3_passed_7d`。
- **Calculation**：
  ```
  composite_treat - composite_base >= sigma_noise(baseline 30d)
  ```
- **Action**：success → 計入 success-day（也是 14-day 結束時宣告整體
  success 的 PRIMARY 信號）；fail → 不算 fail，但連續 14 天 fail →
  整體 CANARY 無效。

---

## 4. Failure criteria — F1–F9

> 任一 F# 觸發 → 立即 rollback runtime 至 baseline weights（hot-swap），
> Telegram alert + Calcifer incident log + AKASHA witness 同步。
> **不可** j13 override 維持 treatment（除非 CR2 YELLOW override 被引用，
> 且 F4 / F6 / F8 仍永不可 override）。

| # | Statement |
| --- | --- |
| F1 | A2 improves but A3 collapses |
| F2 | A2 improves but deployable_count falls |
| F3 | OOS_FAIL increases materially |
| F4 | UNKNOWN_REJECT increases |
| F5 | profile collapse occurs |
| F6 | exploration floor violated |
| F7 | attribution verdict regresses to RED |
| F8 | rollback cannot execute |
| F9 | unexpected execution / capital / risk path touched |

### 4.1 F1 — A2 improves but A3 collapses

- **Threshold**：A2 pass_rate 相對 baseline 上升 ≥ +3 pp **同時** A3
  pass_rate 下降 ≥ 5 pp absolute。
- **Window**：7-day rolling。
- **Data source**：`arena_batch_metrics.a2_pass_rate` /
  `a3_pass_rate`。
- **Calculation**：
  ```
  (treat_a2 - base_a2) >= 0.03 AND (base_a3 - treat_a3) >= 0.05
  ```
- **Action**：rollback；Calcifer 寫 incident
  `docs/governance/incidents/YYYYMMDD-rollback-F1.md`；j13 24h review。

### 4.2 F2 — A2 improves but deployable_count falls

- **Threshold**：A2 pass_rate ↑ ≥ +3 pp **同時** deployable_count 7-day
  rolling median 下降 ≥ 1。
- **Window**：7-day rolling。
- **Data source**：`arena_batch_metrics.a2_pass_rate` +
  `<proj>_status.deployable_count`。
- **Calculation**：treatment − baseline 7-day median 同期比對。
- **Action**：rollback；§17.4 auto-revert 也會 12h 內獨立觸發。

### 4.3 F3 — OOS_FAIL increases materially

- **Threshold**：OOS_FAIL rate 增加 ≥ +5 pp absolute（vs baseline）。
- **Window**：7-day rolling。
- **Data source**：`arena_batch_metrics.oos_fail_rate`。
- **Calculation**：treatment − baseline 7-day median。
- **Action**：rollback。

### 4.4 F4 — UNKNOWN_REJECT increases

- **Threshold**：treatment unknown_reject_rate 7-day mean ≥ baseline
  + 0.02（即新增 ≥ 2 pp），或單日 ≥ 0.05。
- **Window**：7-day rolling + daily spike。
- **Data source**：`arena_batch_metrics.unknown_reject_count /
  entered_count`。
- **Calculation**：
  ```
  treat_7d_mean - base_7d_mean >= 0.02
  OR max(treat_daily) >= 0.05
  ```
- **Action**：rollback；同步暫停 CANARY 直到 taxonomy（0-9H/0-9I）修
  正；**永不** j13 override。

### 4.5 F5 — profile collapse occurs

- **Threshold**：actionable profile 數 < 50% baseline actionable profile
  數，連續 ≥ 3 day 未恢復。
- **Window**：daily + 3-day persistence。
- **Data source**：`generation_profile_metrics.actionable=true`。
- **Calculation**：見 S7 公式；連 3 天 fail → F5 觸發。
- **Action**：rollback；governance review profile diversity。

### 4.6 F6 — exploration floor violated

- **Threshold**：任一 profile budget weight < 0.05。
- **Window**：每次 dry-run plan emit 即時檢查。
- **Data source**：`SparseCandidateDryRunPlan.budget_weights`。
- **Calculation**：見 S8。
- **Action**：rollback；**永不** j13 override；同步檢查
  `enforce_floor_and_diversity` 是否被改動。

### 4.7 F7 — attribution verdict regresses to RED（NEW vs 0-9R）

- **Threshold**：`profile_attribution_audit.py` 在 CANARY window 中對最
  近 7-day 樣本回傳 `RED`。
- **Window**：daily audit run。
- **Data source**：PR-B audit tool（`zangetsu/tools/profile_attribution_audit.py`）。
- **Calculation**：
  ```
  python -m zangetsu.tools.profile_attribution_audit --window 7d --emit-verdict
  -- pass: verdict in {GREEN, YELLOW}; F7 = (verdict == RED)
  ```
- **Action**：rollback；consumer 立刻停止 emit ACTIONABLE plan（per
  `04_attribution_audit_dependency.md` §4 verdict regression flow）；
  governance review attribution gap。
- **備註**：0-9R 未明確列此為 F-criterion；PR-D 將其獨立為 F7 以對齊
  CR2 + consumer verdict gate。

### 4.8 F8 — rollback cannot execute

- **Threshold**：rollback drill / 實際 rollback 執行失敗（hot-swap 卡
  住、AKASHA witness 寫入失敗、Telegram alert 未送達等任一）。
- **Window**：每次 rollback 執行。
- **Data source**：rollback drill log + Calcifer incident log。
- **Calculation**：rollback 流程 1–5 步任一步 timeout > 5 min 或 exit
  status ≠ 0。
- **Action**：treat as governance critical；CANARY 永久 hold；j13 直接
  介入；不再嘗試 retry treatment 直到 rollback 路徑修復並重演練 ≥ 3 次。

### 4.9 F9 — unexpected execution / capital / risk path touched

- **Threshold**：CANARY window 中發現 execution / capital / risk
  module 被任一 PR diff（含 transitively import）。
- **Window**：full CANARY window。
- **Data source**：controlled-diff CI（0-9M）+ git diff watchlist
  （見 S12 名單）。
- **Calculation**：controlled-diff verdict ≠ `EXPLAINED` 且 diff 觸及
  watchlist 任一檔案 → F9 觸發。
- **Action**：rollback + governance audit + 強制 §17.5 review；可能
  需要 PR revert（per §17.4 auto-revert）。

---

## 5. Aggregation rules — daily / weekly / 14-day

| 視窗 | 規則 |
| --- | --- |
| Daily | 計算所有 S1–S14；任一 F1–F9 觸發 → rollback 不等到日終 |
| 連續 7 day | success-day 計數 ≥ 5 才視為 weekly success；< 5 → governance review |
| 14-day（CANARY full window） | 14-day success-day ≥ 10 **且** F1–F9 全程未觸發 → 進入 0-9T production rollout 評估 |

未達 14-day success → CANARY close，不立即進 0-9T；可在 governance
review 後重啟 next round（intervention design 可調整）。

CANARY window 預期最長 30 天（與 0-9R `§11 Off-cycle controls` 一致）；
超過必須由 j13 確認延長或 STOP。

---

## 6. Composite scoring — restated

```
composite = 0.40 * a2_pass_rate
          + 0.40 * a3_pass_rate
          + 0.20 * deployable_density

deployable_density = deployable_count_7d / a3_passed_7d
```

- 權重 0.40 / 0.40 / 0.20 為 0-9R 設計提案；0-9S-CANARY activation
  order 啟動前由 j13 顯式確認。
- noise floor σ：baseline 過去 30 天 daily composite 的 std。
- `a3_passed_7d` 為 `arena_batch_metrics.a3_passed_count` 之 7-day sum。
- `deployable_count_7d` 為 `<proj>_status.deployable_count` 之 7-day
  median × 7（保守計）；evidence package 中明列計算方式以避免歧義。

S14 = composite improvement ≥ 1σ above noise；F-criteria 並未直接以
composite 為 trigger（避免單一 KPI 隱藏分項退化）。CANARY 整體成敗的
PRIMARY 判定為 §5 14-day rule + S/F 全名單。

---

## 7. Action mapping —— success vs failure

| 結果 | 即時動作 | 中期動作 | 紀錄 |
| --- | --- | --- | --- |
| success-day | 維持 treatment；當日 evidence package 寫入 | 累計 success-day → weekly / 14-day 評估 | `docs/recovery/.../0-9s-canary-activation/daily_log/YYYYMMDD.md` |
| F1 / F2 / F3 / F5 / F7 / F9 | rollback hot-swap → baseline；Telegram alert | Calcifer incident log；24h j13 review；intervention design 調整 | `docs/governance/incidents/YYYYMMDD-rollback-F#.md` |
| F4 / F6 | rollback + 永不 j13 override；暫停 CANARY 至 root cause 修正 | governance review taxonomy / floor enforcement | 同上 |
| F8 | CANARY 永久 hold；rollback 路徑修復並重演練 ≥ 3 次後再評估 | j13 直接介入 | 同上 |
| 14-day success | 進入 0-9T production rollout 評估（per 0-9R §10） | PR1–PR6 evidence package | `docs/recovery/.../0-9t-readiness/` |
| 14-day fail | CANARY close；intervention design 調整；再下一輪 0-9S | 不立即 0-9T | `docs/retros/YYYYMMDD-0-9s-fail.md` |

---

## 8. Cross-reference quick map

| 主題 | 來源 |
| --- | --- |
| S1–S12 原始定義 | `docs/recovery/20260424-mod-7/0-9r/05_ab_evaluation_and_canary_readiness.md` §6 |
| F1–F8 原始定義 | 同檔 §7 |
| Verdict consumption（CR2 / F7） | `docs/recovery/20260424-mod-7/0-9r-impl-dry/04_attribution_audit_dependency.md` |
| Runtime isolation（S10 / S12 / F9） | `docs/recovery/20260424-mod-7/0-9r-impl-dry/05_runtime_isolation_audit.md` |
| Smoothing / step / floor（S8 / F6） | `docs/recovery/20260424-mod-7/0-9r-impl-dry/03_smoothing_and_step_limit_contract.md` |
| Outcome metric / deployable_count（S5 / S13 / F2） | CLAUDE.md §17.1 / §17.3 / §17.4 |
| Audit tool（CR2 / F7） | `zangetsu/tools/profile_attribution_audit.py`（PR-B / `3219b805`） |
| Consumer module（S1–S14 treatment 來源） | `zangetsu/services/feedback_budget_consumer.py`（PR-C / `fe3075f`） |
| Rollback SOP（F1–F9 動作） | `docs/recovery/20260424-mod-7/0-9s-ready/03_rollback_plan.md` |
| Alert path（all F#） | `docs/recovery/20260424-mod-7/0-9s-ready/04_alert_path.md` |
| CANARY readiness gate（先決條件） | `docs/recovery/20260424-mod-7/0-9s-ready/01_canary_readiness_gate.md` |

---

## 9. Limitations and explicit non-goals

- 本檔不啟動 CANARY；CR15 仍 Pending j13。
- 本檔不修改 consumer source、不 hot-swap weights、不打通 Telegram
  alert wiring（PR-D 為 docs only）。
- composite weights 為設計提案；最終值在 0-9S activation order 確認。
- per-regime regime label 來源若不可用（`passport.regime` 未注入），
  S13 / F8 暫以 worker_id mapping 替代並記錄到 evidence package。
- 0-9T production rollout 條件（PR1–PR6）見 0-9R §10，不在本檔展開。

PR-D 至此交付完畢；S/F 條件僅在 TEAM ORDER 0-9S-CANARY 下單後生效。
