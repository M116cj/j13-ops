# 03 — Criteria Evaluation

## 1. Evaluation context

- Window: empty (rounds_observed = 0)
- Telemetry sources: none supplied at PR time
- Status: **OBSERVING_NOT_COMPLETE**

Most delta-style criteria report `INSUFFICIENT_HISTORY` because the
baseline `sample_size_rounds = 0`. Caller-flag-style criteria (S9-S12)
report PASS at PR time because no governance flag is dropped.

## 2. Success criteria S1-S14 (live tool output)

| ID | Status | Reason |
| --- | --- | --- |
| S1 | INSUFFICIENT_HISTORY | baseline.sample_size_rounds = 0 |
| S2 | INSUFFICIENT_HISTORY | baseline.sample_size_rounds = 0 |
| S3 | INSUFFICIENT_HISTORY | baseline.sample_size_rounds = 0 |
| S4 | INSUFFICIENT_HISTORY | baseline.sample_size_rounds = 0 |
| S5 | INSUFFICIENT_HISTORY | baseline.sample_size_rounds = 0 |
| S6 | PASS | unknown_reject_rate = 0.0 < 0.05 |
| S7 | PASS | profile_collapse_detected = False |
| S8 | FAIL | profile_diversity_score = 0.0 (no profiles observed yet) |
| S9 | PASS | no threshold change (caller flag) |
| S10 | PASS | no Arena pass/fail change (caller flag) |
| S11 | PASS | no champion promotion change (caller flag) |
| S12 | PASS | no execution / capital / risk change (caller flag) |
| S13 | INSUFFICIENT_HISTORY | per_regime_stable=None (regime labels not supplied at PR time) |
| S14 | INSUFFICIENT_HISTORY | baseline.sample_size_rounds = 0 + composite_score_stddev = None |

S8 reports FAIL only because the empty-input PR-time invocation has
no profiles to evaluate; this is **expected** for a zero-round run and
will resolve to PASS once continuous observation collects profile
weights from the dry-run consumer's plans.

## 3. Failure criteria F1-F9

The runner's status logic suppresses F-criteria evaluation when
`rounds_observed == 0` because empty inputs would falsely trigger F6
(no profiles → diversity=0 → "exploration floor violated"). The
runner-level `rollback_required` is **False**.

For transparency, the observer module's evaluator was still called
and its output is preserved in the observation record:

| ID | Status (live) | Note |
| --- | --- | --- |
| F1 | PASS | a2 not improving over baseline (both 0) |
| F2 | PASS | deploy not falling (both 0) |
| F3 | PASS | oos not increasing |
| F4 | PASS | unknown_reject_rate = 0.0 < 0.05 |
| F5 | PASS | profile_collapse_detected = False |
| F6 | FAIL | profile_diversity_score = 0.0 — **suppressed by runner** because rounds_observed = 0 |
| F7 | PASS | attribution_verdict GREEN, not RED |
| F8 | PASS | rollback_executable = True |
| F9 | PASS | execution_path_touched = False |

**Runner-level decision:** `rollback_required = False`, `status =
OBSERVING_NOT_COMPLETE`. F6 is informational only at zero rounds.

## 4. Re-evaluation contract

Once the continuous observation order runs and `rounds_observed >= 20`:

- S1-S5 + S14 unblock from `INSUFFICIENT_HISTORY`
- S8 + F6 will reflect actual profile diversity from observed plans
- S13 unblocks if regime labels are supplied
- composite_score_stddev becomes populated, enabling S14 sigma-test

The runner's status machine is:

```
rounds_observed == 0          → OBSERVING_NOT_COMPLETE  (F skipped)
rounds_observed > 0
  + any F == FAIL              → FAILED_OBSERVATION
  + observation_window_complete (>= MIN_ROUNDS_FOR_COMPLETE = 20)
      + all S in {PASS, INSUFFICIENT_HISTORY} → OBSERVATION_COMPLETE_GREEN
      + otherwise                              → OBSERVING_NOT_COMPLETE
  + observation_window_complete == False → OBSERVING_NOT_COMPLETE
```

## 5. Verification commands

```
python3 -m pytest \
  zangetsu/tests/test_sparse_canary_observer.py \
  zangetsu/tests/test_sparse_canary_readiness.py \
  zangetsu/tests/test_sparse_canary_observation_runner.py
# expected: 135 / 135 PASS
```

## 6. Final criteria status (this PR)

- S1, S2, S3, S4, S5, S13, S14: INSUFFICIENT_HISTORY
- S6, S7, S9, S10, S11, S12: PASS
- S8: FAIL (suppressed at PR time; will re-evaluate)
- F1-F5, F7-F9: PASS
- F6: FAIL (suppressed at zero rounds; will re-evaluate)
- Runner-level rollback_required: **False**
- Runner-level status: **OBSERVING_NOT_COMPLETE**
