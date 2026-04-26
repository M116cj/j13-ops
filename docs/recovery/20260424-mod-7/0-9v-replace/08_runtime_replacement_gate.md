# 08 — Runtime Replacement Gate (G1-G15)

## 1. Gate verdict

**FAILED on G2 (working tree dirty).**

## 2. Per-gate evaluation

| # | Gate | Status | Evidence |
| --- | --- | --- | --- |
| G1 | Repo synced to latest governed main | **FAIL** | Alaya is on `f5f62b2b`; origin/main is `73b931d2`. 0 ahead, 10 behind. Sync NOT performed (blocked by G2). |
| G2 | Dirty state clean except evidence docs | **FAIL** | 3 modified runtime services + 4 modified/untracked Calcifer state + 2 untracked files. See `01` §4. |
| G3 | Rollback snapshot complete | PASS | See `02_rollback_snapshot.md`. |
| G4 | Old runtime process / launcher documented | PASS | crontab `watchdog.sh` + `arena13_feedback.py`; cp_api / dashboard-api / console-api systemd units. See `01` §5-§8. |
| G5 | Logs / env / secrets / runtime state preserved | PASS | No deletion; logs + venv + data preserved. See `02` §5. |
| G6 | Tests pass or non-blocking environment issue documented | DEFERRED | Mac proxy: 453 PASS / 0 regression. Alaya re-test deferred (see `04`). |
| G7 | Runtime safety audit PASS | PASS | No apply path; no APPLY mode; A2_MIN_TRADES=25; no consumer connection. See `05`. |
| G8 | No apply path exists | PASS | Three pre-existing trading helpers documented; no apply_budget / apply_plan / apply_consumer / apply_allocator / apply_canary symbols. See `05` §2. |
| G9 | No runtime-switchable APPLY mode exists | PASS | `MODE_DRY_RUN` constant only; no `mode == "APPLY"` flag; no env/config switch. See `05` §3. |
| G10 | Consumer not connected to generation runtime | PASS | Consumer module not even on Alaya yet; even after sync, source-text isolation tests will enforce. |
| G11 | A2_MIN_TRADES = 25 | PASS | Two literal occurrences both at 25. See `05` §5. |
| G12 | Telemetry source check complete | PASS (with note) | `arena_batch_metrics.jsonl` and `sparse_candidate_dry_run_plans.jsonl` MISSING; documented as expected pre-replacement state. See `06`. |
| G13 | Shadow validation PASS or documented non-blocking missing telemetry | DEFERRED | Tools not on Alaya; SHADOW_BLOCKED_MISSING_TOOLS. See `07`. |
| G14 | Branch protection intact | PASS | `enforce_admins=true / required_signatures=true / linear_history=true / allow_force_pushes=false / allow_deletions=false`. Verified via GitHub API at PR #27 merge time. |
| G15 | Signed PR-only flow preserved | PASS | All 10 prior PRs in chain went through signed PR; this PR will too. |

## 3. Gate roll-up

- **Critical FAIL**: G1, G2 (cannot fast-forward over dirty state)
- **PASS**: G3, G4, G5, G7, G8, G9, G10, G11, G12 (with telemetry note), G14, G15 — **11 PASS**
- **DEFERRED**: G6 (tests pending sync), G13 (shadow pending tool install) — **2 DEFERRED**
- **FAIL**: G1, G2 — **2 FAIL**

Per order §12:

> "If any critical gate fails: Status = BLOCKED_REPLACEMENT_GATE. Do not switch runtime process."

G1 and G2 are critical and FAIL → **BLOCKED_REPLACEMENT_GATE.**

## 4. Why this is the correct outcome

The dirty state on Alaya contains uncommitted WIP from when P7-PR4B was
being developed directly on Alaya (before the work moved to Mac and
shipped via PR #18). That WIP:

- Modifies the same files as PR #18 but with **different content**
  (the PR-#18 markers `_p7pr4b_*` and helper names
  `normalize_arena_stage` are NOT present in the Alaya dirty version).
- Cannot be auto-resolved — order forbids stash / reset / merge.
- Must be inspected by j13 to decide: discard / preserve in feature
  branch / something else.

Auto-replacing the runtime here would either:

1. Force-push over the dirty WIP (forbidden), OR
2. Encounter merge conflicts that block fast-forward.

Either way, Phase I (runtime switch) cannot safely happen.

## 5. Remediation paths (j13 chooses)

See `03` §7 for the two paths. Quick recap:

**Path A — discard WIP** (simplest, recommended if WIP is obsolete):

```bash
ssh j13@100.123.49.102 "
  cd /home/j13/j13-ops
  # Inspect first
  git diff zangetsu/services/arena23_orchestrator.py | head -60
  git diff zangetsu/services/arena_pass_rate_telemetry.py | head -60
  git diff zangetsu/services/generation_profile_metrics.py | head -60
  # If j13 confirms discard:
  git restore zangetsu/services/arena23_orchestrator.py \\
              zangetsu/services/arena_pass_rate_telemetry.py \\
              zangetsu/services/generation_profile_metrics.py
  # Move untracked WIP files
  mkdir -p ~/alaya-wip-backup-\$(date +%Y%m%d)
  mv zangetsu/tests/test_a2_a3_arena_batch_metrics.py ~/alaya-wip-backup-\$(date +%Y%m%d)/
  mv docs/governance/snapshots/2026-04-24T221219Z-pre-p7-pr4b.json ~/alaya-wip-backup-\$(date +%Y%m%d)/
  # Decide on Calcifer state files (recommend: add to .gitignore in a separate order)
  git restore calcifer/maintenance.log calcifer/maintenance_last.json calcifer/report_state.json
  rm calcifer/deploy_block_state.json
  # Then sync
  git checkout main
  git pull --ff-only origin main
  git rev-parse HEAD  # expected: 73b931d2df695572b0816fc1ebe1d10dbe9a5564
"
```

**Path B — preserve WIP** (if j13 wants to keep it):

Requires a separate signed PR to land the WIP through GitHub review.
Then fast-forward.

## 6. After remediation

Re-run 0-9V-REPLACE from Phase C → I:

1. Phase C: fast-forward to `73b931d2`
2. Phase D: run pytest on the 9 sparse / canary suites
3. Phase E: re-run safety audit on new code
4. Phase F: telemetry sources still missing (expected; resolved by 0-9S-CANARY-OBSERVE-LIVE)
5. Phase G: run shadow validation with new tools
6. Phase H: re-evaluate G1-G15 (expected all PASS or G6/G13 documented PASS)
7. Phase I: runtime switch via `systemctl restart` or watchdog cycle

## 7. Final gate verdict

```
G1: FAIL  (sync not performed)
G2: FAIL  (dirty working tree)
G3: PASS
G4: PASS
G5: PASS
G6: DEFERRED
G7: PASS
G8: PASS
G9: PASS
G10: PASS
G11: PASS
G12: PASS (with telemetry note)
G13: DEFERRED
G14: PASS
G15: PASS

OVERALL: BLOCKED_REPLACEMENT_GATE on G1 + G2.
```
