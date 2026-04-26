# 03 — Environment Source Plan

## 1. Selected Option

**Option A — `~/.env.global` preamble in `watchdog.sh`** (the order's preferred fast-repair path).

| Field | Value |
| --- | --- |
| Env file path | `/home/j13/.env.global` |
| Owner | `j13:j13` |
| Permission | `600` (already, will not loosen) |
| Tracked in repo | NO (matches `**/.env*` gitignore) |
| Committed | NO |
| Loaded from | `zangetsu/watchdog.sh` (a tracked, executable shell script) |
| Loading mechanism | `set -a; . "$HOME/.env.global"; set +a` (auto-export) |

## 2. Why Option A

- Existing `~/.env.global` is the j13-global secrets file documented in `_global/server_alaya.md`.
- Already has `600` perms and matches the order §10 expected pattern.
- Adding the preamble to `watchdog.sh` requires changing exactly one tracked shell script, which is governance-acceptable as a "safe env-loading preamble" (per order §11 / §18).
- Single-line preamble is auditable in controlled-diff (no strategy logic touched).

## 3. Why NOT Option B (systemd unit migration)

- Workers are currently cron-managed. Migrating to systemd-per-worker is a larger refactor than this order authorizes.
- HTTP APIs already have systemd EnvironmentFile patterns; mixing the two doesn't introduce new vulnerabilities, but the cron→systemd migration is a separate engineering effort and a separate order scope.
- Option A repairs immediately without changing the runtime topology.

## 4. Secret Source

The actual secret value will NOT be re-entered by j13. It is already present in `zangetsu/secret/.env` (authoritative source for the running HTTP APIs). Phase E will copy ONLY the `ZV5_DB_PASSWORD` line from that file to `~/.env.global` via redirection (no `echo`, no `cat`, no value printed in any output stream).

| Step | Command | Print risk |
| --- | --- | --- |
| Copy line | `grep '^ZV5_DB_PASSWORD=' /home/j13/j13-ops/zangetsu/secret/.env >> /home/j13/.env.global` | NO (output is redirected, never to terminal) |
| Verify count | `grep -c '^ZV5_DB_PASSWORD=' /home/j13/.env.global` | NO (only count printed) |
| Verify load | `bash -lc 'source ~/.env.global && python3 -c "import os; print(bool(os.getenv(\"ZV5_DB_PASSWORD\")))"'` | NO (only boolean printed) |

## 5. Watchdog Preamble (exact pattern, per order §11)

```bash
# Load local runtime secrets for cron-launched workers.
# File is local-only, not committed, and must not be printed.
if [ -f "$HOME/.env.global" ]; then
  set -a
  . "$HOME/.env.global"
  set +a
fi
```

Inserted directly after the shebang `#!/bin/bash` line. No other change to `watchdog.sh`.

## 6. Rollback Method

If the watchdog preamble causes any unintended issue:

| Step | Command |
| --- | --- |
| Revert watchdog.sh | `git restore zangetsu/watchdog.sh` (after stashing local change) — restores tracked content |
| Revert env file | `cp /home/j13/.env.global.bak /home/j13/.env.global && chmod 600 /home/j13/.env.global` (a `.bak` is created in Phase E before the append) |
| Cron schedule | `*/5` cron line is untouched, so reverting the script alone fully reverses Option A |

## 7. Phase D Verdict

→ **PASS.** Plan locked in. No new secret value required. Proceed to Phase E.
