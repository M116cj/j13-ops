# 02 — Rollback Snapshot

## 1. Old runtime SHA

`f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52` (= PR-A 0-9P merge baseline, 2026-04-25 16:32 UTC)

## 2. Old branch

`phase-7/p7-pr4b-a2-a3-arena-batch-metrics` (NOT `main`)

## 3. Old working tree status

Same `git status --porcelain=v1` output as captured in `01_old_runtime_inventory.md` §4. 9 entries (3 modified runtime services + 4 modified or untracked Calcifer state files + 1 untracked test + 1 untracked snapshot).

## 4. Old runtime launcher

The arena pipeline is currently **stopped** (engine.jsonl last write 2026-04-23). When restarted, the launcher is one of:

| Mechanism | Evidence |
| --- | --- |
| Crontab `watchdog.sh` (every 5 min) | `*/5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1` |
| `arena13_feedback.py` cron | `*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py` |
| Possible manual launcher (`tmux` / `nohup`) | none observed |

Currently running (NOT arena pipeline, but supporting services):

```
PID 2537810  cp_api/.venv/bin/python server.py            (Apr 24)
PID 3871446  uvicorn zangetsu.dashboard.run:app --port 9901 (Apr 23)
PID 3871449  uvicorn zangetsu.console.run:app --port 9900   (Apr 23)
```

## 5. Local-only state to preserve

| Path | Status |
| --- | --- |
| `.env*` | NOT present at top level (no scan hits) |
| `secret/` / `secrets/` | NOT present at top level |
| `zangetsu/logs/engine.jsonl` (38 MB) | KEEP (historic log) |
| `zangetsu/logs/engine.jsonl.1` (2.5 MB) | KEEP (rotated log) |
| `zangetsu/logs/dashboard.log` | KEEP |
| `zangetsu/logs/pipeline-v2.log` | KEEP |
| `zangetsu/data/funding/` | KEEP (price data) |
| `zangetsu/data/ohlcv/` | KEEP (price data) |
| `calcifer/maintenance.log`, `*.json` (state) | runtime state (technically dirty in git; NOT real code — produced by Calcifer at runtime) |

## 6. Rollback feasibility

| Question | Answer |
| --- | --- |
| Old SHA captured? | YES (`f5f62b2b`) |
| Old branch captured? | YES (`phase-7/p7-pr4b-a2-a3-arena-batch-metrics`) |
| Dirty diff captured? | YES — diff stat documented in `01` §4; can be re-derived via `git diff` until j13 cleans state |
| Untracked files captured? | YES (3 files) |
| Old launcher known? | PARTIAL — crontab entries known, but arena_pipeline / arena23_orchestrator process is NOT currently running (engine stopped Apr 23). Re-launch via crontab entries or manual systemd / nohup |
| Logs / data preserved? | YES (no deletion attempted) |
| Rollback path documented? | YES (this doc + `rollback_commands.sh`) |

**Rollback feasible:** YES. Even though the dirty state cannot be auto-restored once cleaned, the diff is preserved in git's working tree until j13 chooses to commit / stash / discard.

## 7. Rollback command draft

See `rollback_commands.sh` (this directory). Summary:

```bash
# IF replacement was performed and rollback is needed:
ssh j13@100.123.49.102 "
  cd /home/j13/j13-ops
  # Stop new runtime (whatever launcher was used during forward switch)
  # Reset to old SHA — REQUIRES j13 EXPLICIT AUTHORIZATION
  git checkout main
  git reset --hard f5f62b2b27a448dcf41c9ff6f6c847cb01c56c52
  # Re-apply dirty WIP if needed (re-derived from PR diff archive)
  # Restart old runtime via crontab watchdog or manual launcher
"
```

## 8. Limitations

1. The dirty WIP on Alaya does NOT match what the new main has. If j13 wants the dirty changes preserved, they must be committed to a feature branch BEFORE we can fast-forward — order forbids us from auto-committing.
2. The arena pipeline has been stopped since Apr 23. Re-launch behavior depends on cron + watchdog. After replacement, the new code will start the next time watchdog.sh fires (every 5 min).
3. Calcifer state files are NOT proper runtime state to preserve in git — they're regenerated. Recommend `.gitignore` entry in a future order.

## 9. Conclusion

Rollback path documented. Forward replacement BLOCKED on dirty state.
