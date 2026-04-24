# SHADOW + CANARY Rehearsal Standard

- **Scope**: The minimum standard every Phase 7 module must meet for SHADOW and CANARY rehearsals per 0-9 §3 P7-M6.
- **Actions performed**: Transcribed 0-9 §3 P7-M6 verbatim + added evidence-file convention per MOD-6 Controlled-Diff framework.
- **Evidence path**: 0-9 §3 P7-M6; MOD-6 `controlled_diff_framework.md`.
- **Observed result — standard**:

### SHADOW mode (observation, no mutation)
- Module runs live or replayed flow
- NO production mutation (enforced by Controlled-Diff forbidden-diff + cp_api write-safety middleware)
- NO capital allocation
- NO threshold tuning during observation
- Evidence logged (snapshot every 15min during SHADOW window; full log retained)

### CANARY mode (limited activation)
- Limited activation — bounded scope (e.g., 1 symbol, 5% time window, specific CP rollout_tier=CANARY_X%)
- Rollback path ready + tested (runbook pre-authored + manually verified)
- Controlled-diff clean (no forbidden diff during window; explained diffs traceable to module commits only)
- Service health monitored (obs_metrics alert thresholds set pre-canary)

### Minimum CANARY requirements (0-9 §3 P7-M6 verbatim)
1. Start condition documented
2. Stop condition documented
3. Rollback command documented
4. Expected metrics documented
5. Forbidden-diff check clean
6. Post-run verdict written

### Evidence file convention (MOD-7 addition)
```
docs/rehearsal/<module_id>/
  shadow_plan.md              — start/stop/duration/expected metrics
  shadow_execution_log.txt    — live stdout + snapshots
  shadow_verdict.md           — post-run verdict with forbidden-diff result
  canary_plan.md              — scope / rollout_tier / rollback command
  canary_execution_log.txt
  canary_verdict.md
  rollback_runbook.md         — exact commands to revert to pre-canary state
```

### Verdict criteria per mode

**SHADOW VERDICT = PASS** iff:
- No production mutation detected (Controlled-Diff forbidden-diff = 0)
- Module telemetry produces coherent output (≥ 95% of events have full traceability)
- No service health degradation

**CANARY VERDICT = PASS** iff:
- SHADOW already PASSed
- All 6 minimum requirements met
- Forbidden-diff = 0 during canary window
- Alert thresholds not breached
- Rollback path exercised at least once (dry-run or live) during canary

**PROMOTION = ALLOWED** iff SHADOW PASS + CANARY PASS + Gate-B all checks green.

- **Forbidden changes check**: This standard does not mutate anything. It sets the BAR that future module migrations must clear.
- **Residual risk**:
  - Standard is documentation-level; Phase 7 first real migration (P7-PR1) exercises it for the first time.
  - Controlled-Diff cron is not yet running (MOD-6 delivered manual protocol). Phase 7 module migrations must capture snapshots manually at SHADOW/CANARY boundaries until cron lands.
- **Verdict**: Standard is the operational template. Every Phase 7 module migration PR must include a `shadow_plan.md` + `canary_plan.md` linked from PR body field 9 + 10.
