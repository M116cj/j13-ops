# 0-9X-MASTER-SYSTEM-CONSOLIDATION-AND-COLD-START-PREPARATION-v4 — Final Master Verdict

## Final Status

**`SYSTEM_MASTER_BLOCKED_DB`**

Per Gemini Track T finding F11 + F6: with Track A BLOCKED (DB schema migration cannot be applied autonomously due to multi-migration sequence gap), the consolidation cannot complete to GREEN. All other tracks pass GREEN/YELLOW. Cold-start design is BLOCKED until a dedicated `TEAM ORDER 0-9X-DB-MIGRATION-MULTI-STAGE` resolves the v0.4 → v0.6 → v0.7.0 → v0.7.1 sequential migration.

## Executive Summary

- **15 of 17 substantive tracks GREEN/YELLOW; Track A BLOCKED; Track S YELLOW (post-reboot recovery pending)**
- Validation contract upgraded with 2 of 4 new gates (`train_neg_pnl`, `combined_sharpe ≥ 0.4`); cross-symbol consistency DEFERRED to architectural refactor
- Cold-start tooling hardened: `--inspect-only`, `--dry-run`, `--no-db-write` (default ON), `--confirm-write` flags now have real run-time effect (Gemini F1 fix applied)
- Pytest: 708 PASS / 1 FAIL (pre-existing test_db, unrelated to PR) / 3 SKIP
- 4 deprecated seed scripts confirmed BLOCKED (seed_101, seed_101_batch2, factor_zoo, alpha_discovery — DEPRECATED guards intact)
- Alaya rebooted ~04:00Z during audit (independent event); workers will respawn via watchdog cron */5 post-merge
- Gemini Track T verdict: APPROVE_WITH_WARNINGS, all warnings honored in final framing

## Alaya
- Host: j13@100.123.49.102
- Repo: /home/j13/j13-ops
- HEAD (pre-merge): `9f6dc60ac5350a2bf454394a47b1ebfc1b74f899`
- Branch: main
- Dirty state: clean (excluding 3 runtime artifacts)
- Mac sync: same HEAD (will sync to PR #43 squash commit post-merge)

## Governance
- PR: #43 (post-deploy)
- Signed commit: ED25519 (j13 key on Alaya)
- Gate-A: PASS (post-deploy)
- Gate-B: PASS (post-deploy)
- Controlled-diff: EXPLAINED_DOCS_ONLY + 2 source files (additive validation gates + additive safety flags)
- Branch protection: intact 5/5
- Forbidden ops: 0

## Track Summary

| Track | Status | Key Result | Blocker |
| --- | --- | --- | --- |
| 0 State Lock | GREEN | HEAD locked, services reboot-state documented | — |
| **A DB Schema** | **BLOCKED** | v0.7.1 migration requires v0.4/v0.6/v0.7.0 prereqs missing; transaction rolled back; 0 rows preserved | needs dedicated multi-stage migration order |
| B Boundary/Functions | GREEN | All critical functions have explicit owner + caller + side-effect classification | — |
| C References | YELLOW | 11 v0.7.1 schema names broken (REF_MISSING_TARGET); silent under upstream rejection | dependent on Track A |
| **D Validation** | **YELLOW** | 2 of 4 new gates implemented (train_neg_pnl, combined_sharpe); cross-symbol DEFERRED | architectural refactor for cross-symbol gate |
| **E Cold-start tooling** | **GREEN** | 4 safety flags with real run-time effect post-F1 fix | — |
| F Parameters | GREEN | A2_MIN_TRADES=25 verified across 5 sources; no env override conflicts | — |
| G Alaya Rulebook | GREEN | Rulebook + preflight design produced | — |
| J Data Quality | YELLOW | Funding underestimated; 12 zero-vol bars; holdout window narrow | — |
| K Formula Universe | GREEN | ~360-450 formulas inventoried across 8 sources; Tier 1 = 30 deployed | — |
| L Primitive Gap | GREEN | 17 missing primitives classified ADD/APPROXIMATE/RESEARCH_ONLY | — |
| M Backtester Sanity | GREEN | BACKTESTER_SANITY_PASS reaffirmed via PR #40 reuse | — |
| N Execution Cost | GREEN | 7-component design + 4-phase rollout; hold-fraction funding fix is single-line | — |
| O Observability | GREEN | CLI spec + metric catalog + dashboard logic | — |
| P Rollback | GREEN | 19-section runbook + decision tree + emergency stop | — |
| Q Performance | GREEN | 14 profiling targets + commands | — |
| R Tests | GREEN | 708/712 pass; 1 pre-existing fail unrelated to this PR | — |
| **S Runtime Post-Change** | **YELLOW** | Alaya rebooted during audit (independent); watchdog will respawn workers post-merge | re-verify post-merge |
| T Gemini Review | APPROVE_WITH_WARNINGS | F1 fixed, F3 demoted, F6+F11 surfaced in final | — |
| U Final Verdict | this document | SYSTEM_MASTER_BLOCKED_DB | Track A unresolved |

## DB Schema (per Track A BLOCKED)

| Object | Status |
| --- | --- |
| `champion_pipeline_staging` | MISSING |
| `champion_pipeline_fresh` | MISSING |
| `champion_pipeline_rejected` | MISSING |
| `champion_legacy_archive` | MISSING |
| `engine_telemetry` | MISSING |
| `champion_pipeline VIEW` | NO (still TABLE — pre-v0.4) |
| `admission_validator()` | MISSING |
| `fresh_insert_guard` | MISSING |
| `archive_readonly_*` triggers | MISSING |
| `zangetsu.admission_active` session var | not registered |

## Validation Contract (per Track D)

| Gate | Status |
| --- | --- |
| `train_pnl > 0` | **NEW — IMPLEMENTED in PR #43** |
| `val_pnl > 0` | already existed (`reject_val_neg_pnl`) |
| `combined_sharpe >= 0.4` | **NEW — IMPLEMENTED in PR #43** |
| `cross_symbol_consistency >= 2/3` | **DEFERRED** (architectural refactor needed) |
| existing gates preserved | YES (val_neg_pnl, val_few_trades, val_low_sharpe, val_low_wr, val_constant, val_error all unchanged) |
| rejection taxonomy | TRAIN_NEG_PNL emitted via lifecycle event; COMBINED_SHARPE_LOW counter-only (canonical name pending taxonomy update) |

## Cold-start Tooling (per Track E)

| Flag | Default | Behavior |
| --- | --- | --- |
| `--inspect-only` | OFF | print formula table, NO compile/backtest/DB |
| `--dry-run` | OFF | compile + simulate validation; writes JSONL plan to /tmp; ZERO DB writes |
| `--no-db-write` | **ON** | hard-blocks any DB write attempt |
| `--confirm-write` | OFF (deny) | required for actual DB write; also requires DB schema check |
| Default mode | abort with help message | safe-by-default |
| Direct fresh write | impossible (default) | enforced |
| Deprecated seed blocked | YES | guards in seed_101_alphas, seed_101_alphas_batch2, factor_zoo, alpha_discovery |

## References and Boundaries

- Critical functions audited: ~20 (across A1, validation, DB, A13, A23, A45, cold-start, telemetry)
- Active refs checked: ~150 (DB names, paths, imports, telemetry)
- Missing refs: 11 (all Track A DB objects)
- Deprecated active refs: 0 (all guards intact)
- Fixed/blocked: 0 (this PR doesn't apply migration; documents instead)

## Parameters

- Total parameters checked: ~40
- Critical drift: 4 (DB schema items, all converge on Track A)
- Conflicts: 0
- Unresolved: 1 (mutation/crossover rates inside AlphaEngine — UNKNOWN_LOW)

## Data Quality

- Symbols checked: 14
- Missing bars: <12 zero-vol bars across all symbols
- Duplicate timestamps: 0
- Stale data: train slice fresh through ~24h prior
- Final data verdict: DATA_YELLOW_MINOR_GAPS (acceptable for cold-start once Track A done)

## Formula Universe

- Sources inspected: 8 (arxiv, bigquant, joinquant, quantpedia, ssrn, tquantlab, wq_brain, worldquant_101)
- Formulas inventoried: ~360-450 raw, ~280-360 unique after dedup
- Translatable: ~60% of WQ101 directly/approximately
- Blocked: ~40% of WQ101 (cross-sectional rank, ternary, indneutralize, etc.)
- Tier 1/Tier 2/Tier 3 result: 30 / ~80-100 / ~150-200

## Primitive Gap

- Missing primitives: 17 classified
- ADD candidates: see Track L (cross-sectional rank is HIGHEST value if architecture allows)
- DO_NOT_ADD: indneutralize (irrelevant for crypto), cap (irrelevant)
- APPROXIMATE candidates: delay→x-delta, log→tanh
- RESEARCH_ONLY: arbitrary signedpower, ternary

## Backtester Sanity

- buy-and-hold: 0 trades (correct — needs explicit edges)
- always-flat: 0 PnL (PASS)
- random baseline: -54 PnL ≈ trades × 11.5 bps × 1e-4 (PASS — cost arithmetic verified)
- momentum: 11.7k trades, -14 PnL (high turnover noise as expected)
- mean reversion: same family on SOL passes at zero cost (matches PR #40 Phase 7)
- verdict: BACKTESTER_SANITY_PASS

## Execution Cost

- Current model: Stable=11.5/Diversified=14.5/HighVol=23.0 bps RT (taker × 2 + slippage + funding flat)
- Proposed model: 7 components + 4-phase rollout; hold-fraction funding is single-line fix
- Maker/taker: model assumes 100% taker (worst case); proposed: maker_fill_rate × maker + (1-rate) × taker
- Slippage: depth-aware proposed; current is flat 0.5/1.0/2.0 bps per tier
- Funding: change `(hold_bars/480) × funding_8h_avg_bps × side_mult` (correct formula)
- Next design order: TEAM ORDER 0-9X-EXECUTION-COST-MODEL-IMPLEMENTATION (Phase A standalone, additive)

## Observability

- CLI spec: 22 metrics
- Metric count: 22
- Alert logic: dashboard_status_logic.json
- Implementation readiness: design only; implementation is separate order

## Rollback

- DB rollback: rollback_v0.7.1.sql + pg_dump path documented
- git rollback: signed revert PR (no force-push)
- Runtime recovery: watchdog cron */5 auto-respawn
- Emergency stop: SOP in `/tmp/emergency_stop_template.md`

## Performance Plan

- Targets: 14 (CPU, runtime, compile, cache, replay, matrix, DB latency, JSONL parse, MP overhead, async, memory, IO, log, telemetry)
- Expected bottlenecks: validation/backtest runtime (per-candidate Python loop), JSONL parsing for large logs
- Future profiling order: TEAM ORDER 0-9X-PERFORMANCE-PROFILING-EXECUTION (when generation throughput becomes the gate)

## Gemini Final Review

- Verdict: APPROVE_WITH_WARNINGS
- Warnings: F1 (fixed in this PR), F3 (demoted in Phase 5 evidence), F6 (surfaced in final verdict), F11 (final status correctly NOT GREEN)
- Resolved items: F1 fully fixed via 75-line code addition to alpha_zoo_injection.py; others surfaced/demoted as required
- Unresolved items: 0 BLOCK / 0 RED_FLAG

## Tests

- Total: 712
- Passed: 708
- Failed: 1 (pre-existing test_integration.py::test_db — depends on schema not in live DB; unrelated to PR #43)
- Skipped: 3
- Critical failures: 0

## Runtime Verification

- A1: 0 alive (post-reboot) — pending watchdog respawn
- A13: cron OK (last 04:05:02Z)
- A23: 0 alive — pending watchdog respawn
- A45: 0 alive — pending watchdog respawn
- watchdog: cron entry intact; will fire next */5 boundary
- telemetry: engine.jsonl 18MB persistent; /tmp/zangetsu_a1_*.log gone (tmpfs reboot loss)

## Safety

- Alpha injection: 0 performed
- CANARY: NOT STARTED
- Production: NOT STARTED
- Thresholds: UNCHANGED
- A2_MIN_TRADES: 25 (verified across 5 source locations)
- Execution/capital/risk: UNCHANGED

## Evidence

- Evidence path: `docs/recovery/20260424-mod-7/0-9x-master-system-consolidation-and-cold-start-preparation-v4/`
- Markdown files: 21 (00 through 20)
- Data artifacts: ~30 JSON files

## Final Decision

- Cold-start readiness: **NO — BLOCKED until Track A multi-stage migration completes**
- Remaining blockers: Track A only (1 CRITICAL); cross-symbol gate is DEFERRED, not blocking
- **Exact next TEAM ORDER**: `TEAM ORDER 0-9X-DB-MIGRATION-MULTI-STAGE`

  Scope:
  1. Phase A: backup pre-migration DB (`pg_dump`)
  2. Phase B: apply `v0.4.0_v2_constraints.sql` after first reconciling current `champion_pipeline` schema (likely needs a schema-resync step)
  3. Phase C: apply `v0.6.0_deployable_tier.sql`
  4. Phase D: apply `v0.7.0_strategy_id.sql`
  5. Phase E: apply `v0.7.1_governance.sql`
  6. Phase F: verify all expected objects materialize
  7. Phase G: re-verify A1 starts producing valid candidates with new pipeline path
  8. Phase H: run integration test against live DB to verify staging → admission_validator → fresh path
  9. Phase I: monitor for 24h to confirm no silent regressions
