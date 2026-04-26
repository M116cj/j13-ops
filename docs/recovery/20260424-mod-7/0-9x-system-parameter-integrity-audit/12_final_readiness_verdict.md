# 0-9X-SYSTEM-PARAMETER-INTEGRITY-AUDIT — Final Verdict

## 1. Status

**SYSTEM_PARAMETERS_RED_BLOCK_COLD_START**

The audit identifies **9 CRITICAL drift items** (entirely DB schema gap from v0.7.1 governance migration not being applied) and **5 HIGH-severity** items (validation contract gaps + cold-start tool unsafety). Cold-start cannot proceed safely until these gaps are closed.

## 2. System Health Summary

| Subsystem | Verdict | Severity |
| --- | --- | --- |
| Runtime services | RUNTIME_PARAMETERS_OK (with caveat: reject distribution drift) | YELLOW |
| Environment / secrets | ENV_OK | GREEN |
| A1 generation parameters | A1_GENERATION_PARAMS_OK + A1_GENERATION_UNDOCUMENTED | YELLOW |
| Signal-to-trade | SIGNAL_PARAMS_OK | GREEN |
| Backtest / validation | **VALIDATION_CONTRACT_TOO_WEAK** | **RED** |
| Cost / horizon | NO_DRIFT (params) + minor funding bias | GREEN with footnote |
| Arena thresholds | ARENA_PARAMS_OK | GREEN |
| Arena telemetry | ARENA_TELEMETRY_RISK (silent insert failure) | YELLOW |
| **DB schema / session** | **DB_STALE_STATE + DB_VIEW_RISK + ADMISSION_SETTING_RISK** | **CRITICAL** |
| Telemetry | TELEMETRY_MISSING_EXPECTED | YELLOW |
| Cold-start tooling | TOOL_REQUIRES_SAFETY_REFACTOR (alpha_zoo_injection) | YELLOW |
| Governance | GOVERNANCE_OK | GREEN |

## 3. Subsystem Readiness Table

| Subsystem | GREEN / YELLOW / RED | Cold-start blocker? |
| --- | --- | --- |
| Runtime services | YELLOW | NO |
| Environment | GREEN | NO |
| A1 generation params | YELLOW | NO (but reject distribution shift needs investigation) |
| Signal-to-trade | GREEN | NO |
| Backtest gates | YELLOW | partial — current 4 gates work but lack 3 needed gates |
| Cost / horizon | GREEN | NO |
| Arena thresholds | GREEN | NO |
| **DB schema** | **RED** | **YES — primary blocker** |
| Telemetry | YELLOW | partial — engine_telemetry DB-side missing |
| Cold-start tools | YELLOW | YES — alpha_zoo_injection is currently unsafe |
| Governance | GREEN | NO |

→ **2 RED + 6 YELLOW + 4 GREEN.** RED items block cold-start.

## 4. Critical Risks (must close before cold-start)

| ID | Risk | Severity |
| --- | --- | --- |
| C1 | DB schema is at pre-v0.7.1 — `champion_pipeline_fresh`, `champion_pipeline_staging`, `champion_pipeline_rejected`, `champion_legacy_archive`, `engine_telemetry` tables MISSING; `admission_validator()` function MISSING; `fresh_insert_guard` trigger MISSING; `zangetsu.admission_active` session var MISSING | **CRITICAL** |
| C2 | Validation contract lacks 3 gates required to block SOL-only artifacts: `train_pnl > 0`, `combined_sharpe ≥ 0.4`, cross-symbol consistency ≥ 2/3 | **HIGH** |
| C3 | `alpha_zoo_injection.py` has unimplemented `--dry-run-one` flag AND its validator dependency is missing → would currently bypass validation if run | **HIGH** |
| C4 | A1 reject reason distribution shifted to `COUNTER_INCONSISTENCY` (50%) + `COST_NEGATIVE` (50%) — UNDOCUMENTED in prior governance orders | **MEDIUM** |
| C5 | `alpha_discovery.py` runs every */30 min via cron despite DEPRECATED guard — should be examined and disabled or unmarked | **MEDIUM** |

## 5. Cold-Start Blockers

Cold-start MUST NOT proceed until ALL of the following are resolved:

| Blocker | Resolution |
| --- | --- |
| **B1** — Apply v0.7.1 governance migration to live DB | Run `migrations/postgres/v0.7.1_governance.sql`; verify `champion_pipeline_fresh`, `champion_pipeline_staging`, `champion_pipeline_rejected`, `champion_legacy_archive`, `engine_telemetry` exist; verify `admission_validator()` function exists; verify triggers + session var registered |
| **B2** — Implement validation contract upgrade | Add `train_pnl > 0`, `combined_sharpe ≥ 0.4`, cross-symbol consistency gates per PR #41 next-order recommendation (TEAM ORDER 0-9X-VAL-FILTER-CONTRACT-UPGRADE-AND-EXPANDED-CALIBRATION-MATRIX) |
| **B3** — Make `alpha_zoo_injection.py` safe | implement working `--dry-run-one` body; gate live mode behind explicit governance flag; require `admission_validator()` to exist |
| **B4** — Investigate A1 reject distribution shift | trace `COUNTER_INCONSISTENCY` and `COST_NEGATIVE` paths; document in VERSION_LOG; confirm whether intentional or regression |
| **B5** — Resolve `alpha_discovery.py` cron status | either disable the cron entry or remove the DEPRECATED guard and document its purpose |

## 6. Final Recommendation

→ **DO NOT begin cold-start design until B1-B5 are resolved.**

The recommended next order should be the same as PR #41's recommendation, but with explicit DB migration as the FIRST step:

`TEAM ORDER 0-9X-DB-MIGRATION-AND-VAL-FILTER-CONTRACT-UPGRADE`

Phases:
1. **Phase A**: Verify the v0.7.1 migration script exists in repo (`migrations/postgres/v0.7.1_governance.sql`); apply to live DB; verify all expected objects materialize; run smoke tests against `admission_validator()`
2. **Phase B**: Implement the 3 missing val gates (train_pnl + combined_sharpe + cross-symbol)
3. **Phase C**: Re-run expanded calibration matrix (per PR #41) under new gates; determine whether ANY robust candidate exists
4. **Phase D**: Address `alpha_zoo_injection.py` safety (dry-run + validator guard) — only AFTER Phase A
5. **Phase E**: Investigate and resolve A1 reject distribution shift (B4)
6. **Phase F**: Resolve `alpha_discovery.py` cron status (B5)

After this order completes successfully, only THEN can a cold-start design order be considered.

## 7. Block Status (carried forward)

| Item | Status |
| --- | --- |
| alpha_zoo injection | **BLOCKED** (PR #41 NG conditions + new B3 blocker) |
| Live CANARY | **BLOCKED** |
| Runtime calibration change | **BLOCKED** until PR #41 NG1-NG5 + new B1-B5 |
| Cold-start design | **BLOCKED** until B1-B5 |
| **Cold-start execution** | **BLOCKED** |

## 8. Safety + Governance

| Item | Status |
| --- | --- |
| Source code mods | 0 |
| Schema mods | 0 |
| DB mutation | 0 |
| Service restart | 0 |
| Threshold change | 0 |
| Alpha injection | 0 |
| CANARY | NOT STARTED |
| Production rollout | NOT STARTED |
| Branch protection | intact (5/5 flags) |
| Signed commit | will be ED25519 |
| Forbidden ops count | **0** |

## 9. Final Declaration

```
TEAM ORDER 0-9X-SYSTEM-PARAMETER-INTEGRITY-AUDIT = SYSTEM_PARAMETERS_RED_BLOCK_COLD_START
```

This order made **0 source code / 0 schema / 0 cron / 0 secret / 0 DB / 0 alpha injection** changes. Pure read-only system inspection. Forbidden changes count = 0.

Recommended next order: **TEAM ORDER 0-9X-DB-MIGRATION-AND-VAL-FILTER-CONTRACT-UPGRADE** (B1 must be addressed first; merging B1+B2 into one order is appropriate because B2 needs the DB tables from B1 to function).

Cold-start design remains BLOCKED until all 5 critical/high blockers are resolved.
