# Phase 7 STOP Conditions

- **Scope**: 10 STOP triggers per 0-9 §7 + 5-field STOP report requirement.
- **Actions performed**: Recorded STOP triggers + STOP report schema; linked MOD-7 current STOP #1 invocation.
- **Evidence path**: 0-9 §7.
- **Observed result — triggers**:

Immediately stop if any of the following occurs:

1. **Signed commit cannot be produced** ← currently triggered by MOD-7 probe
2. PR flow cannot be used
3. Gate-A fails
4. Gate-B fails
5. Controlled-diff reports forbidden diff
6. Any unsigned/bypass push is attempted
7. Any production runtime mutation occurs outside scope
8. Any threshold is changed without explicit evidence
9. Arena 2 rejection reason remains mostly UNKNOWN_REJECT
10. SHADOW/CANARY evidence is missing

### STOP report schema (5 fields MANDATORY)

Per 0-9 §7: "If stopped, produce:"
1. Stop reason
2. Exact failing command or check
3. Evidence path
4. Rollback status
5. Next safe action

### Current MOD-7 STOP status

| # | Triggered? | Notes |
|---|---|---|
| 1 Signed commit cannot be produced | **YES** | Probe at 2026-04-24T02:45Z showed `verified:false` `reason:unsigned` on API PUT commits; see `mod7_stop_report.md` |
| 2 PR flow cannot be used | Derivative of #1 | Unsigned PR cannot be merged to main under `required_signatures=true` |
| 3 Gate-A fails | N/A (never executed) | No PR exists to run Gate-A against |
| 4 Gate-B fails | N/A (never executed) | same |
| 5 Controlled-diff forbidden diff | N/A | no code change attempted |
| 6 Any unsigned/bypass push attempted | **NOT TRIGGERED** (did not attempt after probe) | Claude Lead intentionally did NOT push to feature branch after probe showed no-signing; rule 2 + STOP #6 respected |
| 7 Production runtime mutation outside scope | **NOT TRIGGERED** | no runtime change made |
| 8 Threshold changed without evidence | **NOT TRIGGERED** | no threshold touched |
| 9 Arena 2 UNKNOWN_REJECT dominates | N/A | pre-P7-M1; telemetry does not exist yet |
| 10 SHADOW/CANARY evidence missing | N/A | no module promoted |

### Active STOP

STOP #1 (signed commit cannot be produced). Invoked; report written. See `mod7_stop_report.md` for the 5 required fields.

- **Forbidden changes check**: This doc is a record. No runtime state mutated.
- **Residual risk**:
  - Operating under STOP #1 means MOD-7 P7-PR1 execution is blocked until signing resolution.
  - STOP #6 was respected (no unsigned push attempted) — preserves governance integrity.
- **Verdict**: MOD-7 is currently STOPPED at condition #1. Clean halt. Next action is j13 unblock per `mod7_stop_report.md §5`.
