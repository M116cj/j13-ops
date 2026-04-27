# 10 — A1 Pipeline Re-Verification

## Verdict
**A1_REVERIFY_BLOCKED_BY_COLD_BOOT_GAP**

## Process State

```
$ ps aux | grep -E 'arena_pipeline|arena23|arena45' | grep -v grep
[empty]
```

→ **0 arena workers alive.**

## Root Cause: Cold-Boot Gap (documented in PR #43)

Alaya was rebooted ~04:01Z. The watchdog cron (`*/5`) only checks lock files in `/tmp/zangetsu/*.lock`. After reboot:
- `/tmp` is tmpfs and was wiped
- Only persistent lock files (`arena13_feedback.lock`, `calcifer_supervisor.lock` — written every cron tick) re-appeared
- `arena_pipeline_w0/w1/w2/w3.lock`, `arena23_orchestrator.lock`, `arena45_orchestrator.lock` are GONE
- Watchdog detection logic: "for each existing lock file, check if PID is alive; if not, restart" — but if NO lock file exists, watchdog doesn't know there SHOULD be a worker

→ **Watchdog cannot cold-boot from scratch.** Manual intervention or a separate `init` script is needed to first-launch the workers, after which watchdog can keep them alive.

## DB Live Write State

```sql
SELECT count(*) FROM champion_pipeline;          -- VIEW over fresh: 0
SELECT count(*) FROM champion_pipeline_staging;  -- 0
SELECT count(*) FROM champion_pipeline_fresh;    -- 0
```

→ DB schema correct; tables empty (consistent with no workers running).

## Engine.jsonl Latest Activity

```
$ tail -n 10 /home/j13/j13-ops/zangetsu/logs/engine.jsonl
[empty/old data only — last write was pre-reboot at 04:05Z, before this migration ran]
```

## A1 Schema Compatibility (deferred verification)

**A1 cannot be tested against the new schema until the cold-boot gap is resolved.**

The schema IS the v0.7.1 contract that the code references. Code paths in `arena_pipeline.py:329` (`INSERT INTO engine_telemetry`), line 685, 821 (`FROM champion_pipeline_fresh`), line 1140 (`INSERT INTO champion_pipeline_staging`), line 1180 (`SELECT admission_validator($1)`) now have valid targets. So the migration unblocks A1's previously-dormant write path.

## Out-of-Scope per Order

The order's Phase J says:
> "If workers are not running because of known cold-boot lockfile gap, do not patch here. Document: `A1_REVERIFY_BLOCKED_BY_COLD_BOOT_GAP`"

I am following this guidance.

## Next Order to Resolve

The order's "Expected Next Order After Success" specifies:
> `TEAM ORDER 0-9X-POST-DB-COLD-BOOT-RECOVERY`
> Purpose: Fix watchdog cold-boot gap after reboot when /tmp lockfiles vanish.

→ A1 schema compatibility verification is deferred to that order.
