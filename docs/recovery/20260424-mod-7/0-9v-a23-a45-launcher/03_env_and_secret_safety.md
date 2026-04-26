# 03 — Environment and Secret Safety

## 1. `~/.env.global`

| Field | Value |
| --- | --- |
| Path | `/home/j13/.env.global` |
| Mode | `600 j13:j13` |
| Tracked | NO |
| Committed | NO |

## 2. `ZV5_DB_PASSWORD` Reachability via Watchdog Preamble

The watchdog preamble (added in PR #31) sources `~/.env.global` with `set -a; . "$HOME/.env.global"; set +a`, which auto-exports every `KEY=VALUE` in the file. Spawned children — including any future A23 / A45 process — will inherit these as ordinary environment variables.

```
$ bash -c 'set -a; . /home/j13/.env.global; set +a; python3 << EOF
import os
v = os.getenv("ZV5_DB_PASSWORD")
print("ZV5_DB_PASSWORD=" + ("PRESENT" if v else "MISSING"))
EOF'
ZV5_DB_PASSWORD=PRESENT
```

→ The variable is reachable in any subshell that follows the watchdog preamble. The same env is therefore available to the orchestrators when watchdog spawns them.

## 3. Watchdog Preamble (verbatim, top 12 lines)

```bash
#!/bin/bash
# Load local runtime secrets for cron-launched workers.
# File is local-only, not committed, and must not be printed.
if [ -f "$HOME/.env.global" ]; then
  set -a
  . "$HOME/.env.global"
  set +a
fi

# Watchdog — checks each service independently, restarts only the dead one
# Install: crontab -e → */5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1
```

→ Confirmed in main at SHA `f50e8cba` (PR #31).

## 4. Secret Hygiene Checklist

| Item | Status |
| --- | --- |
| `~/.env.global` exists | YES |
| Permission `600` | YES (owner `j13:j13`) |
| `ZV5_DB_PASSWORD` present | YES |
| Secret value printed in this run | NO (only `PRESENT` status string) |
| Secret value committed | NO |
| Secret value in this evidence doc | NO |
| Secret value in any tracked file | NO (only `*.env.example` template files are tracked) |

## 5. Launcher Env Inheritance Pre-Validation

`A23` / `A45` orchestrators import `zangetsu.config.settings`, which reads `os.environ["ZV5_DB_PASSWORD"]` at module load time (line 99). Because the watchdog preamble has exported the variable into the watchdog process, every child it spawns via `eval "$cmd > $log 2>&1 &"` inherits the same env table. A23/A45 will therefore pass the same import-time check that A1 now passes.

| Component | Env-inheritance status |
| --- | --- |
| A1 (`arena_pipeline_w*`) | VERIFIED at PR #31 (workers run for full cycle without `KeyError`) |
| A23 (`arena23_orchestrator`) | EXPECTED PASS (same parent shell env) |
| A45 (`arena45_orchestrator`) | EXPECTED PASS (same parent shell env) |

## 6. Phase C Verdict

→ **PASS.** Env reachable, secret never printed/committed/leaked. No `BLOCKED_SECRET_MISSING`, `BLOCKED_SECRET_LEAK`, or `BLOCKED_ENV_INHERITANCE`.
