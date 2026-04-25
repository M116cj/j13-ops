# 07 — Controlled-Diff Report (Expected)

## 1. Expected classification

```
Classification: EXPLAINED  (NOT EXPLAINED_TRACE_ONLY — no runtime SHA changed)

Zero diff:                   ~43 fields  (incl. all 6 CODE_FROZEN runtime SHAs)
Explained diff:              1 field   — repo.git_status_porcelain_lines
Explained TRACE_ONLY diff:   0 fields
Forbidden diff:              0 fields
```

## 2. Files added (non-CODE_FROZEN)

- `zangetsu/tools/__init__.py` (new package)
- `zangetsu/tools/profile_attribution_audit.py` (new offline tool)
- `zangetsu/tests/test_profile_attribution_audit.py` (new test file)
- `docs/recovery/20260424-mod-7/0-9p-audit/01..08*.md` (8 evidence docs)

## 3. Files NOT modified

- `zangetsu/services/arena_pipeline.py`
- `zangetsu/services/arena23_orchestrator.py`
- `zangetsu/services/arena45_orchestrator.py`
- `zangetsu/services/arena_gates.py`
- `zangetsu/services/arena_pass_rate_telemetry.py`
- `zangetsu/services/arena_rejection_taxonomy.py`
- `zangetsu/services/feedback_budget_allocator.py`
- `zangetsu/services/feedback_decision_record.py`
- `zangetsu/services/generation_profile_metrics.py`
- `zangetsu/services/generation_profile_identity.py`
- `zangetsu/config/`
- `zangetsu/engine/`
- `zangetsu/live/`

All 6 CODE_FROZEN runtime SHAs are zero-diff:

- `config.zangetsu_settings_sha`
- `config.arena_pipeline_sha`
- `config.arena23_orchestrator_sha`
- `config.arena45_orchestrator_sha`
- `config.calcifer_supervisor_sha`
- `config.zangetsu_outcome_sha`

No `--authorize-trace-only` flag needed.

## 4. Hard-forbidden 守恆

- `runtime.arena_processes.count` 仍 0
- `runtime.engine_jsonl_mtime_iso` 仍 static
- `runtime.engine_jsonl_size_bytes` 仍 static

## 5. Branch protection

`enforce_admins=true` / `required_signatures=true` / `linear_history=true`
/ `allow_force_pushes=false` / `allow_deletions=false` 全部維持。

## 6. Diff exit code 預期

```
exit code 0  ⇐ ZERO / EXPLAINED
```
