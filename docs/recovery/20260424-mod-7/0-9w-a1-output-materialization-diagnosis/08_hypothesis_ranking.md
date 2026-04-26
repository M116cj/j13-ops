# 08 — Hypothesis Ranking

## 1. Mandatory Hypotheses (per order §13)

### H1 — A1 DB write path is not reached

| Field | Value |
| --- | --- |
| Evidence FOR | line-1218 UnboundLocalError crashes asyncio main BEFORE staging INSERT can complete a full round; 0 staging rows since A1 alive 2h 35m+ |
| Evidence AGAINST | the INSERT code (lines 1117-1158) is syntactically present and structurally correct |
| Confidence | **HIGH** |
| Required repair | source patch — initialize `_pb = None` (or default provenance bundle) BEFORE the per-alpha loop in `arena_pipeline.py:main()` |

### H2 — A1 DB write path is reached but blocked by fresh_insert_guard

| Field | Value |
| --- | --- |
| Evidence FOR | none |
| Evidence AGAINST | A1 writes to `champion_pipeline_staging` (unguarded); only `admission_validator()` server-side function writes into `champion_pipeline_fresh` (guarded). No `psycopg2.errors.InsufficientPrivilege` or `RAISE EXCEPTION` traceback in worker logs. |
| Confidence | **LOW (ruled out)** |
| Required repair | n/a |

### H3 — `zangetsu.admission_active` missing/false in A1 DB sessions

| Field | Value |
| --- | --- |
| Evidence FOR | none |
| Evidence AGAINST | A1 doesn't INSERT into `champion_pipeline_fresh` directly (only `admission_validator()` does, server-side). A1 just writes to `staging`, which has no admission guard. |
| Confidence | **LOW (ruled out)** |
| Required repair | n/a |

### H4 — A1 generates candidates but eligibility filters reject all before DB insert

| Field | Value |
| --- | --- |
| Evidence FOR | numpy overflow → NaN val signals → `nan_to_num→0.0` → `np.std(av_val) < 1e-10` → `reject_val_constant`; observed RuntimeWarnings in workers w0..w3 every cron cycle |
| Evidence AGAINST | round-end stats summary (`rejects: few_trades=N val_few=N val_neg_pnl=N val_sharpe=N val_wr=N`) is never logged because the line-1218 crash precedes the `if round_number % 10 == 0:` log block on the first round (rd 49451 % 10 = 1). So we cannot directly count which filter rejects them all. |
| Confidence | **MEDIUM (proximate cause; but masked by H1)** |
| Required repair | none in this order — fix H1 first, then observe stats output |

### H5 — A1 stuck recomputing indicator cache and never finalizes

| Field | Value |
| --- | --- |
| Evidence FOR | high-CPU during indicator-cache build phase |
| Evidence AGAINST | "Pipeline V10 running" + "Resumed from checkpoint" + "AlphaEngine ready" log lines confirm A1 EXITS the cache build phase and ENTERS the main loop; ENTRY events fire after that |
| Confidence | **LOW (ruled out)** |
| Required repair | n/a |

### H6 — numpy overflow causes batch invalidation before INSERT

| Field | Value |
| --- | --- |
| Evidence FOR | numpy overflow warnings; `nan_to_num` masks the issue |
| Evidence AGAINST | overflow at numerical level is caught and converted to `reject_val_constant` per-candidate; this would cause the round to have 0 passes but the round itself would COMPLETE (not crash) if the source code at line 1218 didn't have the `_pb` bug |
| Confidence | **MEDIUM (proximate cause; but root is H1)** |
| Required repair | numpy overflow may be a separate strategy concern, but does NOT need a patch in this order |

### H7 — A1 writes to unexpected/legacy table

| Field | Value |
| --- | --- |
| Evidence FOR | none |
| Evidence AGAINST | code at line 1117 explicitly INSERTs into `champion_pipeline_staging`; no INSERT statements pointing at `champion_legacy_archive` or other locations |
| Confidence | **LOW (ruled out)** |
| Required repair | n/a |

### H8 — A1 output queue is empty or disconnected

| Field | Value |
| --- | --- |
| Evidence FOR | none |
| Evidence AGAINST | ENTRY lifecycle events confirm `alphas` list is non-empty and being iterated |
| Confidence | **LOW (ruled out)** |
| Required repair | n/a |

### H9 — engine_telemetry disabled or broken (secondary)

| Field | Value |
| --- | --- |
| Evidence FOR | engine_telemetry table is empty |
| Evidence AGAINST | `_flush_telemetry` is intact and DOES write the table — it's just never called because the staging INSERT never runs (per H1) |
| Confidence | **LOW (this is symptom of H1, not root cause)** |
| Required repair | n/a — fixed automatically when H1 is fixed |

### H10 — A13 / A23 / A45 are not root cause

| Field | Value |
| --- | --- |
| Evidence FOR | A13 feedback: 12+ clean runs since PR #34, 0 errors. A23 + A45: alive 2h 35m+, idle for the right reason (no candidates exist). |
| Evidence AGAINST | none |
| Confidence | **HIGH (confirmed not root cause)** |
| Required repair | n/a |

## 2. Top Root Cause Ranking

1. **H1 — A1 DB write path is not reached** (HIGH confidence, root cause)
2. **H4 — Eligibility filters reject all** (MEDIUM, proximate cause that triggers H1's crash)
3. **H6 — Numpy overflow causes per-candidate rejection** (MEDIUM, proximate cause that feeds H4)

## 3. Required Repair Type

**source patch** (minimal):

```python
# In zangetsu/services/arena_pipeline.py, somewhere BEFORE the inner per-alpha loop in main():
_pb = None  # default — handles the zero-candidate-passed-all-val-gates case

# Existing code at line 1116 stays unchanged; it overwrites _pb when a candidate passes:
_pb = _get_or_build_provenance(engine, worker_id, ...)
```

Plus the line-1218 call already uses `getattr(_pb, "run_id", "")`, which correctly handles `_pb = None` (returns `""`). So the only change needed is the initialization.

This is a **single-line config-style source change** — not a strategy / threshold / Arena-pass-fail change. It restores the existing intent of the line-1218 author (who clearly meant for it to be safe via `getattr` default).

## 4. Secondary Concern (out of scope for this order)

After H1 is fixed, the system will produce stats output. Then we can directly observe whether all candidates are being rejected by val filters (and at which gate). If observation shows 100% rejection at `reject_val_constant`, a **separate** strategy-tuning order may be needed to address numpy overflow (e.g. tighter pre-processing, different indicator scaling, mid-price normalization). That repair would be a strategy change and outside the current investigation scope.
