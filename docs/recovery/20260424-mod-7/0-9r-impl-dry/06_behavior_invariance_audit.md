# 06 — Behavior Invariance Audit

## 1. Forbidden changes (per TEAM ORDER 0-9P/R-STACK-v2 §2 / §6)

| Item | Status |
| --- | --- |
| Alpha generation behavior | ✅ unchanged (consumer is leaf module; never imported by arena_pipeline / alpha_engine) |
| Formula generation behavior | ✅ unchanged |
| Mutation / crossover behavior | ✅ unchanged |
| Search policy | ✅ unchanged |
| Real generation budget | ✅ unchanged (no apply path) |
| Sampling weights | ✅ unchanged (no `sampling_weight = ...` assignment) |
| Thresholds (incl. `A2_MIN_TRADES`, ATR/TRAIL/FIXED grids, A3 segments) | ✅ unchanged (locked by source-text test) |
| Arena pass/fail (`arena_gates.arena2_pass` / `arena3_pass` / `arena4_pass`) | ✅ unchanged |
| Rejection semantics | ✅ unchanged |
| Champion promotion (`arena45_orchestrator.maybe_promote_to_deployable`) | ✅ unchanged |
| `deployable_count` semantics (champion_pipeline.status='DEPLOYABLE' VIEW) | ✅ unchanged (consumer source contains no `'DEPLOYABLE'` literal) |
| Execution / capital / risk | ✅ unchanged (no `live/` references) |
| CANARY activation | ✅ not started |
| Production rollout | ✅ not started |
| Per-alpha lineage | ✅ not introduced |
| Formula explainability | ✅ not required |
| Apply path / runtime apply | ✅ no `apply_*` symbol |
| Runtime-switchable mode flag | ✅ `mode` is hard-coded `DRY_RUN` |
| `applied=false` invariant | ✅ enforced at __post_init__ + to_event() |

## 2. Files modified (this PR)

Runtime SHA tracker coverage:

| File | Status |
| --- | --- |
| `zangetsu/services/arena_pipeline.py` | NOT modified |
| `zangetsu/services/arena23_orchestrator.py` | NOT modified |
| `zangetsu/services/arena45_orchestrator.py` | NOT modified |
| `zangetsu/services/arena_gates.py` | NOT modified |
| `zangetsu/services/feedback_budget_allocator.py` | NOT modified |
| `zangetsu/services/feedback_decision_record.py` | NOT modified |
| `zangetsu/services/generation_profile_metrics.py` | NOT modified |
| `zangetsu/services/generation_profile_identity.py` | NOT modified |
| `zangetsu/services/arena_pass_rate_telemetry.py` | NOT modified |
| `zangetsu/services/arena_rejection_taxonomy.py` | NOT modified |
| `zangetsu/config/settings.py` | NOT modified |
| `zangetsu/engine/components/*.py` | NOT modified |
| `zangetsu/live/*.py` | NOT modified |

New (non-CODE_FROZEN):

- `zangetsu/services/feedback_budget_consumer.py` — new module (services dir but new file, not a CODE_FROZEN SHA tracker target).
- `zangetsu/tests/test_feedback_budget_consumer.py` — new test file.
- `docs/recovery/20260424-mod-7/0-9r-impl-dry/01..09*.md` — 9 evidence docs.

Modified (non-CODE_FROZEN, allow-list extension only):

- `zangetsu/tests/test_feedback_budget_allocator.py` — added
  `feedback_budget_consumer.py` to the allow-list of legitimate
  downstream modules in
  `test_allocator_output_not_consumed_by_generation_runtime`.
- `zangetsu/tests/test_profile_attribution_audit.py` — refined
  `test_audit_does_not_modify_runtime_files` to check imports
  rather than raw substring (so commentary references are allowed).

Both test edits are pure test maintenance to admit the legitimate
new downstream; they don't relax governance.

## 3. SHA tracker expectations

All 6 CODE_FROZEN runtime SHAs zero-diff:

- `config.zangetsu_settings_sha`
- `config.arena_pipeline_sha`
- `config.arena23_orchestrator_sha`
- `config.arena45_orchestrator_sha`
- `config.calcifer_supervisor_sha`
- `config.zangetsu_outcome_sha`

No `--authorize-trace-only` flag needed.

## 4. Tests covering invariance

- `test_no_threshold_constants_changed`
- `test_a2_min_trades_still_pinned`
- `test_arena_pass_fail_unchanged`
- `test_champion_promotion_unchanged`
- `test_deployable_count_semantics_unchanged`
- `test_consumer_does_not_redefine_arena_thresholds`
- `test_consumer_has_no_apply_method`
- `test_no_generation_budget_file_changed`
- `test_no_sampling_weight_file_changed`
- `test_no_runtime_import_by_generation`
- `test_no_runtime_import_by_arena`
- `test_no_runtime_import_by_execution`
- `test_consumer_output_not_consumed_by_runtime`
- `test_consumer_not_imported_by_existing_consumer_substitutes`
- `test_plan_invariants_resilient_to_caller_kwargs`
- `test_plan_invariants_resilient_to_post_construction_mutation`

All PASS locally.

## 5. Conclusion

Zero runtime SHA changes. All forbidden items unchanged. Consumer
is a leaf-only module; cannot affect Arena decisions, generation
behavior, or any production state. Dry-run invariant enforced at
three independent layers.
