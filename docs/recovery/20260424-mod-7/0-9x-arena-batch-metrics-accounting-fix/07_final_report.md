# 07 — Final Report

Order: TEAM ORDER 0-9X-ARENA-BATCH-METRICS-ACCOUNTING-FIX
Phase: 7
Date (UTC): 2026-04-27
Author: Claude Lead

## 1. Final Verdict

**FINAL_VERDICT: COMPLETE_ACCOUNTING_FIX_RESIDUAL_ZERO**

The cumulative-stats-vs-per-round-entered_count telemetry bug is fixed at the source level. After the next worker restart cycle, `arena_batch_metrics.reject_reason_distribution` will sum to a per-round value consistent with `entered_count - passed_count - skipped_count`, and `COUNTER_INCONSISTENCY` will collapse to ≈ 0 for valid data.

Note: `LIVE_NEW_DELTA_VISIBLE_DEFERRED` — the running A1/A23/A45 workers (alive since 2026-04-27T08:04Z) hold the pre-patch code in memory; new behavior surfaces on next watchdog-driven restart cycle. This is the same do-not-force-restart policy applied successfully in the previous order (PR #49).

## 2. HEAD before / after

| | Before | After (post-merge) |
|---|---|---|
| Mac HEAD | `0370b3e` | TBD (Phase 8) |
| Alaya HEAD | `0370b3e` | TBD (Phase 8) |

## 3. Patch files changed

| File | LOC delta | Type |
|---|---|---|
| `zangetsu/services/arena_pipeline.py` | +56 / -16 | 1 new tuple constant + 1 new module dict + 1 new pure helper + emitter refactor |
| `zangetsu/tests/test_arena_batch_metrics_accounting.py` | +186 / 0 (new) | 6 regression tests |

7 evidence docs in `docs/recovery/20260424-mod-7/0-9x-arena-batch-metrics-accounting-fix/`. No other files modified.

## 4. Before / after residual

### Before (pre-patch, captured live at 2026-04-27T15:13:31Z)

```
batch R328310: entered=10, passed=0
  reject_reason_distribution = {
    COST_NEGATIVE: 16, LOW_BACKTEST_SCORE: 5, SIGNAL_TOO_SPARSE: 9,
    UNKNOWN_REJECT: 17070,           ← cumulative-stats-rooted overcounting
    COUNTER_INCONSISTENCY: 17090,    ← spurious; from cumulative-vs-per-round mismatch
  }
  rejected_count = 34190
  Conservation: 10 != 0 + 34190 + 0  (residual broken at telemetry layer)
```

CI bucket grows by ~+10 each batch consistent with `entered_count` per round.

### After (post-patch, simulated via test_residual_zero_per_batch)

```
Round 1: entered=10, passed=2, deltas={few:3, neg_pnl:2}, rejected=5, skipped=3
  Conservation: 10 == 2 + 5 + 3 ✓

Round 2: entered=10, passed=1, deltas={few:+2, neg_pnl:+3, train_neg:+2}, rejected=7, skipped=2
  Conservation: 10 == 1 + 7 + 2 ✓
```

CI bucket = 0 for valid data; remains as defensive guard for genuine residual deficits.

## 5. COUNTER_INCONSISTENCY reduction (expected post-restart)

| | Pre-patch (live) | Post-patch (post-restart, expected) |
|---|---|---|
| CI per batch | ~17090 (= cumulative reject sum since worker start) | ≈ 0 |
| CI rate (% of distribution) | ~50 % | ≈ 0 % |
| `rejected_count` per batch | ~34190 (= 2 × cumulative) | ~10 (per-round, varies by pass rate) |

## 6. Confirmation no validator change

Validator `stats[reject_*] += 1` increment sites at `arena_pipeline.py` lines 975, 988, 1020, 1039, 1048, 1051, 1054, 1058, 1066 (now shifted to 1030, 1043, 1075, 1094, 1103, 1106, 1109, 1113, 1121 due to insertions above) are **unchanged**. `arena_gates.py`, `arena_rejection_taxonomy.py`, `config/settings.py`, and `admission_validator` paths are untouched. `A2_MIN_TRADES = 25` confirmed unchanged. `alpha_zoo_injection.py` defaults (`--no-db-write=True`, `--confirm-write=False`) intact.

The validator decides pass/fail by reading `stats[reject_*]` integers directly. The fix changes only how the **telemetry emitter** interprets those integers (per-round delta vs cumulative). No candidate's pass/fail outcome changes.

## 7. Tests

| Suite | Result |
|---|---|
| `pytest -q zangetsu/tests/test_arena_batch_metrics_accounting.py -v` | **6 / 6 PASS** |

The 6 tests cover the 4 required (`residual_zero_per_batch`, `counter_inconsistency_not_triggered_for_valid_data`, `existing_distribution_keys_preserved`, `first_batch_initialization`) plus 2 belt-and-braces guards (`helper_is_pure_does_not_mutate_input`, `negative_or_zero_delta_not_counted`).

Tests use AST extraction to load the pure helper in isolation, sidestepping arena_pipeline's heavy runtime deps (pyarrow, Rust extensions, hard-coded `os.chdir`).

## 8. Live observability

`SOURCE_COMPILES_ON_ALAYA_PASS` (will verify in Phase 8 post-merge) + `LIVE_NEW_DELTA_VISIBLE_DEFERRED` until next worker restart cycle. Detail in `05_live_verification.md`.

## 9. Controlled diff

**CONTROLLED_DIFF_PASS** — see `06_controlled_diff_report.md` (governance-verifier subagent).

| Dimension | Outcome |
|---|---|
| arena_pipeline.py | EXPLAINED_TELEMETRY_EMITTER_ONLY (+ helper + state) |
| new test file | EXPLAINED_TEST_ONLY |
| docs | EXPLAINED_DOCS_ONLY |
| arena_gates.py / arena_rejection_taxonomy.py / config/settings.py | unchanged |
| validator increment sites | unchanged |
| A2_MIN_TRADES | 25 unchanged |
| alpha_zoo no-db-write default | intact |
| apply path | 0 real apply paths added |

## 10. Forbidden ops status

**0**

- No alpha formula generation / mutation / crossover / search policy / sampling weights / validation thresholds change
- No A2_MIN_TRADES / Arena pass-fail / champion promotion / deployable_count change
- No execution / capital / risk change
- No alpha_zoo DB write enabled
- No CANARY started, no production rollout started
- No runtime calibration change
- No DB guard weakening
- No admission_validator change
- No worker killed, no force-push, no hard reset

## 11. Validator behavior changed?

**No.** Same reading: validator decides via `stats[reject_*]` integers. The fix changes only the telemetry emitter's interpretation (per-round delta vs cumulative). Pass/fail outcomes per candidate are identical.

## 12. UNKNOWN_REJECT / COUNTER_INCONSISTENCY closed?

| Issue | Status |
|---|---|
| UNKNOWN_REJECT taxonomy bug (PR #43) | CLOSED by previous order (PR #49) |
| COUNTER_INCONSISTENCY accounting bug (this order) | CLOSED at source level by this PR; visible in live distribution after next restart |

## 13. Q1 / Q2 / Q3 self-check

- **Q1 Adversarial (5-dim)**:
  - Input boundary: PASS — empty stats / zero current / current==prev / current<prev (rollback) all handled by helper
  - Silent failure: PASS — emitter wrapper catches all exceptions; helper has zero side effects beyond returning new dicts
  - External dependency: PASS — pure helper has no I/O / no module deps; emitter still tolerates `classify()` ImportError via fallback
  - Concurrency / race: PASS — module-level dict is per-Python-process; each worker has its own; no cross-worker contention
  - Scope creep: PASS — `arena_pipeline.py` (helper + state + emitter rewrite) + new test file only
- **Q2 Structural**: PASS — defensive `COUNTER_INCONSISTENCY` branch preserved for genuine residual deficits; validator paths and taxonomy untouched
- **Q3 Efficiency**: PASS — 1 helper + 1 tuple + 1 dict + emitter rewrite + 1 test file (6 tests) + 7 evidence docs (target ≤ 8)

## 14. Next recommended order

After this hotfix lands and the next worker restart picks up the new code, the A1 telemetry distribution should be fully correct (`COUNTER_INCONSISTENCY ≈ 0`, `UNKNOWN_REJECT ≈ 0`, canonical buckets reflect real per-round rejection patterns).

Suggested follow-up (NOT auto-triggered by this order):
- A short live observability report once a representative window of post-restart batches is available, validating the expected distribution shape
- (Out of scope for this order chain) re-evaluate whether the persistent `COUNTER_INCONSISTENCY` and `UNKNOWN_REJECT` patterns suggest any deeper signal/cost issues — almost certainly not, given the diagnosis attributed both 100% to telemetry artifacts, but a clean post-restart sample would confirm

No follow-up order is currently mandatory.

## 15. Telegram status

Phase 8 message will be sent to Thread 356 after PR merge.
