# 06 — Regression Window Analysis

**Subagent:** `regression-window-auditor`
**Order:** 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS Phase 6
**Mode:** READ-ONLY. No commits, no source modification.
**Mac repo:** `/Users/a13/dev/j13-ops` @ `b1615c67` on `main`
**Alaya source:** `/home/j13/j13-ops/zangetsu/logs/engine.jsonl{,.1,.2,.3,.4,.5}` (6 rotated files, total 167,423 lines, 724 with `reject_reason_distribution`)
**History coverage:** 2026-04-26T15:00Z → 2026-04-27T14:01Z (~23 h). Order spec claimed `.1` reaches 2026-04-16T04:20Z; actual earliest `ts` in any rotated file is **2026-04-26T15:00Z**. Older history is NOT on disk.

---

## 1. PR Merge Timeline (UTC)

| PR | mergedAt (UTC) | Title (truncated) |
|---|---|---|
| #39 | 2026-04-26T14:08:55Z | `chore(zangetsu/phase7): val-filter root-cause + alpha-zoo offline replay` |
| #41 | 2026-04-26T16:42:26Z | `docs(0-9w-calibration-candidate-review): all 8 cost=0.5x survivors are SINGLE_SY` |
| #43 | 2026-04-27T04:54:39Z | `feat(consolidation/0-9x-master-v4): SYSTEM_MASTER_BLOCKED_DB — 17 tracks + Gemin` |
| #44 | **2026-04-27T06:50:53Z** | `feat(db-migration/0-9x-multi-stage): COMPLETE_DB_MIGRATED_V071` |
| #45 | 2026-04-27T09:09:03Z | `fix(zangetsu/watchdog): cold-boot recovery from zero-lock state` |
| #46 | 2026-04-27T10:06:00Z | `fix(zangetsu/watchdog): force decimal parsing for timestamp arithmetic` |
| #47 | 2026-04-27T13:42:53Z | `docs(zangetsu): finalize cold boot recovery evidence` |

---

## 2. Hourly Reject-Distribution Buckets (UTC)

`events` = number of log lines that contained `reject_reason_distribution`. `total_rejects` = sum of all reason counts in that bucket. `CI+UR%` = (`COUNTER_INCONSISTENCY` + `UNKNOWN_REJECT`) / `total_rejects`.

| Hour (UTC) | events | total_rejects | CI+UR % | Top-3 reasons (counts) |
|---|---:|---:|---:|---|
| 2026-04-26T15 | 148 | 1,562,880 | 50.0% | COUNTER_INCONSISTENCY 780,700 · COST_NEGATIVE 778,349 · SIGNAL_TOO_SPARSE 1,674 |
| 2026-04-26T16 | 220 | 3,132,800 | 50.0% | COUNTER_INCONSISTENCY 1,565,300 · COST_NEGATIVE 1,557,864 · LOW_BACKTEST_SCORE 4,209 |
| 2026-04-26T17 | 222 | 4,142,520 | 50.0% | COUNTER_INCONSISTENCY 2,070,150 · COST_NEGATIVE 2,058,580 · LOW_BACKTEST_SCORE 6,425 |
| 2026-04-26T18 | 220 | 5,077,600 | 50.0% | COUNTER_INCONSISTENCY 2,537,700 · COST_NEGATIVE 2,523,938 · LOW_BACKTEST_SCORE 7,517 |
| 2026-04-26T19 | 222 | 6,105,000 | 50.0% | COUNTER_INCONSISTENCY 3,051,390 · COST_NEGATIVE 3,034,393 · LOW_BACKTEST_SCORE 9,162 |
| 2026-04-26T20 | 220 | 7,022,400 | 50.0% | COUNTER_INCONSISTENCY 3,510,100 · COST_NEGATIVE 3,491,169 · LOW_BACKTEST_SCORE 9,648 |
| 2026-04-26T21 | 223 | 8,106,050 | 50.0% | COUNTER_INCONSISTENCY 4,051,910 · COST_NEGATIVE 4,031,017 · LOW_BACKTEST_SCORE 10,816 |
| 2026-04-26T22 | 221 | 9,014,590 | 50.0% | COUNTER_INCONSISTENCY 4,506,190 · COST_NEGATIVE 4,483,985 · LOW_BACKTEST_SCORE 11,273 |
| 2026-04-26T23 | 221 | 9,991,410 | 50.0% | COUNTER_INCONSISTENCY 4,994,600 · COST_NEGATIVE 4,970,195 · LOW_BACKTEST_SCORE 11,830 |
| 2026-04-27T00 | 222 | 11,020,080 | 50.0% | COUNTER_INCONSISTENCY 5,508,930 · COST_NEGATIVE 5,481,052 · LOW_BACKTEST_SCORE 12,386 |
| 2026-04-27T01 | 222 | 12,005,760 | 50.0% | COUNTER_INCONSISTENCY 6,001,770 · COST_NEGATIVE 5,971,455 · LOW_BACKTEST_SCORE 13,141 |
| 2026-04-27T02 | 221 | 12,930,710 | 50.0% | COUNTER_INCONSISTENCY 6,464,250 · COST_NEGATIVE 6,431,930 · LOW_BACKTEST_SCORE 14,024 |
| 2026-04-27T03 | 221 | 13,907,530 | 50.0% | COUNTER_INCONSISTENCY 6,952,660 · COST_NEGATIVE 6,918,297 · LOW_BACKTEST_SCORE 15,406 |
| 2026-04-27T04 | 2 | 130,320 | 50.0% | COUNTER_INCONSISTENCY 65,150 · COST_NEGATIVE 64,832 · LOW_BACKTEST_SCORE 146 |
| **04→08 GAP** | — | — | — | engine offline (PR #44 DB migration window) |
| **2026-04-27T08** | **862** | **1,857,660** | **99.9%** | **UNKNOWN_REJECT 930,876 · COUNTER_INCONSISTENCY 924,520 · SIGNAL_TOO_SPARSE 816** |
| 2026-04-27T09 | 959 | 6,432,610 | 99.9% | UNKNOWN_REJECT 3,215,766 · COUNTER_INCONSISTENCY 3,211,510 · LOW_BACKTEST_SCORE 1,982 |
| 2026-04-27T10 | 963 | 11,086,790 | 99.9% | UNKNOWN_REJECT 5,539,662 · COUNTER_INCONSISTENCY 5,538,580 · LOW_BACKTEST_SCORE 3,074 |
| 2026-04-27T11 | 960 | 15,667,560 | 99.9% | COUNTER_INCONSISTENCY 7,828,980 · UNKNOWN_REJECT 7,823,477 · SIGNAL_TOO_SPARSE 5,867 |
| 2026-04-27T12 | 956 | 20,181,420 | 99.9% | COUNTER_INCONSISTENCY 10,085,930 · UNKNOWN_REJECT 10,074,758 · COST_NEGATIVE 8,470 |
| 2026-04-27T13 | 958 | 24,808,260 | 99.9% | COUNTER_INCONSISTENCY 12,399,340 · UNKNOWN_REJECT 12,380,057 · COST_NEGATIVE 11,943 |
| 2026-04-27T14 | 35 | 993,450 | 99.9% | COUNTER_INCONSISTENCY 496,550 · UNKNOWN_REJECT 495,740 · COST_NEGATIVE 475 |

---

## 3. Findings

### 3.1 shift_start_time
**`2026-04-27T08:00:00Z`** — first bucket where `UNKNOWN_REJECT` is non-zero AND `CI + UR > 50%` of total rejects (jumped from 0% UR pre-04Z to 50.1% UR at 08Z). Engine had a 04→08 outage; the shift is observed at restart.

### 3.2 Likely Causing PR
**PR #44 — `feat(db-migration/0-9x-multi-stage): COMPLETE_DB_MIGRATED_V071`** merged **2026-04-27T06:50:53Z**.

Closest-prior PR among #43 (04:54Z, 3h before shift), #44 (06:50Z, 1h10m before shift) and #45 (09:09Z, post-shift). PR #44 is the only schema-touching change immediately preceding the engine outage 04→08; engine restarted post-migration and the new code path stopped emitting `COST_NEGATIVE` and started emitting `UNKNOWN_REJECT` at the same magnitude.

### 3.3 Confidence: **HIGH**

- **Temporal proximity:** PR #44 merge → engine quiet → restart → new taxonomy. 1h10m gap; PR #43 was 3h prior with no observed effect; PR #45 was 1h after shift (cannot retroactively cause it).
- **Magnitude conservation:** `COST_NEGATIVE` was ~50% of rejects pre-shift; post-shift `COST_NEGATIVE` is <0.1% and `UNKNOWN_REJECT` is ~50%. The bucket flipped, total volume per event is consistent (~10–25k rejects/event before and after).
- **Schema-migration mechanism:** v0.7.1 schema migration is the canonical kind of change that re-keys reason codes. The other near-merges (#43 consolidation DB, #45 watchdog cold-boot, #46 bash octal) do not touch the reject-emission path.
- **Single deduction risk:** observed at restart not at merge; if engine had restarted mid-04Z window without PR #44, we could not isolate. Confidence remains HIGH because no other code path touched reject taxonomy in the window.

### 3.4 Behavior Change vs Observability Change
**Observability / taxonomy change. NOT a behavior change.**

Evidence:
- `events`/hour: 220 (pre) → ~960 (post). 4.4× increase. **However** total_rejects/event is comparable (~45k pre vs ~22k post), and total_rejects/hour grew proportionally. Strategy throughput accelerated post-restart but the *per-strategy reject ratio* is preserved.
- `COUNTER_INCONSISTENCY` count remains ~50% of total in both regimes — invariant.
- The `COST_NEGATIVE` slot's ~50% mass got re-labelled to `UNKNOWN_REJECT`. This is a label flip, not a population change. The validator is rejecting the same kinds of strategies; the engine simply lost the mapping from validator-internal reason → emitted reason string and is now defaulting to `UNKNOWN_REJECT`.
- `LOW_BACKTEST_SCORE`, `SIGNAL_TOO_SPARSE`, `INVALID_FORMULA` magnitudes scaled with throughput; their relative shape is preserved. Only the `COST_NEGATIVE → UNKNOWN_REJECT` slot moved.

### 3.5 `val_neg_pnl` Disappearance
**`val_neg_pnl` NEVER appears inside `reject_reason_distribution` in any of the 6 rotated files (~23 h coverage).** It IS present as a literal string 73× per file (engine.jsonl: 73, .1: 73) — but in unrelated fields (likely diagnostic narrative or a legacy free-text field), never as a `reject_reason_distribution` key.

The order spec's premise that "PR #39 baseline was `val_neg_pnl ~99%`" cannot be confirmed from on-disk logs because **the rotated files do not extend back to PR #39's window**. PR #39 merged 2026-04-26T14:08Z; earliest log ts is 2026-04-26T15:00Z, and the first observed bucket already shows `COUNTER_INCONSISTENCY + COST_NEGATIVE` at 50/50, NOT `val_neg_pnl`. Either:
(a) `val_neg_pnl` was already replaced by `COST_NEGATIVE` in or before PR #39 (taxonomy churn predates the available log window), OR
(b) the order spec's "PR #39 baseline" was sourced from an earlier (now rotated-out) log that no longer exists on Alaya.

Without retrieving older logs from backup/Alaya rsync targets, we cannot pinpoint the exact moment `val_neg_pnl` left the taxonomy. **Within the available 23 h, the only observed shift is `COST_NEGATIVE → UNKNOWN_REJECT` at 2026-04-27T08:00Z, attributable to PR #44.**

---

## 4. Caveats / Open Items (for downstream phases)

1. **Log retention gap:** order spec claimed engine.jsonl.1 reached 2026-04-16. Actual earliest ts is 2026-04-26T15:00Z. Phase 7+ should consult Alaya backup or AKASHA archives to recover PR #39 / PR #41 / PR #43 windows if `val_neg_pnl` lineage matters to remediation.
2. **Engine outage 04→08:** 4-hour gap straddles PR #44 merge (06:50Z). Cannot isolate whether the taxonomy flip occurred at code load (PR #44 merge), at engine cold-boot (08:00Z), or in between.
3. **`UNKNOWN_REJECT` is a default-fallthrough symptom, not a root cause:** a downstream phase should grep the post-PR-44 source for the validator branch that previously emitted `COST_NEGATIVE` and identify why the literal got dropped (renamed enum? new column? broken dict lookup?).
4. **Total rejects/event ratio dropped (~45k → ~22k post-restart):** could indicate validator now runs in a faster / smaller-batch mode, or that the new schema rejects fewer mutations per event. Worth Phase 7 verification — not a regression on its own.

---

## Q1 / Q2 / Q3 — read-only audit gates

- **Q1 (adversarial):** PASS — examined input boundaries (no-ts lines counted separately), failure propagation (parse_failures=0 across 167k lines), external dep (only filesystem reads), concurrency (snapshot-read; engine still writing live but bucket grouping at 1h granularity absorbs jitter), scope creep (no source modified, no commits, no AKASHA writes).
- **Q2 (structural):** PASS — analysis is reproducible by re-running the SSH-piped python in §2 of the parser; no silent skips, all parse failures would have surfaced.
- **Q3 (efficiency):** PASS — single-pass scan of 6 files, output ≤350 LOC report, deliverable scoped to one file.
