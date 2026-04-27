# 03 — Internal Reference Integrity

## A. DB References (status updated to reflect Phase 4 BLOCKED)

| Reference | Source files | Target exists in live DB? | Class |
| --- | --- | --- | --- |
| `champion_pipeline` | dashboard/services/scripts (~30 references) | YES (legacy table) | REF_OK |
| `champion_pipeline_fresh` | arena_pipeline, dashboard, services | **NO** | **REF_MISSING_TARGET** |
| `champion_pipeline_staging` | arena_pipeline, alpha_zoo_injection | **NO** | **REF_MISSING_TARGET** |
| `champion_pipeline_rejected` | (audit code) | **NO** | **REF_MISSING_TARGET** |
| `champion_legacy_archive` | calcifer + audit | **NO** | **REF_MISSING_TARGET** |
| `champion_pipeline_v9` | dashboard | **NO** | **REF_MISSING_TARGET** |
| `engine_telemetry` | arena_pipeline:329 | **NO** | **REF_MISSING_TARGET** (silent insert failure) |
| `admission_validator()` | arena_pipeline:1180 | **NO** | **REF_MISSING_TARGET** |
| `fresh_insert_guard` (trigger) | (audit only) | **NO** | **REF_MISSING_TARGET** |
| `archive_readonly_*` (triggers) | (audit only) | **NO** | **REF_MISSING_TARGET** |
| `zangetsu.admission_active` | (set inside admission_validator) | n/a (function missing) | **REF_MISSING_TARGET** |

**11 of 11 v0.7.1 governance objects are missing.** All currently masked because A1 candidates fail at upstream COUNTER_INCONSISTENCY/COST_NEGATIVE before reaching these code paths.

## B. File / Path References

| Reference | Status |
| --- | --- |
| `/home/j13/j13-ops/zangetsu/.venv/bin/python3` | OK (exists, executable) |
| `~/strategic-research/alpha_zoo/` | OK (exists) |
| `~/strategic-research/worldquant_101/` | OK (exists) |
| `/home/j13/j13-ops/zangetsu/migrations/postgres/v0.7.1_governance.sql` | OK (file exists) |
| `/home/j13/j13-ops/zangetsu/config/a13_guidance.json` | OK (read by arena_pipeline) |
| Mac mirror `/Users/a13/dev/j13-ops/` | OK (synced to a74406d as of pre-PR #43) |
| `/tmp/zangetsu_a1_w*.log` | OK (active write) |
| `/tmp/zangetsu_arena13_feedback.log` | OK |
| `/tmp/zangetsu_a23.log`, `/tmp/zangetsu_a45.log` | OK (idle but tailable) |

## C. Module / Import References

| Module | Status |
| --- | --- |
| `from zangetsu.config.cost_model import CostModel` | OK |
| `from zangetsu.engine.components.alpha_signal import generate_alpha_signals` | OK |
| `from zangetsu.engine.components.backtester import Backtester` | OK |
| `from j01.fitness import ...` | OK (sys.path-injected) |
| `from j01.config.thresholds import ...` | OK |
| `from zangetsu.services.arena_rejection_taxonomy import classify` | OK |
| `from zangetsu.engine.provenance import ...` | OK |

## D. Telemetry References

| Telemetry | Status |
| --- | --- |
| `engine.jsonl` writer | active |
| `arena_batch_metrics` event format | parseable |
| `arena_batch_metrics.jsonl` standalone file | not present at canonical path; events go to `engine.jsonl` and `/tmp/zangetsu_a1_*.log` |
| `sparse_candidate_dry_run_plans.jsonl` | not present (pre-cold-start) |
| `generation_profile_id` field | populated |
| `generation_profile_fingerprint` field | populated (sha256) |
| `deployable_count` field | nullable; emitted as null when source is empty |

## Reference Integrity Summary

| Class | Count |
| --- | --- |
| REF_OK | majority of paths/imports/files |
| REF_MISSING_TARGET | 11 (all DB schema gaps; concentrated in v0.7.1 governance) |
| REF_DEPRECATED_ACTIVE | 0 (deprecated guards prevent active execution) |
| REF_MAC_ONLY | 0 |
| REF_DB_SCHEMA_DRIFT | 11 (same as REF_MISSING_TARGET) |
| REF_TELEMETRY_DRIFT | 1 (run_id field empty in batch metrics — minor) |

→ **All 11 broken DB references converge on a single root cause: the v0.7.1 governance migration has not been applied** (and prerequisites v0.4, v0.6, v0.7.0 are also missing — see Phase 4). Until those are applied, the entire v0.7.1 governance code path is dead-code.
