# 02 — Risk Register (Subprogram A)

Risks tracked across the 0-9Y master program. Each risk has a severity (P0/P1/P2), an owning subprogram, and a containment posture.

## Active risks

### R-1 — Telemetry exposure adds field-name collision or schema drift
- **Severity:** P1
- **Owner:** B1
- **Description:** Adding `gross_pnl` / `net_pnl` / cost-component fields to the `arena_batch_metrics` event must not collide with existing field names or break downstream parsers (`generation_profile_metrics.py`, `sparse_canary_observer.py`, `run_sparse_canary_observation.py`, `replay_sparse_canary_observation.py`).
- **Containment:** B1 must read all consumers before adding fields; new fields are additive; existing field semantics must not change. Tests must verify all existing parsers still work.
- **STOP if:** any existing parser breaks.

### R-2 — Telemetry conservation guarantee broken by exposure work
- **Severity:** P0
- **Owner:** B1
- **Description:** PR #50 established that `entered_count = passed_count + sum(reject_reason_distribution.values()) + skipped_count`. Any new field MUST NOT be confused with the existing canonical four. Especially: do not change `reject_reason_distribution` semantics.
- **Containment:** B1 final test must re-run the conservation parser from PR #51 (96/96 batches residual=0). If new fields are added inside the dict, re-evaluate parser.
- **STOP if:** residual ≠ 0 in any batch after deploy.

### R-3 — Engine_telemetry repair triggers DB write storm
- **Severity:** P1
- **Owner:** B2
- **Description:** If B2 fixes the silent `try: ... except: pass` insert at `arena_pipeline.py:385`, a retroactive flush could write a large backlog at once, OR per-round flushes might add many rows quickly.
- **Containment:** B2 patch must include explicit flush rate-limiting OR a documented decision that DB telemetry is obsolete (`COMPLETE_ENGINE_JSONL_CANONICAL_DB_TELEMETRY_OBSOLETE` verdict). If repaired, monitor for storm in 24h window.
- **STOP if:** insert rate > 10/min sustained or DB connection exhaustion observed.

### R-4 — Calcifer NULL-safety patch creates false RED on cold-start
- **Severity:** P1
- **Owner:** B3
- **Description:** §17.3 says `deployable_count==0 AND last_live_at_age_h>6 → RED`. With `COALESCE(last_live_at_age_h, 999) > 6`, a system in genuine cold-start (never had a live champion) immediately turns RED — which is the **intended** new semantics, but it would block any `feat(zangetsu/vN)` commit per §17.3 enforcement. The §17.5 bump_version.py also depends on this.
- **Containment:** B3 must patch the predicate AND coordinate with §17.3's deploy-block writer so cold-start is distinguishable from "deploy regression". Possible escape hatch: add a third state (UNKNOWN_BLOCKED vs RED) so cold-start does not mask actual outcome regressions.
- **STOP if:** patch turns RED without explicit mechanism for cold-start exit.

### R-5 — Subprogram E implementation accidentally weakens validation
- **Severity:** P0
- **Owner:** E1/E2/E3/E4
- **Description:** Master order forbids "validation weakening". Adding new target labels (E1) or new operators (E2) could *implicitly* lower gate strictness if the same numerical thresholds become looser in the new feature space.
- **Containment:** E1/E2/E3/E4 must run **shadow / dry-run** evaluation that uses the *current* validation gates unchanged; only the alpha generation universe expands. No changes to `A2_MIN_TRADES`, `A3_WR_FLOOR`, `A4_REGIME_WR_FLOOR`, `reject_train_neg_pnl` gate, etc.
- **STOP if:** any E-phase patch touches `zangetsu/services/arena_gates.py` or the `reject_train_neg_pnl` gate at `arena_pipeline.py:1042`.

### R-6 — Strategic redesign without economic-edge evidence creates wishful thinking
- **Severity:** P0
- **Owner:** D depends on C
- **Description:** D should propose paths only after C's evidence is available. Without B1's `gross_pnl` exposure, C cannot distinguish "gross < 0" from "0 < gross < cost". Skipping C and going straight to D risks recommending P2/P3 without empirical justification.
- **Containment:** Strict subprogram order. Do not start D until C completes with non-`BLOCKED_METRICS_INSUFFICIENT` verdict.
- **STOP if:** C verdict = `BLOCKED_METRICS_INSUFFICIENT` — return to B1 for additional metrics.

### R-7 — Runtime instability during long subprogram E build
- **Severity:** P1
- **Owner:** all
- **Description:** Source-touching subprograms (B1/B2/B3/E*) require reasonable runtime stability. If A1 workers crash or watchdog enters loop during the program, all in-flight work is suspect.
- **Containment:** Re-run §17.6 stale-check at every PR's Phase 0 state lock. Pause sequence and run `/calcifer` if instability appears.
- **STOP if:** any worker dies unexpectedly or watchdog log contains `action=restart` for the same worker > 2× in 30 min.

### R-8 — Deploy-block bypass via accidental schema migration
- **Severity:** P0
- **Owner:** B2
- **Description:** B2 might be tempted to add `engine_telemetry` triggers / VIEWs / additional columns. Any DB schema change requires explicit migration and rollback.
- **Containment:** Forbidden actions list explicitly forbids DB schema migration unless additive. B2 must justify any DDL with rollback.sql; no implicit ALTER TABLE.
- **STOP if:** B2 produces an `ALTER TABLE` against `champion_pipeline_*` or related governance tables.

### R-9 — Validation-gate retest fails after telemetry change
- **Severity:** P1
- **Owner:** B1, F
- **Description:** After B1 deploys, the existing test suite (`tests/test_arena_batch_metrics_accounting.py`, `tests/test_arena_pass_rate_telemetry.py`, `tests/test_a2_a3_arena_batch_metrics.py`) must still pass.
- **Containment:** B1 must run the existing test suite green before commit. F (deployable flow recheck) re-validates conservation and pass/fail unchanged.
- **STOP if:** any pre-existing test fails.

### R-10 — j13 decision checkpoint skipped
- **Severity:** P0 (governance)
- **Owner:** master order
- **Description:** Master order mandates a hard stop after D for j13 path selection. Implementation phase E must NOT proceed without explicit choice (P1 / P2 / P3 / P4 / multi / closure).
- **Containment:** Code path: at end of D, return decision options to j13 and wait. No autonomous selection of E sub-path.
- **STOP if:** any E sub-order is started without explicit j13 choice in conversation.

## Closed / contained

| ID | Description | Resolution |
|---|---|---|
| R-prior-A | A1 telemetry COUNTER_INCONSISTENCY ~50% | PR #50 + verified PR #51 (residual=0 across 96 batches) |
| R-prior-B | A1 telemetry UNKNOWN_REJECT bucket | PR #49 (taxonomy fix) + verified PR #51 |
| R-prior-C | Stale workers serving pre-fix code | PR #51 §17.6 FRESH 4/4 |

## Severity color summary

- **P0 active:** R-2, R-5, R-6, R-8, R-10 (5 risks)
- **P1 active:** R-1, R-3, R-4, R-7, R-9 (5 risks)
- **P2 active:** none
