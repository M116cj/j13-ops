# 04 — Feedback Env Plan

## 1. Selected Method

**Option A — tracked launcher wrapper at `zangetsu/arena13_feedback_env.sh` + crontab line update**.

This mirrors the approach used by `watchdog.sh` (PR #31) and keeps env loading fully out of Python source.

## 2. Why Option A

- **Auditable**: the wrapper is a 10-line tracked shell script with the same env-loading preamble already governance-approved in PR #31.
- **Symmetric**: produces a single repeatable pattern across both cron paths (watchdog + feedback).
- **Reversible**: pure-shell launcher; reverting is `git revert <PR>` + restore the old crontab line.
- **No Python source change**: `arena13_feedback.py` itself is untouched.
- **No strategy logic, threshold, or Arena-pass-fail change**.

Option B (modify cron command directly to inline the env source) was considered but rejected because:

- A multi-line `bash -lc 'source ...; cd ...; <cmd>'` cron line is harder to read and audit than a tracked wrapper.
- Crontab itself is a non-versioned, host-local config — putting the env-loading logic in a tracked script makes the change visible in `git log`.

## 3. Original Cron Command (verbatim)

```
*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1
```

| Field | Value |
| --- | --- |
| Schedule | `*/5 * * * *` |
| cwd | `~/j13-ops/zangetsu` |
| Python | `.venv/bin/python` (relative) |
| Script | `services/arena13_feedback.py` (relative) |
| Log | `/tmp/zangetsu_a13fb.log` |

## 4. New Cron Command (planned)

```
*/5 * * * * /home/j13/j13-ops/zangetsu/arena13_feedback_env.sh >> /tmp/zangetsu_arena13_feedback.log 2>&1
```

| Field | Value |
| --- | --- |
| Schedule | `*/5 * * * *` (UNCHANGED) |
| Launcher | `/home/j13/j13-ops/zangetsu/arena13_feedback_env.sh` (NEW, tracked) |
| Log | `/tmp/zangetsu_arena13_feedback.log` (NEW; old log `/tmp/zangetsu_a13fb.log` left in place as historical evidence) |

## 5. Wrapper Contents (planned, verbatim — NO secret value)

```bash
#!/usr/bin/env bash
set -euo pipefail
# Load local runtime secrets for cron-launched arena13 feedback loop.
# This file must not print secrets.
if [ -f "$HOME/.env.global" ]; then
  set -a
  . "$HOME/.env.global"
  set +a
fi
cd /home/j13/j13-ops/zangetsu
exec /home/j13/j13-ops/zangetsu/.venv/bin/python /home/j13/j13-ops/zangetsu/services/arena13_feedback.py
```

| Property | Value |
| --- | --- |
| Tracked path | `zangetsu/arena13_feedback_env.sh` |
| Permission | `+x` (executable) |
| Same Python interpreter as original | YES (`.venv/bin/python`, absolute form) |
| Same script as original | YES (`services/arena13_feedback.py`, absolute form) |
| Same effective cwd | YES (`/home/j13/j13-ops/zangetsu` = `~/j13-ops/zangetsu`) |
| Adds env-loading preamble | YES |
| Strategy args / flags | NONE (script takes no CLI args; `exec ... .venv/bin/python services/arena13_feedback.py` is identical in semantics) |
| Embedded secret | NONE |

## 6. Rollback Method

| Step | Command |
| --- | --- |
| Restore old cron line | `crontab /tmp/0-9v-feedback-crontab-before.txt` (backup taken before edit) |
| Remove wrapper | `rm /home/j13/j13-ops/zangetsu/arena13_feedback_env.sh` (or `git revert <PR>`) |
| Verify | `crontab -l \| grep arena13_feedback` |

Old log `/tmp/zangetsu_a13fb.log` remains on disk for audit purposes (no log file is deleted by this order).

## 7. Strategy Args / Threshold / Forbidden-Change Audit

| Item | Diff |
| --- | --- |
| `arena13_feedback.py` source | NOT modified |
| Other Python source | NOT modified |
| Strategy parameters / thresholds / Arena pass/fail | NOT touched |
| `A2_MIN_TRADES` | UNCHANGED at 25 |
| Champion promotion / `deployable_count` semantics | NOT touched |
| Execution / capital / risk | NOT touched |
| CANARY / production rollout | NOT started |
| New consumer wiring into runtime | NONE |

## 8. Phase E Verdict

→ **PASS.** Plan locked in. Smallest-possible launcher repair via tracked wrapper.
