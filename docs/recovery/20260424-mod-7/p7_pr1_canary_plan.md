# P7-PR1 CANARY Plan — Arena Rejection Taxonomy + Telemetry Baseline

Per TEAM ORDER 0-9E §15. This plan defines how the P7-PR1 telemetry is enabled in a bounded production-adjacent CANARY window after SHADOW has PASSed.

## 1. Scope

- Enable the telemetry baseline (classifier + collector + candidate trace) in a **bounded** production-adjacent observation context.
- Observation remains passive: the canary wrapper calls `make_rejection_trace()` at Arena reject paths to populate a `TelemetryCollector`, and writes the collector summary to an evidence file. **No alpha / Arena / threshold / promotion / execution behavior is mutated.**

## 2. Canary limits

- **Telemetry only.** No candidate promotion mutation. No trading behavior mutation. No threshold mutation.
- **Single symbol, single regime.** The canary activation wrapper runs against exactly one symbol (recommended: `BTCUSDT`) in one regime window (duration ≤ 1 arena pipeline cycle) for the first canary run.
- **Read-only process.** The canary wrapper runs in its own process; it does not share state with the production Arena pipeline beyond parsing its log output. It does not inject code into any existing Arena service.
- **Rollback command pre-authored and verified.** See §6.

## 3. Start conditions

The CANARY window may start only if **all** of the following are true:

- Gate-A passed on the P7-PR1 PR (this PR).
- Gate-B passed on the P7-PR1 PR (this PR).
- Controlled-diff on the P7-PR1 PR = **EXPLAINED** with `forbidden_diff = 0`.
- SHADOW plan accepted (SHADOW ran at least once with PASS verdict — see `p7_pr1_shadow_plan.md §6`).
- A separate authorized order (P7-PR1-CANARY or P7-PR2-CANARY) explicitly requests CANARY activation. This PR alone does NOT authorize CANARY.
- Branch protection invariants still hold: `enforce_admins=true`, `required_signatures=true`, `linear_history=true`.
- `main` HEAD still matches the post-P7-PR1 merge SHA (no drift).

## 4. Stop conditions (immediate abort)

Terminate the CANARY window immediately if any of the following occurs:

- Telemetry breaks runtime (e.g., wrapper process raises unhandled exception that back-pressures Arena log emission).
- `unknown_reject_ratio()` exceeds 0.15 over a full sample window (indicates classifier drift; must extend `RAW_TO_REASON` before re-running).
- Controlled-diff during or after the canary window reports a forbidden diff on any tracked surface.
- `deployable_count` source cannot be traced (i.e., `derive_deployable_count()` returns empty `breakdown_by_*` despite non-zero candidates — indicates data plumbing gap).
- Any production mutation detected (alpha formula change, threshold change, champion promotion change, execution behavior change, live capital change).
- Any unauthorized branch protection change detected.
- Arena runtime service health degrades (systemd unit transitions to failed; engine.jsonl mtime freezes > 10 min).

## 5. Expected deliverables from a CANARY run

```
docs/rehearsal/p7-pr1/
  canary_plan.md                ← reference to this file
  canary_execution_log.txt      ← structured telemetry summary for the canary window
  canary_verdict.md             ← pass / fail with explicit forbidden-diff result + metric snapshot
  rollback_runbook.md           ← exact commands to revert (see §6)
```

## 6. Rollback (pre-authored + manually verified)

Because CANARY does not mutate production state, rollback is deliberately trivial:

```
# Terminate the canary wrapper process (if still running)
pkill -f 'p7_pr1_canary_wrapper'  # pattern name set by the canary order

# Retain / archive the canary evidence
mv docs/rehearsal/p7-pr1/canary_execution_log.txt \
   docs/rehearsal/p7-pr1/canary_execution_log.ABORTED.$(date -u +%Y%m%dT%H%M%SZ).txt

# Controlled-diff sanity: verify no production state tracked by snapshot moved
bash scripts/governance/capture_snapshot.sh post-canary-rollback
python3 scripts/governance/diff_snapshots.py <pre-canary.json> <post-canary-rollback.json>
```

Rollback does NOT require:
- A revert-commit (no commit was made during CANARY — wrapper writes only to `docs/rehearsal/p7-pr1/*`).
- A service restart (no service was modified).
- A data migration (no schema change).
- A branch protection change.

If controlled-diff after rollback still shows forbidden diff, escalate: the wrapper contained an unintended side effect and the wrapper code must be audited before any re-attempt.

## 7. Canary PASS criteria

The CANARY verdict is PASS iff **all** of the following hold at the end of the window:

- SHADOW PASS still valid (no regression since SHADOW).
- All 6 canary minimum requirements per 0-9E §15 met (start condition documented, stop condition documented, rollback command documented, expected metrics documented, forbidden-diff check clean, post-run verdict written).
- Forbidden-diff = 0 throughout the window.
- Alert thresholds (controlled-diff + Arena runtime health) not breached.
- Rollback command dry-run exercised at least once during the canary window (proves rollback path is live, not theoretical).
- `unknown_reject_ratio()` < 0.15.
- `derive_deployable_count()` produces actionable provenance for at least one candidate cohort.

Only after CANARY PASS can a subsequent order authorize promotion of telemetry to always-on mode (P7-PR2+).

## 8. Non-authorization (explicit)

This CANARY plan does NOT authorize:
- Threshold tuning based on telemetry (a future order can request after observation).
- Arena 2 root-cause fixes (strictly out of P7-PR1 scope).
- Champion promotion rule changes.
- Production rollout declarations.

This CANARY plan is only about bounded observation to validate that the P7-PR1 telemetry API works under production-adjacent conditions without regressing decision behavior.
