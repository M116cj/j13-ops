# 0-9O-A — Behavior Invariance Audit

## 1. Scope

All runtime changes are identity / telemetry / read-only scoring only.
This audit enumerates forbidden areas and confirms none were modified.

## 2. Audit table

| Forbidden area | Touched? | Evidence |
|----------------|----------|----------|
| Alpha generation behavior | No | No files under formula / mutation / crossover / search policy touched. GP parameters `N_GEN`, `POP_SIZE`, `TOP_K`, `ENTRY_THR`, `EXIT_THR`, `MIN_HOLD`, `COOLDOWN` are still read from env; only a read-only identity dict is derived from them. |
| Formula generation | No | No change to alpha_signal, alpha_engine, indicator_bridge, or DEAP components. |
| Mutation / crossover | No | Not touched. |
| Search policy | No | Not touched. |
| Generation budget allocation | No | No allocator exists yet in runtime; this PR does not introduce one either. |
| Generation sampling weights | No | Not touched. |
| Threshold constants | No | `test_no_threshold_constants_changed_under_0_9o_a` pins `A2_MIN_TRADES=25`, `A3_SEGMENTS=5`, `A3_MIN_TRADES_PER_SEGMENT=15`, `A3_MIN_WR_PASSES=4`, `A3_MIN_PNL_PASSES=4`, `A3_WR_FLOOR=0.45`. PASS. |
| Arena pass/fail branch conditions | No | `test_arena_pass_fail_behavior_unchanged_a2_min_trades` confirms the 20-vs-25 gate boundary. PASS. |
| Rejection semantics | No | Reuses `arena_rejection_taxonomy.classify()`; no remapping. |
| Champion promotion | No | `test_champion_promotion_unchanged` PASS. |
| `deployable_count` semantics | No | `test_deployable_count_semantics_unchanged` — aggregator never infers from `passed_count`. PASS. |
| Execution / capital / risk | No | No execution / capital / risk modules touched. |
| Service restart | No | No deploy / restart action taken. |
| CANARY | No | Not started. |
| Production rollout | No | Not started. |
| Branch protection | No | Branch protection settings unchanged. |

## 3. Exception safety

All new runtime code paths end in `try / except` guards:

- `safe_resolve_profile_identity(...)` — wrapper around
  `resolve_profile_identity`.
- `aggregate_batches_for_profile(...)` — catches internal errors and
  returns a zero-filled record with `LOW_CONFIDENCE` marker.
- `safe_build_generation_profile_metrics(...)` — returns `None` on
  failure.
- `safe_build_feedback_decision_record(...)` — returns `None` on failure.
- `serialize_feedback_decision_record(...)` — returns empty string on
  failure.
- `_emit_a1_batch_metrics_from_stats_safe(...)` — outer `try / except
  Exception: pass` wrapper retained from P7-PR4-LITE; new kwargs do not
  change the exception contract.
- `arena_pipeline` module import guard has an inline fallback that
  returns the UNKNOWN / UNAVAILABLE identity dict if
  `generation_profile_identity` is missing — telemetry cannot be
  blocked by an import error.

`test_runtime_behavior_invariant_when_profile_identity_fails`
simulates a poisoned config and confirms the helpers still return safe
fallbacks. PASS.

## 4. Runtime insertion points (read-only)

`zangetsu/services/arena_pipeline.py`:

- Module import block (~L112–135): import + fallback stub for
  `_safe_resolve_profile_identity`.
- `_emit_a1_batch_metrics_from_stats_safe` signature (~L145–155):
  two new optional kwargs `generation_profile_id`,
  `generation_profile_fingerprint`; defaults preserve P7-PR4-LITE
  behavior when the new kwargs are omitted.
- `_emit_a1_batch_metrics_from_stats_safe` body (~L170–180): uses new
  kwargs with `or` fallback to UNKNOWN / UNAVAILABLE.
- Worker-loop GP-params block (~L727–745): computes
  `_gen_profile_identity = _safe_resolve_profile_identity({...}, ...)`.
  Read-only dict; no downstream mutation.
- A1 emission call site (~L1156–1167): passes
  `generation_profile_id` / `generation_profile_fingerprint` from the
  identity dict into the helper.

No other runtime file is modified.

## 5. Independent verification

- Full test suite: **253 passed, 3 skipped** (excluding pre-existing
  async failures + module-level `sys.exit`).
- Baseline before 0-9O-A: 211 passed.
- New tests: 42.
- Dedicated 0-9O-A suite: 42/42 PASS.
- Controlled-diff: **EXPLAINED_TRACE_ONLY**, 0 forbidden.
