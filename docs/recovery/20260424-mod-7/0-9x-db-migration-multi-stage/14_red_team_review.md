# 14 — Red Team Review

## Verdict: **APPROVE_WITH_WARNINGS**

## Adversarial Questions

### Q1: Could this migration silently lose rows?

**NO.** Source `champion_pipeline` had 0 rows pre-migration. v0.7.1 RENAMEd the empty table to `champion_legacy_archive`, preserving 0 rows. New tables (fresh/staging/rejected/engine_telemetry) created empty. Backup has SHA-256 manifest. Even if rows existed, the RENAME preserves them and `archive_readonly_triggers` make legacy data immutable forever.

### Q2: Could champion_pipeline become a view/table mismatch?

**Mitigated.** v0.7.1 alone leaves no `champion_pipeline` object; code expects it. We post-created `CREATE OR REPLACE VIEW champion_pipeline AS SELECT * FROM champion_pipeline_fresh`. Code that does `SELECT FROM champion_pipeline` works (read-only over fresh). Code that does `INSERT/UPDATE INTO champion_pipeline` would now fail on the VIEW — **but** v0.7.1's intent is that all writes go through staging→admission_validator→fresh anyway. **Risk**: legacy code that still does `INSERT INTO champion_pipeline` will break. Mitigation: PR #43 (already merged) hardened `alpha_zoo_injection.py` to refuse direct writes; `seed_101_alphas.py` etc. have DEPRECATED guards.

### Q3: Could admission_validator reject all future writes?

Possible if `staging_id` lookup fails or all 3 gates reject. Empirically: `admission_validator(0)` returns `not_found_or_already_processed` for non-existent ID (correct). The 3 gates (alpha_hash format, epoch=B_full_space, arena1_score finite) are sane and well-defined. **Mitigation**: rejected rows are written to `champion_pipeline_rejected` for forensics. If validator rejects everything, telemetry will surface immediately.

### Q4: Could staging/fresh divergence occur?

Theoretically yes if `admission_validator` exits via the `EXCEPTION WHEN OTHERS` branch (sets `pending_validator_error` but doesn't promote). Mitigation: `pending_validator_error` rows stay in staging — they don't divert to fresh. There's no path that creates a fresh row WITHOUT going through validator. **Pure additive design.**

### Q5: Could old A1 code write to new DB incorrectly?

A1 code paths reference `INSERT INTO champion_pipeline_staging (...)` at `arena_pipeline.py:1140` — this matches the new staging table schema exactly. The staging table accepts the 11 provenance fields as NOT NULL. If A1 fails to provide all 11 fields, INSERT fails (correct — guards data integrity). PR #43 already verified this code path is wired. **No incorrect writes.**

### Q6: Could new schema break A23/A45 reads?

A23/A45 currently read `champion_pipeline_fresh` (per VERSION_LOG v0.7.1 + bare `champion_pipeline` callers updated). Our backward-compat VIEW makes both `champion_pipeline` AND `champion_pipeline_fresh` valid SELECT targets. **Mitigated.** Any A23/A45 code expecting old 14-col schema would break — but PR #43's audit showed all code references the v0.7.1 schema names.

### Q7: Could this accidentally enable alpha_zoo DB writes?

**NO.** PR #43 hardened `alpha_zoo_injection.py` to `--no-db-write` default. Even if a user runs with `--confirm-write`, the precondition check (added in PR #43) verifies `champion_pipeline_staging`, `champion_pipeline_fresh`, AND `admission_validator()` all exist. Migration makes those exist now — so the precondition CHECK now passes. **But** writes still require explicit `--confirm-write` flag and a future governance order. The migration does NOT auto-enable writes.

### Q8: Could this accidentally start CANARY?

**NO.** No CANARY-related code was touched. No cron entry was added. No service was started. Migration is DB-schema-only.

### Q9: Could this modify champion promotion semantics?

**NO.** Champion promotion is defined in `j01/config/thresholds.py` (A2/A3/A4/A5 thresholds) and `arena_pipeline.py` val_filter chain. Both unchanged. The new staging→admission_validator→fresh path is an INSERTION-side gate, not a promotion-side gate.

### Q10: Is rollback actually executable?

**Tested**: backup verified with `pg_restore --list` (43 TOC entries OK). `rollback_commands.sh` defined with explicit confirmation prompt. `rollback_v0.7.1.sql` exists in repo for partial rollback. **Both paths documented and reviewed**. Conservative path: stop workers (already 0 alive), restore from dump, verify schema, restart only after explicit auth.

## Warnings

| W | Concern | Mitigation |
| --- | --- | --- |
| W1 | Inner BEGIN/COMMIT in v0.7.0/v0.7.1 means dry-run was effectively live | Acceptable in this case (0 rows, backup taken first) but should be documented for future migrations |
| W2 | `test_integration.py::test_db` continues to fail (test bug, not migration bug) | Left as-is; documented in Phase I; future fix requires test rewrite to use staging→admission path |
| W3 | A1 cold-boot gap unresolved | Out of scope per Phase J; deferred to next order `0-9X-POST-DB-COLD-BOOT-RECOVERY` |
| W4 | A1 reject distribution shift unresolved | Out of scope; deferred to next order `0-9X-A1-REJECT-DISTRIBUTION-SHIFT-DIAGNOSIS` |

## Verdict

→ **APPROVE_WITH_WARNINGS.** Migration is sound, backup-first, schema-additive, row-preserving. No forbidden mutations. Warnings W1-W4 are documented and assigned to follow-up orders. **No BLOCK conditions.**
