# P7-PR4B — A2/A3 Aggregate Metrics Design

## 1. 動機

P7-PR4-LITE 已將 A1 的 aggregate `arena_batch_metrics` /
`arena_stage_summary` 接通；0-9O-A 進一步加入 `generation_profile_id`
+ `generation_profile_fingerprint`，並交付 read-only `profile_score` /
`next_budget_weight_dry_run`。但 A2 / A3 階段仍未接通 aggregate batch
metrics — 因此 `generation_profile_metrics` 永遠停在
`LOW_CONFIDENCE_UNTIL_A2_A3_METRICS_AVAILABLE`。

P7-PR4B 的目標：把 A2 / A3 的 aggregate Arena pass-rate 資料補齊，
讓 `generation_profile_metrics` 可以對黑箱 generation profile 在完整
A1 / A2 / A3 漏斗上進行品質比較。

## 2. 範圍硬限制

依 TEAM ORDER P7-PR4B §3 / §5 / §18：

- **不得**修改 alpha 生成、formula 生成、mutation / crossover、
  search policy、generation budget / sampling weights、thresholds
  （含 A2_MIN_TRADES、A3 segment threshold）、Arena pass/fail logic、
  rejection semantics、champion promotion、deployable_count semantics、
  execution / capital / risk、broker / exchange、production runtime。
- **不得**啟動 CANARY、production rollout、weaken branch protection、
  bypass signed PR-only flow、weaken controlled-diff。
- **不得**引入 per-alpha lineage、強制 formula explainability、讓
  telemetry 影響 runtime 決策。

所有 runtime instrumentation 必須是 additive、exception-safe、
non-blocking、behavior-invariant。Runtime SHA 變更走 0-9M
`EXPLAINED_TRACE_ONLY` controlled-diff 路徑。

## 3. 解法概述

新增 / 擴充三個層次：

```
┌──────────────────────────────────────────────────────────────────────┐
│ arena_pass_rate_telemetry.py（既有，擴充 stage-aware shortcut）         │
│    + normalize_arena_stage(raw)                                        │
│    + build_a2_batch_metrics(acc, *, deployable_count=None)             │
│    + build_a3_batch_metrics(acc, *, deployable_count=None)             │
│    + safe_emit_a2_batch_metrics(acc, *, deployable_count=None, log)    │
│    + safe_emit_a3_batch_metrics(acc, *, deployable_count=None, log)    │
│    + aggregate_stage_metrics(events) → {stage: rollup}                 │
└──────────────────────────────────────────────────────────────────────┘
                            ▲
                            │ stage-agnostic primitives reused
                            │
┌──────────────────────────────────────────────────────────────────────┐
│ arena23_orchestrator.py（authorized EXPLAINED_TRACE_ONLY 變更）          │
│    + module-level try-import telemetry / taxonomy / identity           │
│    + _p7pr4b_record_outcome / _p7pr4b_a2_record / _p7pr4b_a3_record     │
│    + _P7PR4BLogCapture（被動 log wrapper，不修改 log 行為）              │
│    + main() 內：A2 / A3 / dedup-skip 各路徑 accumulator 增量              │
│    + main() 內：每 N=20 champions flush 一次 batch metrics               │
│    + main() 內：shutdown 之前 flush 殘留 accumulator                      │
└──────────────────────────────────────────────────────────────────────┘
                            ▲
                            │ batch_metrics events
                            │
┌──────────────────────────────────────────────────────────────────────┐
│ generation_profile_metrics.py（既有，confidence resolution 升級）        │
│    + CONFIDENCE_A1_A2_A3_AVAILABLE                                     │
│    + CONFIDENCE_LOW_SAMPLE_SIZE                                        │
│    aggregate_batches_for_profile() 已能消化 A1 + A2 + A3 batches，       │
│    現在把 confidence 拆三態：                                             │
│      no a2/a3              → LOW_CONFIDENCE_UNTIL_A2_A3                │
│      a2/a3 + samples<20    → LOW_SAMPLE_SIZE_UNTIL_20_ROUNDS           │
│      a2/a3 + samples>=20   → CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE     │
└──────────────────────────────────────────────────────────────────────┘
```

## 4. Schema 維持不變

A2 / A3 batch metrics 沿用既有 `ArenaBatchMetrics` schema（P7-PR4-LITE
所定義），新增的 builder 只是強制 `arena_stage` 為 `"A2"` / `"A3"`。
所有 required fields（telemetry_version、run_id、batch_id、
generation_profile_id / fingerprint、entered / passed / rejected /
skipped / error / in_flight、pass_rate / reject_rate、top_reject_reason
/ reject_reason_distribution、deployable_count、timestamp_start /
timestamp_end、source）全部沿用。

## 5. Profile identity propagation 規則

§7 規則：

1. 若 upstream A1 / candidate metadata 提供 profile_id，沿用之。
2. 否則使用 orchestrator 的 consumer profile（自 V10 entry/exit 等
   穩定 knob 推導），確保同一 orchestrator instance 內 A2 / A3 batch
   會看見一致的 fingerprint。
3. 仍無法解析 → `UNKNOWN_PROFILE` / `UNAVAILABLE`。

A1 → 0-9O-A 並未把 profile_id 寫入 passport（只是把它打進 A1
telemetry），所以目前 A2 / A3 大多落到 fallback 2 — orchestrator
consumer profile。未來若有 order 把 profile_id 寫進 passport，本
helper 自動拾取。

## 6. Deployable_count 規則

§9 規則：

- 不修改 deployable_count semantics。
- A2 / A3 batch metrics 預設 `deployable_count = None` (= UNAVAILABLE)，
  確保 trace-only A2/A3 pass events **絕不**膨脹 deployable_count。
- `generation_profile_metrics.aggregate_batches_for_profile` 只在 batch
  event 顯式提供 integer `deployable_count` 時納入計算；None / 缺失
  皆視為 UNAVAILABLE。
- authoritative deployable_count 源仍是 `champion_pipeline.status =
  'DEPLOYABLE'`（Arena 4/5 promotion gate 寫入），未被本 PR 改動。

## 7. Counter conservation

§6.3 規則沿用既有 `validate_counter_conservation()`：

- Closed stage：`entered = passed + rejected + skipped + error`
- Open stage：`entered = passed + rejected + skipped + error + in_flight`

`ArenaStageMetrics` 提供 `on_entered / on_passed / on_rejected /
on_skipped / on_error / mark_closed`，後三者會 decrement
`in_flight_count`，使守恆於批次關閉時自動成立。剩餘殘留會被
`mark_closed()` 路由到 `BATCH_CLOSED_WITH_IN_FLIGHT` 捷徑。

## 8. 失敗安全

所有 telemetry 動作（accumulator 構造、計數、emission、profile
identity 解析、reject reason classification）都包在 try / except
內，失敗時 silently 丟回 False / 預設值。runtime A2 / A3 決策路徑
不依賴任何 telemetry 回傳值。

## 9. 範圍

| 檔案 | 性質 | Controlled-diff 預期分類 |
| --- | --- | --- |
| `zangetsu/services/arena_pass_rate_telemetry.py` | helper 擴充 | EXPLAINED |
| `zangetsu/services/generation_profile_metrics.py` | confidence enum 增補 | EXPLAINED |
| `zangetsu/services/arena23_orchestrator.py` | runtime trace-only 接線 | **EXPLAINED_TRACE_ONLY** (`config.arena23_orchestrator_sha`) |
| `zangetsu/tests/test_a2_a3_arena_batch_metrics.py` | 新增測試 | EXPLAINED |
| `docs/recovery/20260424-mod-7/p7-pr4b/*.md` | 證據文件 | EXPLAINED / DOC_ONLY |

未變動 runtime SHA 持有檔：
`zangetsu_settings_sha`、`arena_pipeline_sha`、`arena45_orchestrator_sha`、
`calcifer_supervisor_sha`、`zangetsu_outcome_sha`。
