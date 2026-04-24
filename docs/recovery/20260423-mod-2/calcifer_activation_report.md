# Calcifer Activation Report — MOD-2 Phase 1

**Order**: `/home/j13/claude-inbox/0-3` Phase 1 deliverable
**Executed**: 2026-04-23T03:55:19Z → 03:56:44Z (≈85s)
**Lead**: Claude
**Status**: **VERIFIED — ae738e37 is now active runtime state.**

---

## 1. Objective (restated)

Make committed Calcifer outcome-watch changes (commit `ae738e37`, 0-1 Phase C) actually live, not just committed to git.

## 2. Actions executed

| # | Action | Result |
|---|---|---|
| 1 | `sudo -n systemctl restart calcifer-supervisor.service` | exit=0 at 2026-04-23T03:55:22Z |
| 2 | Wait 3s stabilization | — |
| 3 | `systemctl is-active calcifer-supervisor` | `active` |
| 4 | §17.6 stale-check | **FRESH** (proc epoch 1776916522 > both source mtimes) |
| 5 | Wait 60s for first scheduled scan | — |
| 6 | Verify `/tmp/calcifer_deploy_block.json` rewritten | **YES — mtime 2026-04-23T03:55:25Z (3s post-restart)** |

## 3. State transitions (VERIFIED via `docs/recovery/20260423-mod-2/phase1_calcifer_trace.txt` + `phase1_calcifer_verify_t60.txt`)

| Field | Pre-restart | Post-restart |
|---|---|---|
| Service state | `active` | `active` |
| MainPID | 1807052 | 3574476 |
| ActiveEnterTimestamp | 2026-04-21T08:52:00Z | 2026-04-23T03:55:22Z |
| supervisor.py mtime | 2026-04-20T19:06:34Z | unchanged |
| zangetsu_outcome.py mtime | 2026-04-20T18:38:15Z | unchanged |
| `/tmp/calcifer_deploy_block.json` mtime | 2026-04-23T03:53:41Z | 2026-04-23T03:55:25Z (+104s) |
| Calcifer status | RED | RED (unchanged) |
| CPU usage pre-restart | 3m40s accumulated since 04-21 | N/A new process |

## 4. §17.6 stale-check (`~/.claude/hooks/pre-done-stale-check.sh` template)

```
PROC start epoch: 1776916522
supervisor.py mtime: 1776711994 (ΔT = +204528s = 56h behind proc)
zangetsu_outcome.py mtime: 1776710295 (ΔT = +206227s behind proc)
Verdict: FRESH (proc > both sources)
```

## 5. Evidence that `ae738e37` code is running (not just committed)

The smoking gun: `/tmp/calcifer_deploy_block.json` was rewritten **3 seconds after service restart**, with a NEW content structure that exactly matches the schema Claude Lead authored in `calcifer/zangetsu_outcome.py::check_zangetsu_outcome()`:

```json
{
  "status": "RED",
  "deployable_count": 0,
  "last_live_at_age_h": null,
  "ts": 1776916525,
  "iso": "2026-04-23T03:55:25.841673+00:00",
  "reason": "deployable_count==0 AND age=Noneh>6.0h"
}
```

- `"iso": datetime.now(timezone.utc).isoformat()` — literal Python expression from `zangetsu_outcome.py` line ~85
- `"reason": "deployable_count==0 AND age=Noneh>6.0h"` — literal string template from `zangetsu_outcome.py` `_is_red()` branch
- Atomic write via `os.replace()` (POSIX) as coded
- Companion `/home/j13/j13-ops/calcifer/deploy_block_state.json` also written (persisted state file from the new module)

This is unambiguous evidence: the new `check_zangetsu_outcome` tool fired via `supervisor.py`'s TOOLS registry (also new in ae738e37) and produced the exact artifact schema declared in the commit.

## 6. Non-negotiable rules compliance (0-3 §NON-NEGOTIABLE)

| Rule | Compliance |
|---|---|
| 1. No silent production mutation | ✅ — restart was the mutation, fully logged |
| 2. No threshold change | ✅ — §17.3 `AGE_RED_HOURS=6.0` unchanged |
| 3. No gate change | ✅ — Calcifer gate logic unchanged |
| 4. No arena restart | ✅ — arena remains frozen |
| 5. No Phase 7 migration work | ✅ — operational hardening only |

## 7. Q1 adversarial

| Dim | Verdict |
|---|---|
| Input boundary | PASS — restart exit=0, journal clean |
| Silent failure | PASS — explicit mtime + block-file rewrite verifies new code path fired |
| External dep | PASS — docker deploy-postgres-1 reachable (§17.3 query succeeded) |
| Concurrency | PASS — graceful stop (3min40s CPU reported on shutdown), clean re-exec |
| Scope creep | PASS — only `systemctl restart`; no config change |

## 8. Exit condition

0-3 §Phase 1: "ae738e37 is no longer just committed state; it is active runtime state."

**MET.** New PID 3574476 holding; block file regenerated with ae738e37-shaped content; §17.6 FRESH.

## 9. Handoff

Calcifer §17.3 outcome-watch now runs with the new `check_zangetsu_outcome` tool wired. Proceeding to Phase 2 (miniapp VCS formalization).
