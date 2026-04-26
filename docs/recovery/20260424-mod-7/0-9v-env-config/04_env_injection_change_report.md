# 04 — Environment Injection Change Report

## 1. `~/.env.global` State

| Field | Pre | Post |
| --- | --- | --- |
| Path | `/home/j13/.env.global` | unchanged |
| Owner | `j13:j13` | unchanged |
| Permission | `600` | `600` (re-asserted via `chmod 600`) |
| Tracked | NO (matches `**/.env*` gitignore) | NO |
| Backup | n/a | `/home/j13/.env.global.bak.0-9v-env-config` (created `cp -a` before append) |
| Keys present | `BINANCE_API_KEY`, `BINANCE_SECRET_KEY` | `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`, `ZV5_DB_PASSWORD` |
| `ZV5_DB_PASSWORD` count | 0 | 1 |
| Secret value printed | NO | NO |
| Secret value committed | NO | NO |
| Source of new line | `grep '^ZV5_DB_PASSWORD=' /home/j13/j13-ops/zangetsu/secret/.env >> /home/j13/.env.global` (silent redirect; same value already in production HTTP API EnvironmentFile, no new secret introduced) |

### Append command (verbatim, no value printed)

```bash
cp -a /home/j13/.env.global /home/j13/.env.global.bak.0-9v-env-config
grep '^ZV5_DB_PASSWORD=' /home/j13/j13-ops/zangetsu/secret/.env >> /home/j13/.env.global
chmod 600 /home/j13/.env.global
```

### Verification (no value printed)

```
$ awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/ {split($0, a, "="); print "  " a[1]}' /home/j13/.env.global
  BINANCE_API_KEY
  BINANCE_SECRET_KEY
  ZV5_DB_PASSWORD

$ stat -c '%a %U:%G %n' /home/j13/.env.global
600 j13:j13 /home/j13/.env.global

$ bash -c 'set -a; . /home/j13/.env.global; set +a; python3 << EOF
import os
v = os.getenv("ZV5_DB_PASSWORD")
print("ZV5_DB_PASSWORD=" + ("PRESENT" if v else "MISSING"))
print("len=" + str(len(v) if v else 0))
EOF'
ZV5_DB_PASSWORD=PRESENT
len=32
```

→ Variable loads correctly. Length printed as a length scalar only; no character of the value escapes any output stream.

## 2. `watchdog.sh` Patch

| Field | Value |
| --- | --- |
| Path | `/home/j13/j13-ops/zangetsu/watchdog.sh` |
| Tracked in repo | YES |
| Backup | `/home/j13/j13-ops/zangetsu/watchdog.sh.bak.0-9v-env-config` (local `.bak`, NOT staged for commit) |
| Lines changed | +8 / -0 |
| Strategy logic touched | NO |
| Syntax check | `bash -n` PASS |

### Inserted preamble (verbatim, immediately after `#!/bin/bash`)

```bash
# Load local runtime secrets for cron-launched workers.
# File is local-only, not committed, and must not be printed.
if [ -f "$HOME/.env.global" ]; then
  set -a
  . "$HOME/.env.global"
  set +a
fi

```

### Diff vs. HEAD

```
diff --git a/zangetsu/watchdog.sh b/zangetsu/watchdog.sh
index 60b75557..35855cc2 100755
--- a/zangetsu/watchdog.sh
+++ b/zangetsu/watchdog.sh
@@ -1,4 +1,12 @@
 #!/bin/bash
+# Load local runtime secrets for cron-launched workers.
+# File is local-only, not committed, and must not be printed.
+if [ -f "$HOME/.env.global" ]; then
+  set -a
+  . "$HOME/.env.global"
+  set +a
+fi
+
 # Watchdog — checks each service independently, restarts only the dead one
 # Install: crontab -e → */5 * * * * ~/j13-ops/zangetsu/watchdog.sh >> /tmp/zangetsu_watchdog.log 2>&1
 #
```

→ Diff is exactly the env-loading preamble + one blank line. No other watchdog logic, no strategy code, no thresholds touched.

## 3. Phase G Validation

```
$ bash -c 'set -a; . /home/j13/.env.global; set +a; python3 -c "import os; print(\"watchdog_env_ZV5_DB_PASSWORD=\" + (\"PRESENT\" if os.getenv(\"ZV5_DB_PASSWORD\") else \"MISSING\"))"'
watchdog_env_ZV5_DB_PASSWORD=PRESENT
```

→ A subshell that follows the watchdog preamble pattern can read the variable. Phase G PASS.

## 4. Hard-Ban Compliance

| Forbidden action | Performed? |
| --- | --- |
| Print `ZV5_DB_PASSWORD` value | NO |
| Print full environment | NO |
| Commit secrets | NO (gitignored backup files; `~/.env.global` is outside repo) |
| Commit `.env*` | NO |
| Write secret into docs | NO (this doc and all evidence docs use only `PRESENT` / `len=32` / `<REDACTED>` placeholders) |
| Paste secret into logs | NO |
| Change DB password | NO (value is the same string already in `zangetsu/secret/.env` for HTTP APIs) |
| Hardcode in Python source | NO |
| Hardcode in committed shell scripts | NO |

→ All hard bans honored.

## 5. Phase E + F + G Verdict

→ **PASS.** Env injection prepared, watchdog patched, subshell validation green. Proceed to Phase H.
