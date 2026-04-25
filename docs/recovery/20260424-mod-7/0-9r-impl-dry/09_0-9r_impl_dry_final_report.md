# 0-9R-IMPL-DRY — Sparse-Candidate Black-Box Optimization Dry-Run Consumer Final Report

## 1. Status

**COMPLETE — pending Gate-A / Gate-B / signed merge on Alaya side.**

Local execution complete (branch ready, all consumer tests pass, all
adjacent suites zero-regression). Alaya-side gates run in CI / on PR
open.

PR-C is the **third PR in the 0-9P/R-STACK-v2 stack** — it builds on
PR-A (0-9P passport persistence, merged at `a8a8ba9`) and PR-B
(0-9P-AUDIT attribution audit tool, merged at `3219b805`). PR-C
introduces the dry-run consumer that closes the read side of the
attribution chain: `passport.arena1.generation_profile_id` →
attribution audit verdict → consumer gate decision → dry-run plan.

## 2. Baseline

- origin/main SHA at start: `3219b805f8c1739ef06be32080dd1b09826bc81d`
- prior stack SHAs: `a8a8ba9` (0-9P), `3219b805` (0-9P-AUDIT)
- branch: `phase-7/0-9r-impl-dry-sparse-candidate-consumer`
- PR URL: filled in after `gh pr create`
- merge SHA: filled in after merge
- signature verification: ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`

## 3. Mission

Consume `DryRunBudgetAllocation` (delivered by 0-9O-B) plus the
attribution-audit verdict (delivered by 0-9P-AUDIT) and produce a
**fully-audited dry-run plan** for sparse-candidate generation profile
intervention. The consumer applies an EMA smoother + step-limit + floor
+ diversity guard pipeline, gates actionability behind the consumer's
own stricter thresholds, and emits a `SparseCandidateDryRunPlan` event
that **never reaches runtime**.

Strict scope:

- Dry-run only (`mode = "DRY_RUN"`, `applied = False`).
- No `apply` / `commit` / `execute` symbol on the public surface.
- Allowed interventions: `PB-FLOOR`, `PB-DIV`, `PB-SHIFT` only.
- No runtime module imports the consumer.
- No `SparseCandidateDryRunPlan` symbol referenced anywhere in
  runtime code.

## 4. What changed

| File | Type | Notes |
| --- | --- | --- |
| `zangetsu/services/feedback_budget_consumer.py` | **new module** (~700 LOC) | Consumer + `SparseCandidateDryRunPlan` dataclass + smoothing helpers + verdict gate |
| `zangetsu/tests/test_feedback_budget_consumer.py` | new test file | 81 tests covering pipeline, gate chain, dry-run invariant, runtime isolation, behavior invariance |
| `zangetsu/tests/test_feedback_budget_allocator.py` | **allow-list extension only** | Added `feedback_budget_consumer.py` as legitimate downstream of `allocate_dry_run_budget` symbol |
| `zangetsu/tests/test_profile_attribution_audit.py` | **allow-list extension only** | Added `feedback_budget_consumer.py` as legitimate downstream of `verdict_blocks_consumer_phase` symbol |
| `docs/recovery/20260424-mod-7/0-9r-impl-dry/01..09*.md` | evidence docs | 9 markdown artifacts |

**Zero runtime files modified.** No `arena_pipeline.py`,
`arena23_orchestrator.py`, `arena45_orchestrator.py`, `arena_gates.py`,
`feedback_budget_allocator.py`, `feedback_decision_record.py`,
`generation_profile_identity.py`, `zangetsu/config/`,
`zangetsu/engine/`, `zangetsu/live/`, or `zangetsu/tools/` change.
The two existing test files were modified **only** to extend their
runtime-isolation allow-list — no test logic change, no new permitted
runtime path.

## 5. Consumer design

### 5.1 Inputs

- `allocation`: `DryRunBudgetAllocation` (or dict-equivalent) produced
  by 0-9O-B `allocate_dry_run_budget(...)`. Required to be in
  `mode="DRY_RUN"` with `applied=False` — otherwise the consumer
  refuses with a structured rejection.
- `run_id`: caller-supplied execution identifier for audit chaining.
- `attribution_verdict`: `VERDICT_GREEN` / `VERDICT_YELLOW` /
  `VERDICT_RED` (from 0-9P-AUDIT). `VERDICT_RED` short-circuits the
  consumer to `BLOCK_VERDICT_RED`.
- Optional: `previous_dry_run_weights` (for EMA history),
  `previous_plan_weights` (for step-limit reference),
  `ema_alpha` (clamped ≤ `EMA_ALPHA_MAX = 0.20`),
  `max_step_abs` (default `0.10`),
  `floor` (default `0.05`),
  `diversity_cap_min` (default `2`).

### 5.2 Outputs

`SparseCandidateDryRunPlan` dataclass (28 required fields per
`required_plan_fields()`):

```
{
  telemetry_version: "1",
  plan_id: "plan-<hex>",
  run_id, created_at,
  mode: "DRY_RUN",  applied: false,  consumer_version: "0-9R-IMPL-DRY",
  source_decision_id, source_allocator_version,
  attribution_verdict, attribution_verdict_reasons,
  plan_status: PLAN_STATUS_ACTIONABLE_DRY_RUN | NON_ACTIONABLE | BLOCKED,
  block_reason, block_details,
  confidence,
  input_profile_count, actionable_profile_count, non_actionable_profile_count,
  unknown_reject_rate,
  allocator_proposed_weights,
  smoothed_proposed_weights,
  max_step_limited_weights,
  final_dry_run_weights,
  ema_alpha_used, max_step_abs_used, floor_used, diversity_cap_min_used,
  interventions_applied: [PB-FLOOR | PB-DIV | PB-SHIFT],
  expected_effect: "DRY_RUN_…_NOT_APPLIED",
  safety_constraints: [NOT_APPLIED_TO_RUNTIME, ALLOWED_INTERVENTIONS_ONLY,
                       EMA_ALPHA_LE_0_20, MAX_STEP_ABS_LE_0_10,
                       FLOOR_GE_0_05, DIVERSITY_CAP_MIN_GE_2,
                       UNKNOWN_REJECT_VETO_LT_0_05],
  reason, source, event_type
}
```

Detailed schema lock + field-by-field contract: `02_consumer_input_output_schema.md`.

### 5.3 Gating chain

A plan reaches `PLAN_STATUS_ACTIONABLE_DRY_RUN` only when **all** of:

1. `allocation.mode == "DRY_RUN"` AND `allocation.applied is False`.
2. `allocation.confidence == "CONFIDENCE_A1_A2_A3_METRICS_AVAILABLE"`.
3. `allocation.actionable_profile_count >= 2`.
4. No profile flagged with `COUNTER_INCONSISTENCY` in the allocator's
   per-profile reasons.
5. Aggregate `unknown_reject_rate < UNKNOWN_REJECT_VETO (= 0.05)` —
   **stricter than the allocator's 0.20 ceiling**, by design.
6. `attribution_verdict != VERDICT_RED`.
7. (Caller-supplied) every actionable profile reports
   `sample_size_rounds >= 20`.

Failure of any gate routes to either `PLAN_STATUS_NON_ACTIONABLE`
(structural input deficiency, no recommendation produced) or
`PLAN_STATUS_BLOCKED` with one of:

- `BLOCK_ALLOCATION_NOT_DRY_RUN`
- `BLOCK_ALLOCATION_ALREADY_APPLIED`
- `BLOCK_VERDICT_RED`
- `BLOCK_UNKNOWN_REJECT_VETO`
- `BLOCK_SAMPLE_SIZE_INSUFFICIENT`
- `BLOCK_COUNTER_INCONSISTENCY`

Detailed gate doc: `03_consumer_gate_chain.md`.

### 5.4 Smoothing pipeline

The consumer transforms allocator-proposed weights into a final
dry-run plan via four ordered, audit-stored stages:

```
allocator_proposed_weights
    │
    ▼  ema_smooth(new, history, alpha=ema_alpha_used)        [α ≤ 0.20]
smoothed_proposed_weights
    │
    ▼  limit_step(proposed, previous, max_step_abs=0.10)     [≤ 10pp/profile]
max_step_limited_weights
    │
    ▼  enforce_floor_and_diversity(weights, floor=0.05,
                                   diversity_cap_min=2)
final_dry_run_weights        (sum == 1.0, all ≥ floor, ≥2 above floor)
```

Each intermediate stage is preserved on the plan for downstream replay
+ audit. The smoothing knobs are clamped on entry: `ema_alpha`
clamped to `[0, EMA_ALPHA_MAX]`, `max_step_abs` clamped to
`[0, DEFAULT_MAX_STEP_ABS]`, `floor` clamped to `[EXPLORATION_FLOOR,
1.0]`, `diversity_cap_min` clamped to `[DEFAULT_DIVERSITY_CAP_MIN, n]`.

Detailed contract: `04_smoothing_pipeline.md`.

### 5.5 `safe_consume` exception-safe wrapper

`safe_consume(allocation, *, run_id, ...)` wraps `consume(...)` in a
try/except that catches **any** exception raised by either the
allocator-side input parse or the consumer's own pipeline, and emits a
`PLAN_STATUS_BLOCKED` plan with `block_reason="BLOCK_INTERNAL_ERROR"`
and `block_details` containing the exception class + message. This is
the surface the (future) caller is expected to invoke — it guarantees
**no exception ever surfaces to a runtime caller**, which is a
prerequisite for any future deployment integration.

## 6. Allowed intervention scope

Exactly three intervention labels may appear in
`interventions_applied`:

| Label | Meaning |
| --- | --- |
| `PB-FLOOR` | Exploration-floor enforcement (≥ 0.05 per actionable profile) |
| `PB-DIV` | Diversity preservation (≥ 2 actionable profiles above floor) |
| `PB-SHIFT` | Dry-run weight shift (the smoothed + step-limited proposal itself) |

Anything else is **forbidden** at this stack level and is not
implemented. Specifically, the following are **not** present anywhere
in the consumer module (verified by source-text grep tests):

- `PB-SUPPRESS` (profile suppression / zero-out)
- `PB-QUARANTINE` (profile quarantine state)
- `PB-RESURRECT` (profile resurrection from prior suppression)
- `PB-MUT` (mutation policy intervention)
- `PB-DENSITY` (generation density intervention)
- `PRE-A2-SCREEN` (pre-Arena screening intervention)

Detailed scope contract: `05_allowed_intervention_scope.md`.

## 7. Dry-run invariant (multi-layer)

| Layer | Mechanism |
| --- | --- |
| 1. Construction | `SparseCandidateDryRunPlan.__post_init__` resets `mode=DRY_RUN`, `applied=False`, `consumer_version="0-9R-IMPL-DRY"` regardless of caller-supplied kwargs |
| 2. Serialization | `SparseCandidateDryRunPlan.to_event()` re-asserts the same three fields before returning the payload |
| 3. Public API | No `apply` / `commit` / `execute` / `deploy` symbol exists on `SparseCandidateDryRunPlan` or any consumer helper. `test_consumer_has_no_apply_method` walks public `dir()` to enforce this |
| 4. Runtime isolation | No runtime module imports the consumer (verified by 7 source-text tests) |
| 5. Output isolation | No runtime module references `SparseCandidateDryRunPlan`, `consume`, `safe_consume`, or any consumer constant (verified by reverse source-text test) |
| 6. Exception isolation | `safe_consume` guarantees no exception escapes to caller; emits `BLOCK_INTERNAL_ERROR` plan instead |

The `__post_init__` reset is **defensive overwrite**, not validation —
even if a caller (or future bug) constructs a plan with
`mode="LIVE"` / `applied=True` / `consumer_version="…"`, the
constructor unconditionally rewrites them. `to_event()` rewrites them
again on serialization. This double-write is the same pattern used by
0-9O-B `DryRunBudgetAllocation` and 0-9O-A
`build_feedback_decision_record`, giving the stack three independently
enforcing layers from allocator → consumer → record.

## 8. Runtime isolation

| Runtime surface | Imports consumer? | Verified by |
| --- | --- | --- |
| `arena_pipeline.py` (A1) | NO | source-text test |
| `arena23_orchestrator.py` (A2/A3) | NO | source-text test |
| `arena45_orchestrator.py` (A4/A5) | NO | source-text test |
| `arena_gates.py` | NO | source-text test |
| `alpha_signal_live.py` | NO | source-text test |
| `data_collector.py`, `alpha_dedup.py`, `alpha_ensemble.py`, `alpha_discovery.py` | NO | source-text test |
| `feedback_budget_allocator.py` (0-9O-B) | NO | source-text test (consumer is downstream of allocator, never the reverse) |
| `feedback_decision_record.py` (0-9O-A) | NO | source-text test |
| Consumer → `alpha_engine` / `sampling_weight` references | NO | reverse source-text test |
| Consumer → any `apply` / `commit` / `execute` / `deploy` keyword | NO | reverse source-text test |

`test_consumer_output_not_consumed_by_generation_runtime` walks
`zangetsu/services/*.py` (excluding the consumer itself) and asserts
no file references `SparseCandidateDryRunPlan`, `consume`,
`safe_consume`, `CONSUMER_VERSION`, or any `BLOCK_*` / `PLAN_STATUS_*`
constant. The two test-suite files in §4 added the consumer module
to their **own** allow-list to prevent that test from flagging the
new module as a "rogue runtime importer of the allocator / audit
output" — these are pure-test source files, not runtime, and the
extension is documented inline.

Detailed audit: `06_runtime_isolation_audit.md`.

## 9. Behavior invariance

| Item | Status |
| --- | --- |
| No alpha generation change | yes |
| No formula generation change | yes |
| No mutation / crossover change | yes |
| No search policy change | yes |
| No real generation budget change | yes |
| No sampling weight change | yes |
| No threshold change (incl. `A2_MIN_TRADES`, ATR/TRAIL/FIXED grids, A3 segments) | yes — verified by `test_a2_min_trades_still_pinned`, `test_a3_thresholds_still_pinned` |
| No Arena pass/fail change | yes — verified by `test_arena_pass_fail_behavior_unchanged` |
| No champion promotion change | yes — verified by `test_champion_promotion_unchanged` |
| No `deployable_count` semantic change | yes — consumer source contains no `'DEPLOYABLE'` literal |
| No execution / capital / risk change | yes |
| No allocator output mutation | yes — `test_consumer_does_not_mutate_allocation_input` (deep-copy snapshot before/after) |
| No formula lineage introduced | yes |
| No parent-child ancestry introduced | yes |
| Consumer never raises to caller | yes — `safe_consume` exception isolation |
| CANARY started | NO |
| Production rollout started | NO |

Forbidden-changes audit: `07_behavior_invariance_audit.md`.

## 10. Test results

```
$ python3 -m pytest zangetsu/tests/test_feedback_budget_consumer.py
======================== 81 passed, 1 warning in 0.27s =========================
```

Adjacent suites: **293 PASS / 0 regression** (P7-PR4B 54 + 0-9O-B 62 +
0-9P 40 + 0-9P-AUDIT 56 + 0-9R-IMPL-DRY 81 = 293). 8 pre-existing
local-Mac failures in `arena_pipeline.py` chdir suite (path
`/home/j13/j13-ops` only resolves on Alaya); verified pre-existing on
main during P7-PR4B and 0-9O-B execution and unrelated to PR-C.

Test groupings (81 total):

- 12 — schema lock + `required_plan_fields()` invariants
- 14 — gate chain (each block reason fired by a constructed input)
- 11 — smoothing pipeline (EMA bounds, step-limit, floor, diversity)
- 9  — sum-to-1.0 numerical correctness across edge cases
- 7  — dry-run invariant (construction + serialization + dir() walk)
- 7  — runtime isolation (source-text tests across all surfaces)
- 6  — behavior invariance (A2_MIN_TRADES, A3, Arena pass/fail,
       champion promotion, `DEPLOYABLE` literal, allocator mutation)
- 6  — `safe_consume` exception isolation
- 5  — allowed intervention scope (forbidden labels not present)
- 4  — caller-supplied sample-size guard
- Detailed breakdown: `08_test_results.md`.

Expected on Alaya CI: all prior tests + 81 new = full PASS.

## 11. Controlled-diff

Expected classification: **EXPLAINED** (NOT EXPLAINED_TRACE_ONLY —
no runtime SHA changed, no `--authorize-trace-only` flag needed).

```
Zero diff:                    ~43 fields  (incl. all 6 CODE_FROZEN runtime SHAs)
Explained diff:               1 field    — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:    0 fields
Forbidden diff:               0 fields
```

The 6 CODE_FROZEN runtime SHAs (`config.arena_pipeline_sha`,
`config.arena23_orchestrator_sha`, `config.arena45_orchestrator_sha`,
`config.arena_gates_sha`, `config.alpha_signal_live_sha`,
`config.feedback_decision_record_sha`) all zero-diff. The two test-file
allow-list extensions in §4 do not affect any runtime SHA — test files
are not in the CODE_FROZEN set.

Detailed report: `09_controlled_diff_report.md` (placeholder until PR
opens; will be regenerated by the controlled-diff job in CI).

## 12. Gate-A / Gate-B / Branch protection

- **Gate-A**: expected **PASS** (snapshot-diff classified as
  EXPLAINED → exit code 0; no runtime SHA changed → no
  governance-relevant delta).
- **Gate-B**: expected **PASS** (PR open with required artifacts;
  pull-request trigger restored by 0-9I; signed commits via
  `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`).
- **Branch protection on `main`**: expected **INTACT** —
  `enforce_admins=true`, `required_signatures=true`,
  `linear_history=true`, `allow_force_pushes=false`,
  `allow_deletions=false`. PR-C does not modify governance
  configuration.

## 13. Forbidden changes audit

- CANARY: **NOT** started.
- Production rollout: **NOT** started.
- No new runtime importer of any allocator / consumer / audit symbol.
- No `apply` / `commit` / `execute` / `deploy` symbol introduced.
- No `A2_MIN_TRADES` / ATR / TRAIL / FIXED / A3-segment / Arena
  pass-fail / champion-promotion / `deployable_count` semantic edit.
- No new `DEPLOYABLE` literal anywhere in the consumer module.
- No formula lineage / parent-child ancestry telemetry.
- No production wiring of `SparseCandidateDryRunPlan` output.

The only runtime surface that could in principle "see" the consumer is
the future caller that invokes `safe_consume(...)` — and no such
caller exists yet in any runtime module. PR-C ships the consumer
**inert**: importable, fully tested, allocator-output-aware, but
never invoked at runtime.

## 14. Remaining risks

- **Sample-size sensitivity.** The caller-supplied `sample_size_rounds
  >= 20` guard is necessary but not sufficient. A profile with 20
  batches but heavy regime concentration (e.g. all bull-market) can
  still produce misleading smoothed weights. Future regime-aware
  thresholding remains an open design item — flagged for 0-9R-NEXT.
- **Attribution verdict regression.** The verdict input is treated as
  a per-call value, not a one-time permission. A profile attribution
  audit that was GREEN at allocator time but degrades to YELLOW or
  RED before consumer execution will be correctly caught — but only
  if the caller re-reads the verdict. Operator runbook (to be
  produced in 0-9S) must mandate fresh verdict reads.
- **Smoothing-knob bad-input clamping.** All four smoothing knobs are
  clamped on entry rather than rejected. A pathological caller passing
  `ema_alpha=1e9` will silently get `EMA_ALPHA_MAX=0.20`. This is
  intentional (no exception leakage in dry-run path) but means a
  badly-configured caller cannot detect mis-tuning by exception. The
  plan's `ema_alpha_used` / `max_step_abs_used` / `floor_used` /
  `diversity_cap_min_used` fields exist precisely so the operator
  can cross-check intended vs. effective values in the dry-run record.
- **In-flight allocations between merges.** If 0-9O-B-produced
  allocation events are persisted from before PR-C lands, the
  consumer can replay them — but allocations produced **before**
  0-9P passport persistence (pre-PR-A) will carry
  `UNKNOWN_PROFILE` / orchestrator-fallback attribution, raising
  `unknown_reject_rate` and triggering `BLOCK_UNKNOWN_REJECT_VETO`.
  This is the correct behavior; flagged so the operator knows the
  block is **expected** during the transition window, not a bug.
- **Consumer output is recommendation only.** The dry-run plan is not
  a deployment artifact. Any future production wiring must go through
  CANARY (0-9S) + controlled-diff + signed PR review. The presence of
  `safe_consume` does not authorize any caller to wire the plan into
  runtime — that authorization is gated by the next stack level.
- **Allow-list extension scope.** The two test-file modifications
  (§4) extend the allow-list of `feedback_budget_consumer.py` as a
  legitimate downstream of `allocate_dry_run_budget` and
  `verdict_blocks_consumer_phase`. This is the **only** sanctioned
  way for the consumer to reference allocator + audit symbols.
  Any future runtime caller that needs to invoke the consumer must
  go through a **separate** allow-list extension review — the
  current extension does not authorize runtime callers.

## 15. Recommended next action

**PR-D / 0-9S-READY — CANARY Readiness Gate.**

With PR-A (passport persistence), PR-B (attribution audit), PR-C
(dry-run consumer) merged, the read+plan side of the sparse-candidate
loop is complete and inert. 0-9S-READY's mission:

1. Define the CANARY readiness criteria (minimum
   `actionable_profile_count`, minimum verdict-GREEN window, minimum
   sample-size accumulation, allowed regime distribution).
2. Build the offline replay tool that ingests historical
   `DryRunBudgetAllocation` events + audit verdicts and validates the
   consumer would have produced sensible plans across the last N days.
3. Specify the production wiring requirements (signed caller,
   read-only allocator/audit input contract, write-only telemetry
   sink, CANARY rollback path).
4. **No production wiring**, **no Arena weakening**, **no
   `A2_MIN_TRADES` change**, **no `deployable_count` semantic edit**.

Only after 0-9S-READY passes its own Gate-A / Gate-B / signed merge
should the project even consider designing the runtime caller that
turns `safe_consume(...)` output into actual `proposed_profile_weights`
deployment. The current stack (PR-A + PR-B + PR-C) deliberately stops
**one level short** of any production change — and that is the entire
point of the dry-run discipline.

— end of report —
