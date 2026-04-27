# 08 — Final Report

Order: TEAM ORDER 0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS
Phase: 8
Date (UTC): 2026-04-27
Author: Claude Lead

## 1. Final Verdict

**FINAL_VERDICT: DIAGNOSED_UNKNOWN_REJECT_TAXONOMY_BUG**

Co-equal secondary finding (separately scoped):
**DIAGNOSED_COUNTER_INCONSISTENCY_TELEMETRY_BUG** — same root-cause class as the order's `COUNTER_INCONSISTENCY_TELEMETRY_BUG` option. Requires its own hotfix order.

Two independent bugs were identified, both confined to the telemetry layer. The primary verdict reflects the dominant visible symptom; the secondary finding is reported with equal evidentiary support and a separate recommended next order.

## 2. Repo / Runtime State

| Field | Value |
|---|---|
| HEAD | `b1615c67eeefa69f0a001a89625337d973d644b7` |
| Branch | `main` (Mac and Alaya at parity) |
| Source parity vs origin/main | 0 (`zangetsu/`, `docs/`, `scripts/`, `tests/`, `bin/`, `Makefile`) |
| Worker process status | 6 / 6 alive (etime 05:54+ since 2026-04-27T08:04Z post cold-boot) |
| Lockfile status | 6 / 6 present in `/tmp/zangetsu/` |
| DB schema | v0.7.1 visible (champion_pipeline=89, staging=184, fresh=89, rejected=0) |
| Watchdog cron | stable, last 8 ticks all healthy |

## 3. Live Reject Distribution (3-hour snapshot, 726 batches)

| Reason | Count | % |
|---|---|---|
| `COUNTER_INCONSISTENCY` | 7,648,410 | 50.02 % |
| `UNKNOWN_REJECT` | 7,641,019 | 49.97 % |
| `COST_NEGATIVE` | 6,928 | 0.045 % |
| `SIGNAL_TOO_SPARSE` | 5,357 | 0.035 % |
| `LOW_BACKTEST_SCORE` | 2,366 | 0.015 % |

Per-batch CI consistently exceeds UR by ~+2; 0/726 batches have CI = UR exactly.

## 4. Previous Distribution Baseline

Per order spec, PR #39 era was `val_neg_pnl ~99 %`. On-disk log retention does NOT extend to PR #39 — the earliest timestamp in any rotated log is 2026-04-26T15:00 Z (~23 h coverage at diagnosis time). Baseline is therefore inferred from order spec + decision-record references (`docs/decisions/20260422-valgate-counterfactual-audit.md` cites "72 % cells died from train_neg_pnl") rather than direct log replay.

## 5. Exact Shift Window

First hourly bucket where `UNKNOWN_REJECT` is non-zero AND `CI + UR` exceeds 50 % of total rejects: **2026-04-27T08:00 Z**. The shift is a **post-restart re-emergence** of an in-place bug that pre-dates the visible window — the engine had been silent 04 Z → 08 Z during the Alaya reboot + cold-boot recovery (PR #45). When workers re-spawned at 08:04 Z under the same source revision, the buggy taxonomy mapping immediately surfaced the dominant CI + UR pattern.

## 6. Root Cause — UNKNOWN_REJECT (file `04_unknown_reject_root_cause.md`)

`UNKNOWN_REJECT` is a fallback bucket emitted by `arena_rejection_taxonomy.classify()` when the supplied raw stats key has no entry in `RAW_TO_REASON`. PR #43 (commit `c873857`) introduced two new stats keys — `reject_train_neg_pnl` and `reject_combined_sharpe_low` — and added them to the emitter iteration tuple at `arena_pipeline.py:206-209`, but did **not** add corresponding entries to `RAW_TO_REASON`. Every rejection that increments those two stats keys is therefore mapped to UNKNOWN_REJECT.

Verified by direct module import on Mac:
```
RAW_TO_REASON.get("reject_train_neg_pnl")     = <<NOT IN MAP>>
RAW_TO_REASON.get("reject_combined_sharpe_low") = <<NOT IN MAP>>
```

## 7. Root Cause — COUNTER_INCONSISTENCY (file `05_counter_inconsistency_root_cause.md`)

`COUNTER_INCONSISTENCY` is a per-emit residual delta from `entered_count - passed_count - rejected_count` going negative. The structural defect is that `stats` (initialized at `arena_pipeline.py:707-723`) is **worker-lifetime cumulative** while `entered_count = len(alphas)` passed into `_emit_a1_batch_metrics_from_stats_safe()` is per-round. After warmup, cumulative `rejected_count >> entered_count`, so the negative-residual branch (`arena_pipeline.py:229-232`) trips every emit, adding `abs(residual)` to a `COUNTER_INCONSISTENCY` bucket and to `rejected_count`. This is independent of the UR taxonomy issue and would persist even after taxonomy fix.

## 8. `val_neg_pnl` Status

The literal `val_neg_pnl` was **not renamed**. The stats key `reject_val_neg_pnl` is still alive (initialized line 717, incremented line 1051) and is canonically mapped to `RejectionReason.COST_NEGATIVE` in `RAW_TO_REASON` (taxonomy.py:248). Phase 1 confirmed 72 occurrences of `val_neg_pnl=N` in legacy text-format INFO summary lines (`arena_pipeline.py:1240`); they never appear as a key in `reject_reason_distribution` because the canonical-mapped value goes into the `COST_NEGATIVE` bucket. There is no missing-rename bug at this name.

## 9. PR Contribution Summary

| PR | Effect on this issue |
|---|---|
| #39 | Established `val_neg_pnl ~99 %` baseline (out of log retention window) |
| #41 | Calibration survivor artifact rejected — unrelated to taxonomy |
| #43 (`c873857`) | **Primary cause of UNKNOWN_REJECT bug** — added two new stats keys without corresponding `RAW_TO_REASON` entries |
| #44 | DB schema migration to v0.7.1 — does NOT touch `arena_rejection_taxonomy.py`, `arena_pipeline.py`, or telemetry code |
| #45 | Watchdog cold-boot recovery — restart timing of post-recovery workers explains why the shift became visible at 08 Z, but PR #45 is not the causal factor |
| #46 | Bash octal hotfix — unrelated to A1 logic |
| #47 | Docs-only — unrelated |

The Phase 6 subagent attribution to PR #44 is reframed: the **shift_start observed time** of 08 Z is post-PR #45 cold-boot, but the **causal change** is PR #43 (which preceded the visible window and is therefore not visible in the on-disk hourly buckets). The cumulative-stats CI bug is older than this entire window and may pre-date PR #43; on-disk logs cannot resolve its origin.

## 10. Behavior vs Observability

**Observability/taxonomy only**, NOT behavioral. The validator is rejecting the same population of candidates as before; only the `reject_reason_distribution` labelling has shifted because two reject keys flow through the fallback path. Total reject count and pass rate are unaffected by the taxonomy fix. The CI bug also produces fictitious counts in the telemetry but does not change strategy outcomes.

## 11. Patch Required?

Yes — but **not implemented in this diagnosis order**. Two separate runtime-touching hotfix orders are required.

## 12. Patch Safety Profile

A1: **Taxonomy hotfix** — adding two entries to `RAW_TO_REASON` is one of the safest classes of patch in this codebase: the dict is module-level, read-only at runtime, and the `classify()` fallback ensures backward compatibility. No alpha / Arena pass-fail / threshold / DB / execution change. Risk: LOW.

A2: **Telemetry accounting fix** — modifying the `_emit_a1_batch_metrics_from_stats_safe` contract to use per-round deltas (or per-emit reset) touches the telemetry layer only. Care must be taken not to break the legacy text-format INFO summary at line 1237-1242, which reads cumulative stats. Risk: LOW-MEDIUM (requires regression test on residual semantics).

## 13. Forbidden-Ops Status

**0 — see `07_controlled_diff_report.md`**

- `A2_MIN_TRADES = 25` unchanged (`arena_gates.py:48`, `settings.py:29`)
- `alpha_zoo_injection.py` retains `--no-db-write default=True`
- No apply path / runtime-switchable budget added
- No Arena pass/fail / champion promotion / deployable_count change
- No execution / capital / risk change
- No DB guard weakening
- All `/tmp/0_9x_*` parser scripts uncommitted
- 8 evidence markdowns added to `docs/recovery/.../0-9x-a1-reject-distribution-shift-diagnosis/`; zero source/test/config files modified

## 14. Next Recommended Orders

Per order spec recommendation table, two parallel hotfix orders are the appropriate response:

1. **`TEAM ORDER 0-9X-A1-REJECT-TAXONOMY-HOTFIX`** (primary, blocks UR fallback)
   - Add 2 entries to `RAW_TO_REASON` in `arena_rejection_taxonomy.py`
   - Suggested mapping:
     - `"reject_train_neg_pnl" → RejectionReason.COST_NEGATIVE`
     - `"reject_combined_sharpe_low" → RejectionReason.LOW_BACKTEST_SCORE`
   - Add a contract test: `set(emitter_stats_keys) ⊆ set(RAW_TO_REASON.keys())`

2. **`TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX`** (parallel, blocks CI false signal)
   - Refactor `_emit_a1_batch_metrics_from_stats_safe` to use per-round deltas (preferred) or per-emit reset (simpler)
   - Add regression test: single-round emit with no skip → residual = 0, CI bucket = 0

Both can be developed and merged independently; their merge order does not matter.

## 15. Q1 / Q2 / Q3 Self-Check

- **Q1 Adversarial (5-dim)**: PASS — every classification verified against raw log evidence + direct code/data inspection; UR/CI separation verified by per-batch delta analysis (CI > UR consistently); no inferred-from-inference chains.
- **Q2 Structural**: PASS — read-only operations only; no runtime touched; pre-existing logging path preserved; no regression introduced.
- **Q3 Efficiency**: PASS — 9 evidence files (target ≤ 10); subagents dispatched in parallel where possible; no broad full-suite tests; no source patch.

## 16. Telegram Status

Phase 9 message will be sent to Thread 356 after PR merge.
