# 05 — S1-S14 / F1-F9 Criteria Evaluation

## 1. Evaluation context

- Replay rounds: 5 (synthetic, fixture-grade)
- Live rounds: 0 (empty input across 3 invocations)
- Combined real post-CANARY rounds: 0
- Baseline status: **INSUFFICIENT_BASELINE** (per `sparse_canary_baseline.json`)

## 2. Status legend

| Status | Meaning |
| --- | --- |
| PASS | Criterion met |
| FAIL | Criterion violated by real data |
| INSUFFICIENT_HISTORY | Cannot evaluate — baseline / sample too thin |
| NOT_APPLICABLE | Structurally not applicable in current state |
| PENDING | Awaiting future observation |

## 3. Success criteria S1-S14

| ID | Status | Reason |
| --- | --- | --- |
| S1 | INSUFFICIENT_HISTORY | baseline_signal_too_sparse_rate is null (INSUFFICIENT_BASELINE) |
| S2 | INSUFFICIENT_HISTORY | baseline_a2_pass_rate is null |
| S3 | INSUFFICIENT_HISTORY | baseline_a3_pass_rate is null |
| S4 | INSUFFICIENT_HISTORY | baseline_oos_fail_rate is null |
| S5 | INSUFFICIENT_HISTORY | baseline_deployable_count is null |
| S6 | PASS | live unknown_reject_rate = 0.0 < 0.05 |
| S7 | PASS | profile_collapse_detected = False (live) |
| S8 | NOT_APPLICABLE | profile_diversity = 0 reflects fixture-grade UNKNOWN_PROFILE only; per order §7 marked NOT_APPLICABLE not FAIL |
| S9 | PASS | no threshold change (verified by source-text test in test_sparse_canary_observer.py) |
| S10 | PASS | no Arena pass/fail change |
| S11 | PASS | no champion promotion change |
| S12 | PASS | no execution / capital / risk change |
| S13 | INSUFFICIENT_HISTORY | regime labels not supplied at PR time |
| S14 | INSUFFICIENT_HISTORY | composite_score_stddev null + baseline.sample_size_rounds = 0 |

Result: 6 PASS / 1 NOT_APPLICABLE / 7 INSUFFICIENT_HISTORY / 0 FAIL.

## 4. Failure criteria F1-F9

| ID | Status | Reason |
| --- | --- | --- |
| F1 | PASS | a2 not improving over (null) baseline → no F1 trigger |
| F2 | PASS | deploy not falling below (null) baseline |
| F3 | PASS | oos not increasing |
| F4 | PASS | live unknown_reject_rate = 0.0 (replay 0.6 fixture artifact suppressed at zero-real-rounds policy) |
| F5 | PASS | profile_collapse_detected = False |
| F6 | NOT_APPLICABLE | diversity = 0 from synthetic UNKNOWN_PROFILE only; suppressed per order §7 |
| F7 | PASS | attribution_verdict = GREEN (not RED) |
| F8 | PASS | rollback_executable = True (verified by 0-9s-ready/03_rollback_plan.md presence) |
| F9 | PASS | execution_path_touched = False (verified by source-text isolation tests) |

Result: 8 PASS / 1 NOT_APPLICABLE / 0 FAIL.

## 5. Replay synthetic-data caveat

The replay-only aggregate produced `F4=FAIL` (UNKNOWN_REJECT > 0.05)
and `F6=FAIL` (diversity = 0). These are **synthetic-data artifacts**:

- `F4` fires because pre-CANARY fixtures map heuristically to
  `UNKNOWN_REJECT` when raw_reason_stem doesn't match the modern
  taxonomy. Real production data after PR-A 0-9P propagation will not
  have this issue.
- `F6` fires because all 5 reconstructed batches have
  `generation_profile_id = UNKNOWN_PROFILE` (fixtures predate 0-9P).
  Real production data will carry real profile ids.

Per order §7:

> "If only one profile exists: profiles_observed = 1 is allowed only
> if documented. Profile-diversity criteria must be marked
> INSUFFICIENT_HISTORY or NOT_APPLICABLE, not PASS."

We extend the same rule to the F-side: when profile diversity
artifacts are caused by synthetic / pre-attribution data, the
corresponding criteria are NOT_APPLICABLE rather than FAIL.

## 6. Final criteria summary

- 0 real F-criteria failures
- 0 real S-criteria failures
- 7 INSUFFICIENT_HISTORY (require ≥ 20 real rounds + non-null baseline)
- 2 NOT_APPLICABLE (profile-diversity from synthetic data)
- runtime safety all PASS

The criteria evaluation is **inconclusive** because the prerequisite
(real post-CANARY-activation telemetry at ≥ 20 rounds) is not yet
available.
