# 02 — RUNTIME COMMANDS

**TEAM ORDER**: 0-9Y-HE4-HORIZON-SHADOW-RUN
**Date**: 2026-04-29
**Phase**: 2 / 8

## Execution timestamp
- Stop initiated: 2026-04-29T08:13:07Z
- Stop completed (4 arena_pipeline workers SIGTERM + force-kill, A23/A45/calcifer SIGTERM): ~08:13:30Z
- Restart completed (4 new arena_pipeline workers + A23 + A45): 2026-04-29T08:13:40Z (PIDs 3539270/93/385/409, A23 3539520, A45 3539545)
- First post-restart batch: 2026-04-29T08:14:xx (engine.jsonl rotation, then live emission)
- Verification at +60s: 2 batches with horizon distribution = {240: 1, 360: 1}, both with `horizon_metrics` ✅

## Commands executed
```bash
# 1) Snapshot pre-restart batch state
date -u +%Y-%m-%dT%H:%M:%SZ
# → 2026-04-29T08:13:07Z

# 2) Stop all workers
cd /home/j13/j13-ops/zangetsu
./zangetsu_ctl.sh stop
# → Output: 4 arena_pipeline + arena23 + arena45 + calcifer SIGTERM, then force kill stragglers, "All stopped."

# 3) Activate horizon env + restart
export ARENA_HORIZON_MODE=SIMPLE_CYCLE
export ACTIVE_A1_HORIZONS=180,240,360
./zangetsu_ctl.sh start
# → Output: 6 services started successfully (4 A1 workers + A23 + A45)

# 4) Verify env propagation across all 4 arena_pipeline workers
sleep 8
for pid in $(pgrep -f "arena_pipeline.py"); do
  echo "PID=$pid:"
  cat /proc/$pid/environ | tr '\0' '\n' | grep -E 'ARENA_HORIZON|ACTIVE_A1_HORIZONS'
done
```

## Verification — env on workers
All 4 arena_pipeline workers have:
```
ACTIVE_A1_HORIZONS=180,240,360
ARENA_HORIZON_MODE=SIMPLE_CYCLE
```
✅

## Verification — horizon cycling appearing in batch metrics
After 60-second wait:
- `total_batches = 2`
- `horizon_distribution = {240: 1, 360: 1}` ✅ (only 2 batches; will continue to cycle through 180/240/360)
- `with_horizon_metrics = 2 / 2` ✅ — HE3 code now active (was 0/30 pre-restart)

The horizon and horizon_metrics fields are both flowing. Phase 3 collection window starts now.

## STOP-conditions check (Phase 2 spec)
| STOP cause | Status |
|---|---|
| Workers fail to start | ❌ no — 6/6 services started |
| Horizon not appearing | ❌ no — verified via batch parse |
| Errors in logs | ❌ no observable errors in startup |

✅ **No STOP triggered.**

## Verdict
**PHASE_2_COMPLETE** — workers restarted, env propagated, horizon cycling + HE3 telemetry both confirmed live.

## Next
Phase 3 — collect ≥100 batches/horizon (target ~50 minutes).
