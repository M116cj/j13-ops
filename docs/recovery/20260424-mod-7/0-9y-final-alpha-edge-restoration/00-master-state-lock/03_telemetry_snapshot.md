# 03 — Telemetry Snapshot

**Order:** TEAM ORDER 0-9Y-FINAL-0-MASTER-STATE-LOCK
**Phase:** 0 / sub-doc 03
**Captured (UTC):** 2026-04-28T02:55Z

## Latest batch (live tail of `engine.jsonl`)

```json
{
  "ts": "2026-04-28T02:54:56",
  "msg": {
    "event_type": "arena_batch_metrics",
    "arena_stage": "A1",
    "entered_count": 10,
    "passed_count": 0,
    "rejected_count": 10,
    "skipped_count": 0,
    "reject_reason_distribution": {"COST_NEGATIVE": 10},
    "aggregate_metrics": {
      "schema_version": "0-9y-b1-v1",
      "symbol": "...",
      "regime": "...",
      "lane": "...",
      ...22 fields total per B1 spec
    },
    ...
  }
}
```

## Telemetry invariant snapshot

| Invariant | Live status |
|---|---|
| `entered = passed + rejected + skipped` | **HOLDS** (10 = 0 + 10 + 0) |
| `COUNTER_INCONSISTENCY` per batch | **0** (PR #50 chain-fix verified live) |
| `UNKNOWN_REJECT` per batch | **0** (PR #49 taxonomy fix verified live) |
| `aggregate_metrics` field present | **YES** (PR #55 B1 LIVE; 22 keys per batch) |
| `aggregate_metrics_availability` flags exposed | **YES** (21 flags) |
| `engine_telemetry` table writes | **0** (deprecated per PR #56 B2; canonical = JSONL) |
| Calcifer `/tmp/calcifer_deploy_block.json` schema | **NULL-safe** (PR #57 B3 verified live) |

## Carry-forward economic baseline (from 0-9Y-C)

From `c-economic-edge-decomposition/08_final_report.md` (n=106 post-restart batches):

| Metric | Median | Note |
|---|---|---|
| `train_gross_pnl_median` | +2.46 bps | always positive (0/106 ≤ 0) |
| `train_gross_minus_net_median` (cost charged) | +3.60 bps | exceeds gross |
| `train_net_pnl_median` | -1.33 bps | structurally negative |
| `cost / gross` ratio | 1.54× | 54% over breakeven |
| `train_win_rate_median` | 0.32 | max 0.494 (zero batches reach 50%) |
| `signal_density_per_bar` | 0.00702 | ample (~989 trades/batch) |

Reject distribution at FINAL-0:
- 100 % `COST_NEGATIVE` per batch
- 0 % CI / UR (chain-fix proven live)

## Per-PR contribution proof

| PR | Field touched | Verified live |
|---|---|---|
| #45 / #46 | watchdog cold-boot + octal fix | 6/6 lockfiles after operator restart; w3 watchdog-respawn confirms cold-boot path |
| #48 | A1 reject distribution diagnosis | docs-only |
| #49 | RAW_TO_REASON taxonomy hotfix | UR = 0 in latest batch |
| #50 | per-round delta accounting | CI = 0 in latest batch + conservation residual = 0 |
| #54 | 0-9Y-A baseline state lock | docs-only |
| #55 | B1 aggregate_metrics | schema_version `0-9y-b1-v1` present in latest batch |
| #56 | B2 engine_telemetry deprecation | engine_telemetry count = 0; JSONL is canonical |
| #57 | B3 Calcifer NULL-safe deploy_block | `/tmp/calcifer_deploy_block.json` writes successfully |
| #58 | 0-9Y-C decomposition | docs-only |

All chain-fix is verified live and intact at FINAL-0.

## Conclusion

Telemetry surface is **mathematically consistent, B1-rich, and observable**. Conservation invariant holds 1/1 at the snapshot moment (and 106/106 over the most recent post-restart sample documented in 0-9Y-C). No telemetry regression at FINAL-0 entry.
