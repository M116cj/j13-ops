# 0-9P-AUDIT — Profile Attribution Coverage and Replay Validation Final Report

## 1. Status

**COMPLETE — pending Gate-A / Gate-B / signed merge on Alaya side.**

## 2. Baseline

- origin/main SHA at start: `a8a8ba9786e83e20e501fc5ffa76ce1601cef59f`
- branch: `phase-7/0-9p-audit-profile-attribution-validation`
- PR URL: filled in after `gh pr create`
- merge SHA: filled in after merge
- signature: ED25519 SSH `SHA256:vzKybH9THchzB17tZOfkJZPRI/WGkTcXxd/+a7NciC8`

## 3. Mission

Validate that 0-9P passport persistence delivers clean enough
attribution for PR-C / 0-9R-IMPL-DRY to consume. Read-only / offline.

## 4. What changed

| File | Type | Notes |
| --- | --- | --- |
| `zangetsu/tools/__init__.py` | new package | Offline tools namespace |
| `zangetsu/tools/profile_attribution_audit.py` | new offline tool | `audit()`, `replay_validate()`, `classify_verdict()`, `verdict_blocks_consumer_phase()`, JSON-line parser, schema lock |
| `zangetsu/tests/test_profile_attribution_audit.py` | new test file | 56 tests |
| `docs/recovery/20260424-mod-7/0-9p-audit/01..08*.md` | evidence docs | 8 markdown artifacts |

**Zero runtime files modified.**

## 5. Audit metrics shipped

`AttributionAuditResult` 24 fields:

- 4 stage counts (`total_events`, `total_a1_events`, `total_a2_events`, `total_a3_events`)
- 4 source counts (`passport_identity`, `orchestrator_fallback`, `unknown_profile`, `unavailable_fingerprint`)
- 4 source rates
- 3 cross-stage match counts (A1→A2, A2→A3, mismatch)
- 1 mismatch rate
- 5 per-profile breakdowns (`stage_counts_by_profile`, `reject_reason_distribution_by_profile`, `signal_too_sparse_rate_by_profile`, `oos_fail_rate_by_profile`, `deployable_count_by_profile`)
- `verdict` + `verdict_reasons`

## 6. Verdict thresholds

| Rate | GREEN max | YELLOW max | RED |
| --- | --- | --- | --- |
| `unknown_profile_rate` | 0.05 | 0.20 | > 0.20 |
| `profile_mismatch_rate` | 0.01 | 0.05 | > 0.05 |
| `fingerprint_unavailable_rate` | 0.05 | 0.20 | > 0.20 |

`verdict_blocks_consumer_phase(VERDICT_RED) is True` — PR-C cannot
proceed when verdict is RED.

## 7. Runtime isolation

Audit module imports only:
- `zangetsu.services.generation_profile_identity` (constants +
  `resolve_attribution_chain` helper).

No runtime module imports the audit module (verified by
`test_audit_does_not_modify_runtime_files`).

## 8. Behavior invariance

Zero runtime files modified. All 6 CODE_FROZEN runtime SHAs
zero-diff. `A2_MIN_TRADES`, ATR/TRAIL/FIXED grids, A3 segment
thresholds, Arena pass/fail logic, champion promotion path,
`deployable_count` semantics — all unchanged. Verified by source-text
tests.

## 9. Test results

56 / 56 PASS. Adjacent suites: 212 PASS / 0 regression (P7-PR4B 54 +
0-9O-B 62 + 0-9P 40 + 0-9P-AUDIT 56).

## 10. Controlled-diff

Expected: **EXPLAINED** (docs + new offline tool + tests; no
CODE_FROZEN runtime SHA changed; no `--authorize-trace-only`
needed).

## 11. Gate-A / Gate-B / Branch protection

Expected: **PASS / PASS / INTACT.**

## 12. Forbidden changes audit

- CANARY: NOT started.
- Production rollout: NOT started.

## 13. Remaining risks

- **Verdict expiry**: a GREEN verdict at merge time does not
  guarantee future GREEN. PR-C consumer treats verdict as a per-day
  input, not a one-time permission slip.
- **Source classification heuristic**: aggregate `arena_batch_metrics`
  events lack a stable `attribution_source` field today.
  `classify_attribution_source` defaults to "passport" when no
  source field is present and pid is known — this is conservative
  and may overstate passport coverage. Replay validation is the
  authoritative path for exact classification.
- **Cross-stage match counting** uses naive sequential pairing per
  stage — fine for aggregate audit, but cannot detect per-candidate
  attribution swaps. Out of 0-9P-AUDIT scope; flag for future
  per-candidate audit order.
- **Sample-size**: small windows yield noisy rates. Operator runbook
  requires ≥ 7 days + meaningful event volume before treating
  verdict as actionable.

## 14. Recommended next action

**PR-C / 0-9R-IMPL-DRY — Sparse-Candidate Black-Box Optimization
Dry-Run Consumer.** Build `feedback_budget_consumer.py` limited to
PB-FLOOR + PB-DIV + PB-SHIFT dry-run planning. Consumer must read
the audit verdict at runtime and refuse actionable recommendations
when verdict is RED.
