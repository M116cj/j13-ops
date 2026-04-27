# 01 — Pipeline Outcome Chain Audit (Phase 1)

**Phase 1 Verdict:** `PIPELINE_BLOCKED_AT_A1` (current behavior)

The chain has **two distinct broken layers** along the time axis:

- **Recent (since 2026-04-21 04:34 UTC, ~6.5 days)** — A1 internal reject 100%; pipeline produces no admissions.
- **Historical (2026-04-20 → 2026-04-21)** — original 89 admitted alphas all subsequently `ARENA2_REJECTED`; pool never produced a deployable.

## Chain map

```
A1 (arena_pipeline w0–w3)
    │   per-batch reject distribution clean (CI=0, UNKNOWN_REJECT=0)
    │   pass rate (last 100 batches, ~6 min): 0 / 1000 = 0.0%
    │   reject reasons: COST_NEGATIVE 96.1%, SIGNAL_TOO_SPARSE 3.3%, LOW_BACKTEST_SCORE 0.6%
    ▼
champion_pipeline_staging  (184 rows)
    │   admission_state = admitted (89), admitted_duplicate (95)
    │   first 2026-04-20 18:07,  last 2026-04-21 04:34  (NO new admissions in last 6.5 days)
    │   admission_validator gates 1/2/3 on alpha_hash format, epoch, arena1_score finite
    ▼
champion_pipeline_fresh    (89 rows)
    │   regimes: 1   (single-regime concentration)
    │   distinct indicator_hash: 89   (no internal duplicates; usage_entropy=0 from view, distinct_indicators=0)
    │   arena1_score: min 0.6298, max 0.9989, avg 0.8455   (high A1 scores)
    │   card_status / status: 100% `INACTIVE` / `ARENA2_REJECTED`
    ▼
A23 orchestrator (services/arena23_orchestrator.py)
    │   alive (pid 885011); started 17:02:25 "Service loop started"
    │   no further log activity → idle (no candidates flow in)
    ▼
A45 orchestrator (services/arena45_orchestrator.py)
    │   alive (pid 885036); "Daily reset complete: kept=0 retired=0 across 0 regimes"
    ▼
champion_pipeline_fresh.card_status = DEPLOYED?  ← never reached
    │
    ▼
zangetsu_status.deployable_count = 0  (NEVER > 0)
                last_live_at_age_h = NULL  (NO live champion ever)
```

## A1 — generation rate and reject distribution after fixes

Source: `/home/j13/j13-ops/zangetsu/logs/engine.jsonl`, last 100 `arena_batch_metrics` events.

| Metric | Value |
|---|---|
| Window | 17:19:57Z → 17:25:51Z (5 min 54 s) |
| Batches | 100 |
| Entered | 1000 (100 batches × 10) |
| Passed | 0 |
| Skipped | 0 |
| Rejected sum (= sum of distribution) | 1000 |
| residual ∈ {0} | ∀ 100 batches |
| reject reason — COST_NEGATIVE | 961 (96.1%) |
| reject reason — SIGNAL_TOO_SPARSE | 33 (3.3%) |
| reject reason — LOW_BACKTEST_SCORE | 6 (0.6%) |
| reject reason — COUNTER_INCONSISTENCY | 0 (post-fix) |
| reject reason — UNKNOWN_REJECT | 0 (post-fix) |

Both strategy lanes active: `gp_541a313e770c4424` (j01 baseline) emitted 52 batches; `gp_26f478846fd0f729` (j02 exploration) emitted 48 batches. **Both lanes show 100% reject.**

`COST_NEGATIVE` taxonomy mapping (verified Phase 0): the runtime code emits `reject_train_neg_pnl` for any candidate whose train-window PnL fails to overcome modeled transaction cost; the taxonomy collapses this to `COST_NEGATIVE`. No taxonomy bug; the reject reason is real.

## A2 — admission/rejection counts

`champion_pipeline_staging`:

| admission_state | first | last | count |
|---|---|---|---|
| admitted | 2026-04-20 18:07:49 | 2026-04-21 04:34:21 | 89 |
| admitted_duplicate | 2026-04-20 18:07:51 | 2026-04-21 04:13:52 | 95 |
| pending | — | — | 0 |
| rejected | — | — | 0 |
| pending_validator_error | — | — | 0 |

**Last admission: 2026-04-21 04:34:21Z** (~6.5 days before capture). No new admissions during the active observation window because A1 has not produced any admissible candidates.

## A23 / A45 orchestration status

A23 log post-restart: full warmup (Rust engine loaded; DB connected; 14 symbols loaded train split; Service loop started at 17:02:25Z). No subsequent emit lines — orchestrator is idle (no champions in queue meeting A2 admission criteria).

A45 log post-restart: full warmup (14 symbols loaded holdout split; `Daily reset starting` → `Daily reset complete: kept=0 retired=0 across 0 regimes`). The retain/retire bookkeeping confirms zero champions in any regime.

## Fresh pool deeper inspection

`fresh_pool_outcome_health` view (j01 only):

| Field | Value |
|---|---|
| total_fresh | 89 |
| alphas_with_indicators | 0 |
| indicator_alpha_ratio_pct | 0.00 |
| distinct_indicators | 0 |
| usage_entropy | 0 |
| avg_depth | 0.00 |
| avg_nodes | 0.00 |
| **deployable_count** | **0** |

The 89 fresh alphas use **zero indicators** (depth 0, nodes 0). They are degenerate raw-OHLCV-only formulas — confirming AKASHA's prior finding that "60-bar forward return on OHLCV+indicator formulation" had its space exhausted.

`fresh_pool_process_health` view: **0 rows** — because `engine_telemetry` table has 0 rows.

## engine_telemetry — process health observability gap

The `engine_telemetry` insert at `zangetsu/services/arena_pipeline.py:385` runs inside a guarded `try / except: pass` and depends on `_telemetry_counters` being populated and a flush condition (`_last_telemetry_flush_ts`). Despite the workers running for 23 minutes and emitting 100+ `arena_batch_metrics` events, **0 rows have ever landed in `engine_telemetry`**.

Effect on observability:

- `fresh_pool_process_health` view returns 0 rows
- v0.7.1 dual-evidence VIEW design (process + outcome) has only the outcome side functional
- No DB-side time-series for compile/evaluate/cache/admission rates

Severity: P1 (does not block CANARY directly, but degrades governance gates). Out of scope for this read-only review; flagged for follow-up order.

## Required Phase 1 classification

```
PIPELINE_BLOCKED_AT_A1
```

Rationale: A1 produces zero admissions. Even if A23/A45 were given perfect candidates, none arrive. Original 89 candidates from 2026-04-20–21 already exhausted at A2 (`ARENA2_REJECTED`); no replacement supply.

This is **not a bug**: the telemetry fix (PR #49 + #50) only confirmed observability. The 100% reject is honest signal — the current alpha generation policy (60-bar forward return / OHLCV-only feature space) is exhausted.

## Pipeline data freshness

| Field | Value |
|---|---|
| arena_batch_metrics is fresh | YES (last batch 17:25:51Z, ~10 s before capture) |
| sparse dry-run plans exist | TBD — `zangetsu/services/sparse_canary_observer.py` is implemented (TEAM ORDER 0-9S-CANARY) but no observation records visible from this audit |
| last new admission | 2026-04-21 04:34:21Z (6.5 days stale) |
| last live champion | NEVER |
| last deployable | NEVER |
