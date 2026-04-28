# 00 — State Lock (Subprogram C)

**Order:** TEAM ORDER 0-9Y-C-ECONOMIC-EDGE-DECOMPOSITION
**Phase:** 0
**Captured (UTC):** 2026-04-28T00:08Z
**Captured-by:** Claude Lead

## Repo state

| Field | Value |
|---|---|
| Mac HEAD | `d9d178348b6ec37cbef9212579a7d4b35bf0cd73` |
| Alaya HEAD | `d9d178348b6ec37cbef9212579a7d4b35bf0cd73` (parity) |
| origin/main | `d9d178348b6ec37cbef9212579a7d4b35bf0cd73` |
| Branch | `main` (pre-C) |
| Source dirty | runtime artifacts only |

Master 0-9Y progress: A → B1 → B2 → B3 complete (PRs #54-#57). Current Subprogram = **C**.

## Worker process state — POST-RESTART (operator-authorized)

j13 explicitly authorized worker restart at 2026-04-28T00:04Z via `./zangetsu_ctl.sh restart`. Six fresh worker PIDs spawned within 1-2 s of each other:

| PID | Process | Restart time |
|---|---|---|
| 1364819 | `arena_pipeline.py` (w0) | 2026-04-28T00:04:?? |
| 1364842 | `arena_pipeline.py` (w1) | 2026-04-28T00:04:?? |
| 1364934 | `arena_pipeline.py` (w2) | 2026-04-28T00:04:?? |
| 1364975 | `arena_pipeline.py` (w3) | 2026-04-28T00:04:?? |
| 1365067 | `arena23_orchestrator.py` | 2026-04-28T00:04:?? |
| 1365092 | `arena45_orchestrator.py` | 2026-04-28T00:04:?? |

All 6 lockfiles re-created at `/tmp/zangetsu/` mtime `Apr 28 00:04`. Workers in `Service loop started` state per engine.jsonl.

## Why restart was authorized

Subprogram B1 (PR #55) added `aggregate_metrics` field to every `arena_batch_metrics` event. The previous worker generation (started 2026-04-27T17:02Z) was running pre-B1 code in memory and did NOT emit `aggregate_metrics`. Subprogram C requires the aggregate_metrics distribution to compute gross-vs-cost decomposition, so a restart was necessary to load the B1 emitter code.

j13 directive: "選 A：重啟。理由：Subprogram C 必須依賴 live B1 aggregate_metrics. 不重啟會導致 C = BLOCKED_METRICS_INSUFFICIENT, D 也會被連鎖阻塞."

## DB sanity (v0.7.1)

`docker exec deploy-postgres-1 psql -U zangetsu -d zangetsu`:
- `champion_pipeline = 89` (carry-forward from previous orders; expected 0 movement during this subprogram)
- `champion_pipeline_staging = 184`
- `champion_pipeline_fresh = 89`

DB schema unchanged. No DB writes from this subprogram (read-only diagnosis).

## Live verification — `aggregate_metrics` LIVE post-restart

First sample batch captured at `2026-04-28T00:07:32Z` (`R330403-DOTUSDT-BULL_TREND`):

```
entered=10, passed=0, rejected=10, skipped=0, CI=0, UR=0
reject_reason_distribution = {COST_NEGATIVE: 10}

aggregate_metrics:
  schema_version: 0-9y-b1-v1
  symbol: DOTUSDT
  regime: BULL_TREND
  lane: baseline
  round_total_cost_bps: 14.5
  alphas_with_train_backtest: 10
  alphas_with_val_backtest: 0           ← all 10 train-rejected before val
  alphas_with_combined_sharpe: 0
  train_gross_pnl_median: 2.646          (bps)
  train_gross_pnl_mean: 2.616            (bps)
  train_net_pnl_median: -1.804           (bps)
  train_net_pnl_mean: -1.817             (bps)
  train_gross_minus_net_median: 4.405    (bps; = total cost charged)
  train_total_trades_median: 989
  train_total_trades_mean: 1020
  train_sharpe_median: -2.76
  train_win_rate_median: 0.309
  signal_density_per_bar: 0.0073
  val_net_pnl_median / val_sharpe_median / val_total_trades_median / combined_sharpe_median: null
```

**Initial observation (single batch only)**: gross > 0 (2.65 bps median) but cost > gross (4.4 bps charged) → net < 0 (-1.8 bps). This is the **β-pattern** ("gross edge exists but is smaller than cost"). Confirmation requires the full 100+ batch sample.

## Acquisition plan

Wait until 100+ `arena_batch_metrics` with `aggregate_metrics` are present in `engine.jsonl`. Then:

- Phase 1: parse the full sample, extract distributions of every aggregate_metrics field
- Phase 2 (subagent): gross-vs-cost decomposition — does cost > gross hold across all batches, or only some?
- Phase 3 (subagent): per-symbol / per-regime / per-lane breakdown — find any cohort with gross > cost
- Phase 4 (subagent): train-vs-val divergence — when alphas_with_val_backtest > 0, does val confirm train edge?
- Phase 5 (subagent): signal density — is `signal_density_per_bar` consistent across the cohort, or does sparsity correlate with rejection?
- Phase 6 (Lead synthesis): root-cause classification per the verdict options below
- Phase 7 (subagent governance-verifier): controlled diff
- Phase 8 (Lead): final report
- Phase 9 (Lead): commit + PR + Telegram

## Verdict candidates (chosen at Phase 8)

- `DECOMPOSED_NEGATIVE_GROSS_EDGE_DOMINANT` — gross_pnl < 0 across the board (alphas predict nothing)
- `DECOMPOSED_GROSS_EDGE_LOST_TO_COST` — gross > 0 but cost > gross consistently (cost dominates)
- `DECOMPOSED_PER_SYMBOL_CONCENTRATION` — some symbols have gross > cost; population mean is misleading
- `DECOMPOSED_TRAIN_VAL_DIVERGENCE` — train edge but val cost-negative (overfitting)
- `DECOMPOSED_INSUFFICIENT_SIGNAL_DENSITY` — too few trades to overcome cost noise
- `DECOMPOSED_MIXED_CAUSES` — multiple roots
- `BLOCKED_INSUFFICIENT_BATCHES` — < 100 batches collected
- `BLOCKED_AGGREGATE_METRICS_MISSING` — `aggregate_metrics` field absent or null in all batches
- `BLOCKED_FORBIDDEN_DIFF`

## STOP-condition evaluation

| STOP condition | Triggered? |
|---|---|
| repo dirty with unexplained source modifications | NO |
| HEAD ≠ origin/main | NO — parity verified |
| A1 runtime dead post-restart | NO — 6/6 alive |
| DB unavailable | NO |
| v0.7.1 objects missing | NO |
| `aggregate_metrics` field absent post-restart | NO — confirmed live in first sample batch |

**No STOP. Awaiting 100+ batches before Phase 1.**

## Q1 / Q2 / Q3 for this order

- **Q1 Adversarial (5-dim)**:
  - Input boundary: handle batches with null val/combined fields (alphas_with_val_backtest=0 case); handle medians of empty lists; handle batches with 0 alphas_with_train_backtest
  - Silent failure: any classification verdict must cite the field/threshold that drove it; no inferred-from-inference chains
  - External dependency: rely only on engine.jsonl (no DB queries beyond schema sanity); no /classify() or taxonomy involvement
  - Concurrency: each batch is from one worker at one moment; no cross-worker accounting needed
  - Scope creep: no source patch, no calibration touch, no DB write, no validator change
- **Q2 Structural**: read-only operations; no commit until docs evidence ready; runtime untouched
- **Q3 Efficiency**: 4 parallel subagents for Phases 2-5; max 9 evidence files; subagent dispatch parallel where possible

## Forbidden ops audit (this subprogram)

- No threshold change
- No validation change
- No alpha_zoo run
- No CANARY start
- No production rollout
- No runtime calibration
- No DB write
- No cost model change
- No worker kill (the restart was operator-authorized as Subprogram-C entry condition)
- No force-push
