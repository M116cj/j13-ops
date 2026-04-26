# 05 — Launcher Change Report

## 1. Selected Method

**Option A — tracked launcher wrapper at `zangetsu/arena13_feedback_env.sh` + crontab line update.**

## 2. Files Changed in This PR

| Path | Class | Diff |
| --- | --- | --- |
| `zangetsu/arena13_feedback_env.sh` | new tracked launcher script | +12 lines, mode 755 |
| `docs/recovery/20260424-mod-7/0-9v-feedback-loop-env-config/01..11_*.md` | evidence docs | new |

→ Source modules untouched (`arena13_feedback.py`, `settings.py`, `arena_pipeline.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py`, `arena_gates.py`, etc.).

## 3. Wrapper Contents (verbatim — NO secret value)

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
| Permission | `0755` (executable; same shell-script class as `watchdog.sh`) |
| Bash syntax check | PASS (`bash -n`) |
| Embedded secret value | NONE |
| Strategy args / flags | NONE (the original cron line had none either) |

## 4. Crontab Change

**Before** (verbatim, captured to `/tmp/0-9v-feedback-crontab-before.txt`):

```
*/5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1
```

**After** (verbatim, installed via `crontab /tmp/0-9v-feedback-crontab-after.txt`):

```
*/5 * * * * /home/j13/j13-ops/zangetsu/arena13_feedback_env.sh >> /tmp/zangetsu_arena13_feedback.log 2>&1
```

`diff` between before and after:

```
17c17
< */5 * * * * cd ~/j13-ops/zangetsu && .venv/bin/python services/arena13_feedback.py >> /tmp/zangetsu_a13fb.log 2>&1
---
> */5 * * * * /home/j13/j13-ops/zangetsu/arena13_feedback_env.sh >> /tmp/zangetsu_arena13_feedback.log 2>&1
```

| Field | Value |
| --- | --- |
| Crontab line count before | 25 |
| Crontab line count after | 25 |
| Lines changed | exactly 1 (verified by automated `changed=1` count check) |
| Schedule | `*/5 * * * *` UNCHANGED |
| Other cron lines | UNCHANGED |
| Crontab dump committed in this PR | NO (crontab is host-local config, not repo content) |

## 5. Strategy / Threshold Audit

| Item | Diff |
| --- | --- |
| `arena13_feedback.py` source | NOT modified |
| Other Python source | NOT modified |
| Strategy / threshold | NOT touched |
| `A2_MIN_TRADES` | UNCHANGED at 25 |
| Champion promotion / `deployable_count` | NOT touched |
| Execution / capital / risk | NOT touched |
| CANARY / production rollout | NOT started |

## 6. Secret Hygiene

| Check | Result |
| --- | --- |
| Wrapper contains literal secret value | NO |
| Evidence docs contain literal secret value | NO (only `PRESENT` / `MISSING` / `len=` status) |
| Crontab contains literal secret value | NO (only references the wrapper script) |
| `~/.env.global` committed | NO |

## 7. Rollback Plan

| Step | Command |
| --- | --- |
| Restore old crontab line | `crontab /tmp/0-9v-feedback-crontab-before.txt` |
| Remove wrapper | `git revert <PR>` (or `rm zangetsu/arena13_feedback_env.sh` locally) |
| Verify | `crontab -l \| grep arena13_feedback` |

The historical log `/tmp/zangetsu_a13fb.log` is left in place for audit purposes.

## 8. Phase F + G Verdict

→ **PASS.** Smallest-possible launcher repair with auditable diff (one new tracked file + one crontab line replacement). Strategy logic untouched.
