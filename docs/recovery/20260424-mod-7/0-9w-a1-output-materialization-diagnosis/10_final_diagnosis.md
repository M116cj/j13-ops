# 0-9W-A1-OUTPUT-MATERIALIZATION-DIAGNOSIS — Final Diagnosis

## 1. Final Status

**DIAGNOSED_WRITE_PATH_NOT_REACHED.**

Root cause is a Python source bug in `zangetsu/services/arena_pipeline.py:1224`: the variable `_pb` (provenance bundle) is only assigned inside the per-candidate INSERT block (line 1116), so when **every** candidate in a round is rejected by the strict val-filter chain (lines 950-1100), `_pb` is never assigned. The per-round batch metrics emit at line 1218 then references `getattr(_pb, "run_id", "") or ""` and Python raises **`UnboundLocalError`** — because `_pb` is detected as a function-local but the slot was never filled. This crashes the asyncio main coroutine; the worker exits; cron's watchdog respawns it 5 min later; same crash; no candidate INSERT ever runs.

## 2. Most Likely Root Cause

**H1 — A1 DB write path is not reached** (HIGH confidence).

The exact crash trace (verbatim, observed in /tmp/zangetsu_a1_w0..w3.log every cron cycle today):

```
Traceback (most recent call last):
  File "/home/j13/j13-ops/zangetsu/services/arena_pipeline.py", line 1270, in <module>
    asyncio.run(main())
  File "/usr/lib/python3.12/asyncio/runners.py", line 194, in run
    return runner.run(main)
  File "/usr/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
  File "/usr/lib/python3.12/asyncio/base_events.py", line 687, in run_until_complete
    return future.result()
  File "/home/j13/j13-ops/zangetsu/services/arena_pipeline.py", line 1224, in main
    run_id=getattr(_pb, "run_id", "") or "",
                   ^^^
UnboundLocalError: cannot access local variable '_pb' where it is not associated with a value
```

## 3. Second Most Likely Root Cause (proximate, contributes to H1)

**H4 — eligibility filters reject all candidates before INSERT** (MEDIUM confidence).

Without H1, we'd see this manifest as 0 staging rows BUT no crash. With H1, we see 0 staging rows AND a crash; H4 is the cause that makes H1 fire. Fixing H1 unmasks H4 so it can be diagnosed in a separate order.

## 4. Third Most Likely Root Cause (proximate, contributes to H4)

**H6 — numpy overflow → NaN val signals → reject_val_constant** (MEDIUM confidence).

Workers w0..w3 all emit `RuntimeWarning: overflow encountered in square` and `... in reduce` from `numpy/_core/_methods.py:190 / :201` every cron cycle. This likely produces all-zero val signals after `nan_to_num`, failing the `np.std(av_val) < 1e-10` gate. Combined with strict thresholds (15 trades minimum, net_pnl > 0, sharpe >= 0.3, wilson_lower >= 0.52), this could cause 100% rejection per round.

## 5. Evidence Chain

```
A1 worker spawn (cron */5 watchdog)
  ✓ Imports settings (PR #31 env injection works)
  ✓ Builds indicator caches (110 arrays per symbol, 14 symbols, ~25 MB train + 25 MB holdout each)
  ✓ Loads A13 guidance (PR #34 schema VIEW works; mode=observe, BASE_WEIGHTS, survivors=0)
  ✓ Reaches main() loop ("Pipeline V10 running" log line)
  ✓ Emits ENTRY lifecycle events for ~16 candidates per cycle
  ⚠ Encounters numpy overflow on val backtests → likely 100% reject_val_constant
  ✗ Round-end emit at line 1218 references unset _pb → UnboundLocalError
  ✗ asyncio.run() exits with uncaught exception
  ✗ Worker dies before any INSERT INTO champion_pipeline_staging
  → 0 rows in staging; 0 rows in fresh; 0 rows in engine_telemetry; A23 stays idle; arena_batch_metrics never emits; CANARY never feasible
```

## 6. What Was Ruled Out

| Hypothesis | Reason |
| --- | --- |
| H2 (fresh_insert_guard blocks A1) | A1 doesn't INSERT into fresh; it INSERTs into staging which has no guard. |
| H3 (zangetsu.admission_active missing in A1 sessions) | A1's session doesn't need this setting. Only `admission_validator()` server-side does. |
| H5 (A1 stuck in cache build) | "Pipeline V10 running" + "AlphaEngine ready" + ENTRY events confirm cache build completes. |
| H7 (writes to unexpected/legacy table) | Source code only INSERTs into `champion_pipeline_staging`. |
| H8 (queue empty / disconnected) | ENTRY events confirm `alphas` list is non-empty and being iterated. |
| H10 (A13/A23/A45 root cause) | All three confirmed clean and idle for the right reason. |

## 7. What Remains Unknown

After H1 is fixed, we still need to confirm the val-filter rejection rate (H4 / H6) by reading the round-end stats line `f"rejects: few_trades=N val_few=N val_neg_pnl=N val_sharpe=N val_wr=N"` once it can be emitted. That observation is currently impossible because the crash precedes the log line.

## 8. Required Repair Type

**SOURCE PATCH (minimal — single-line initialization).**

| Field | Value |
| --- | --- |
| Repair type | source patch |
| Risk | LOW (initialization-only; does not change strategy / thresholds / Arena pass-fail) |
| File | `zangetsu/services/arena_pipeline.py` |
| Change | initialize `_pb = None` somewhere BEFORE the per-alpha loop in `main()` (e.g. just after `worker_id` is bound). |
| Compatibility | the existing `getattr(_pb, "run_id", "") or ""` already handles `_pb = None` correctly (returns `""`) |
| Tests required | re-run existing test suites (189 tests baseline); add a regression test if convenient |

## 9. Next Targeted Repair Order

**`TEAM ORDER 0-9W-A1-PB-SCOPE-FIX`** — minimal source patch:

1. Read `zangetsu/services/arena_pipeline.py:411` (start of `main()`).
2. Insert `_pb = None  # default — handles zero-candidate-passed case (see 0-9W-A1-OUTPUT-MATERIALIZATION-DIAGNOSIS)` somewhere before the per-alpha loop (suggested location: just after `_telemetry_counters` is initialized).
3. Run the 189-test baseline.
4. Sign + push + admin-merge as a single-file source PR.
5. Verify that A1 worker logs now reach the round-end stats line `rejects: few_trades=N val_few=N ...` and that `engine_telemetry` and/or `champion_pipeline_staging` start receiving rows in subsequent cron cycles.

If step 5 still shows 0 staging rows, the **next** order can be `TEAM ORDER 0-9W-VAL-FILTER-DIAGNOSIS` (read the actual rejection counts now visible in the logs and decide whether the val filters need any operational tuning — separate from this scope).

## 10. Post-Repair Validation Plan

| Check | Required |
| --- | --- |
| Re-run `0-9W-LIVE-FLOW-PROOF` Phase 4 | YES |
| Confirm `champion_pipeline_staging` has new rows | YES |
| Confirm `champion_pipeline_fresh` is gaining new rows or new statuses | YES |
| Confirm `CANDIDATE` / `DEPLOYABLE` rows appear (eventually) | YES |
| Confirm A23 begins consuming candidates | YES |
| Confirm `arena_batch_metrics.jsonl` begins writing | YES |
| Then: TEAM ORDER 0-9S-CANARY-OBSERVE-LIVE | conditional on >= 20 live arena batches |

## 11. Final Declaration

```
TEAM ORDER 0-9W-A1-OUTPUT-MATERIALIZATION-DIAGNOSIS = DIAGNOSED_WRITE_PATH_NOT_REACHED
```

Made 0 source code / 0 schema / 0 cron / 0 launcher / 0 secret changes. Made 1 commit (signed evidence-docs PR). Identified exact line + file + variable for the next narrow repair order. Forbidden changes count = 0.
