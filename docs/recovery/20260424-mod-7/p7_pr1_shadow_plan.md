# P7-PR1 SHADOW Plan — Arena Rejection Taxonomy + Telemetry Baseline

Per TEAM ORDER 0-9E §14. This plan defines how the P7-PR1 artifacts are exercised in SHADOW mode (observation-only, no runtime mutation).

## 1. Scope

- Run Arena pipeline telemetry in **non-mutating observation mode**.
- Collect rejection traces by parsing existing Arena runtime logs, classifying raw reject-strings via `arena_rejection_taxonomy.classify()`, and aggregating through `arena_telemetry.TelemetryCollector`.
- Compute `derive_deployable_count(lifecycles)` from parsed logs to surface the provenance of `deployable_count == 0`.
- Produce a structured JSON summary suitable for Phase 7 Arena 2 diagnostic review.

Scope is strictly limited to observation. **No writes to any Arena runtime file, no threshold change, no live service restart, no candidate promotion, no capital allocation.**

## 2. Expected behavior

During SHADOW:
- Candidate pass / fail outcomes: **unchanged** (same inputs → same outputs).
- Rejection traces: **emitted** by the SHADOW wrapper that parses existing log output.
- Arena 2 rejection breakdown: **visible** via `TelemetryCollector.arena2_breakdown()`.
- `deployable_count` source trace: **visible** via `derive_deployable_count(lifecycles)` — returns breakdown_by_current_stage, breakdown_by_reject_reason, rejected_ids_by_stage, non_deployable_reasons.
- `UNKNOWN_REJECT` ratio: **measurable** via `TelemetryCollector.unknown_reject_ratio()` — target < 10 %. If > 10 %, the classifier's `RAW_TO_REASON` must be extended before P7-PR2.

## 3. Forbidden during SHADOW

- No threshold change (`arena_gates.A2_MIN_TRADES`, `A3_MIN_*`, etc. must remain at main @ 966cd593 values).
- No champion promotion rule change.
- No live trading mutation (no order submission, no cancellation, no position change).
- No capital allocation change (sub-account balances untouched).
- No execution behavior change (execution engine path unchanged).
- No modification of any file under `zangetsu/services/arena_*.py`, `calcifer/`, or `scripts/` outside the P7-PR1 authorized scope.
- No branch protection change.

## 4. SHADOW activation mechanism

SHADOW is activated by a **separate authorized order** (not by this PR). The recommended activation pattern for a future order:

- Invoke the Arena pipeline as normal.
- Capture its stdout / stderr / log output into a buffer.
- Post-process the buffer with a SHADOW wrapper that calls `arena_telemetry.make_rejection_trace(...)` for each parsed rejection line, populates a `TelemetryCollector`, and writes the collector's `summary()` to `docs/rehearsal/p7-pr1/shadow_execution_log.txt`.
- The Arena pipeline's actual decisions and writes are untouched; the SHADOW wrapper is a passive reader of output.

This PR does not ship the SHADOW wrapper itself. This PR provides only the taxonomy + telemetry + trace API that a future wrapper can invoke. SHADOW activation ≥ P7-PR1-SHADOW order.

## 5. Evidence files (for SHADOW run, produced by future order)

```
docs/rehearsal/p7-pr1/
  shadow_plan.md              ← reference to this file
  shadow_execution_log.txt    ← raw pipeline stdout + classified summary
  shadow_verdict.md           ← pass/fail with forbidden-diff result
```

## 6. SHADOW exit criteria (PASS)

- Telemetry records emit and serialize to valid JSON (schema round-trip tested in `test_arena_telemetry.py`).
- `unknown_reject_ratio()` < 0.10 (if exceeded, extend `RAW_TO_REASON` in a follow-up PR before P7-PR2).
- `derive_deployable_count()` returns non-empty `non_deployable_reasons` when `deployable_count == 0` (i.e., the "why zero" question is answerable).
- Controlled-diff (pre-SHADOW vs post-SHADOW) returns **EXPLAINED** with **zero forbidden diff**.
- No runtime instability observed (engine.jsonl mtime continues to tick per normal cadence; no new error lines in service logs).
- Arena 2 `arena2_breakdown()` contains at least 3 distinct canonical reasons (Arena 2 previously produced only "A2 REJECTED" logs without structured categorization — SHADOW must break this down).

## 7. SHADOW duration

Minimum observation window: **one full Arena 1→2→3 pipeline run** (duration is corpus-dependent; typically 60–180 minutes). Extended observation (≥ 24 hours) is recommended before authorizing CANARY.

## 8. Rollback during SHADOW

SHADOW does not write to production state, so rollback is trivial:
- Terminate the SHADOW wrapper process.
- Delete `docs/rehearsal/p7-pr1/shadow_execution_log.txt` if a retention decision is made.
- No service restart, no revert-commit, no data migration required.

## 9. Pre-CANARY gate

Before a CANARY order is authorized, SHADOW must have:
- Run at least once with PASS verdict.
- `unknown_reject_ratio()` stable < 0.10 across two consecutive runs.
- Arena 2 breakdown produces actionable signal (at least one dominant reason identified, e.g., OOS_FAIL vs SIGNAL_TOO_SPARSE).

If any pre-CANARY criterion fails, SHADOW must be re-run (with taxonomy mapping extended if needed) before CANARY is requested.
