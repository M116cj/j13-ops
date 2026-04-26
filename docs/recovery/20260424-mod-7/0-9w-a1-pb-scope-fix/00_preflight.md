# 00 — Preflight

## 1. Timestamp / Host

| Field | Value |
| --- | --- |
| Timestamp (UTC) | 2026-04-26T13:11:28Z |
| Host | j13@100.123.49.102 (Tailscale) |
| Repo | /home/j13/j13-ops |
| SSH access | PASS |

## 2. Git State

| Field | Expected | Actual | Match |
| --- | --- | --- | --- |
| Branch | main | main | YES |
| HEAD | 1db7412fab4afcbb0ff9be2828513ed33325d400 | 1db7412fab4afcbb0ff9be2828513ed33325d400 | YES |
| origin/main | matches | matches | YES |
| Working tree | clean | clean | YES |

## 3. Crash Reproduction Evidence

`/tmp/zangetsu_a1_w0..w3.log` contain the exact UnboundLocalError documented in PR #36 every cron cycle. At the snapshot moment (13:11Z) workers w0/w1 were still in the cache-build phase of the 13:10 cron cycle (logs 9 KB), while workers w2/w3 contain the previous cycle's traceback (logs 19 KB):

```
File "/home/j13/j13-ops/zangetsu/services/arena_pipeline.py", line 1224, in main
    run_id=getattr(_pb, "run_id", "") or "",
                   ^^^
UnboundLocalError: cannot access local variable '_pb' where it is not associated with a value
```

Watchdog respawn cadence confirms the crash-respawn loop:

```
2026-04-26T13:00:01 WATCHDOG: arena_pipeline_w0 is DEAD (pid=587671), restarting...
2026-04-26T13:05:01 WATCHDOG: arena_pipeline_w0 is DEAD (pid=597869), restarting...
2026-04-26T13:10:01 WATCHDOG: arena_pipeline_w0 is DEAD (pid=608282), restarting...
```

## 4. Branch Protection (read-only)

```json
{
  "enforce_admins": true,
  "required_signatures": true,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
```

## 5. Phase 0 Verdict

PASS. Crash matches the PR #36 diagnosis exactly. No unrelated runtime blocker observed. Proceed to Phase 1 minimal patch.
