# 00 — STATE LOCK

**TEAM ORDER**: 0-9Y-TF3-SIGNAL-AGGREGATION-SHADOW-ACTIVATION
**Date**: 2026-04-28
**Phase**: 0 / 8

## Git
- Branch: `main`
- HEAD: `3decabd4dc9cc821e25dab7544a2ebe4ed7d0f82`
- origin/main: `3decabd4dc9cc821e25dab7544a2ebe4ed7d0f82` ✅ in-sync
- Last signed commit: `feat(zangetsu/tf2): prototype signal aggregation profiles` (ED25519, M116cj)

## Working tree (zangetsu only)
```
 M zangetsu/logs/engine.jsonl.1   ← runtime log (NOT staged)
```
✅ No source changes.

## TF2 helper presence
`zangetsu/services/signal_aggregation.py` importable via venv. `apply_signal_aggregation()` callable; sentinel test verified:
```
profiles = ['BASELINE','CONSENSUS_2_OF_3','HYBRID_TOPK_STRENGTH','OFF','STRENGTH_FILTER','TOP_K_PER_BAR']
OFF entered=2 skipped=0  ← bit-for-bit pass-through verified
```

## Runtime processes
- 4 × `services/arena_pipeline.py` (PIDs 1914251, 1939010, 1944685, 2030138) ✅
- `services/arena23_orchestrator.py` (1365067) ✅
- `services/arena45_orchestrator.py` (1365092) ✅
- `calcifer/supervisor.py` (1365473) ✅

`engine.jsonl` tail timestamp: 2026-04-28T11:55:03Z — A1 actively producing batches.

## Live batch rate
- 3353 arena_batch_metrics events spanning 2026-04-28T03:59:45Z → 11:54:29Z (7.91 hr)
- **Rate: 7.06 batches/min ≈ 424 batches/hour**
- Phase 4 collection target ≥100 batches → ~14 min window after restart

## DB
- `champion_pipeline_staging`: **184**
- DB healthy

## Telemetry sanity
- UNKNOWN_REJECT total over recent 300 batches: 0 ✅
- COUNTER_INCONSISTENCY total: 0 ✅
- Conservation residual: 0 ✅

## Calcifer deploy block
`/tmp/calcifer_deploy_block.json` — `status: UNKNOWN_BLOCKED`, reason `cold_start_no_live_champion_ever` (predicate `0-9Y-B3-NULL-SAFE`). Cold-start, not regression. TF3 is shadow-only, NOT a deployable advancement → not gated by §17.3.

## Baseline aggregation invocation check
Searched `arena_pipeline.py` for any existing `apply_signal_aggregation` calls:
```
grep -n apply_signal_aggregation zangetsu/services/arena_pipeline.py
```
**No matches.** TF2 helper exists but is NOT invoked from baseline path. ✅ Baseline behavior is identical to pre-TF2 — confirmed unintended-activation-free.

## Verdict
**STATE_LOCK_PASS** — proceed to Phase 1.

No STOP triggered:
- Repo not source-dirty ✅
- HEAD == origin/main ✅
- A1 runtime alive (4 workers + 2 orchestrators) ✅
- TF2 helper present and callable ✅
- Baseline path does NOT invoke aggregation ✅
- Telemetry clean ✅
