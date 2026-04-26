# 04 — Aggregate Metrics

## 1. Source mix

| Phase | Records | Status | Notes |
| --- | --- | --- | --- |
| Replay (Phase A) | 5 synthetic batches | reconstructed from heterogeneous fixtures | profile_id = UNKNOWN_PROFILE |
| Live (Phase B) | 3 zero-round records | empty input | runner status = OBSERVING_NOT_COMPLETE per record |
| **Combined** | 4 records in JSONL + 1 latest aggregate | mixed | insufficient for verdict |

## 2. Latest aggregate snapshot (live `live-3`)

```json
{
  "runner_version": "0-9S-OBSERVE-FAST",
  "run_id": "live-3",
  "observation_complete": false,
  "rounds_observed": 0,
  "profiles_observed": 0,
  "unknown_reject_rate": 0.0,
  "signal_too_sparse_rate": 0.0,
  "a1_pass_rate": 0.0,
  "a2_pass_rate": 0.0,
  "a3_pass_rate": 0.0,
  "oos_fail_rate": 0.0,
  "deployable_count": 0,
  "deployable_density": 0.0,
  "composite_score": 0.0,
  "baseline_composite_score": 0.0,
  "composite_delta": 0.0,
  "profile_diversity_score": 0.0,
  "profile_collapse_detected": false,
  "consumer_plan_stability": 0.0,
  "rollback_required": false,
  "status": "OBSERVING_NOT_COMPLETE"
}
```

## 3. Replay-only aggregate (preserved)

The replay-only aggregate (before live runs overwrote it) had:

```
rounds_observed = 5
profiles_observed = 1 (UNKNOWN_PROFILE)
a3_pass_rate = 0.231 (synthetic, lifecycle reconstruction)
oos_fail_rate = 0.5 (synthetic, fixture mapping)
deployable_count = 3 (synthetic, lifecycle DEPLOYABLE finals)
deployable_density = 1.0 (synthetic — 3 deploy / 3 a3-pass)
composite_score = 0.292
status = FAILED_OBSERVATION (artifacts of synthetic data; see §02 §4)
```

The replay aggregate is preserved in
`replay_synthetic_batch_metrics.jsonl` for re-evaluation under future
orders, but is not the canonical observation aggregate because:

- 5 < 20 rounds (order §7 minimum)
- profile_id all UNKNOWN_PROFILE (order §7: "profiles_observed = 1 is
  allowed only if documented")
- F4/F6 fired on fixture-data limitations, not real CANARY signal

## 4. Required aggregate fields per order §9

| Field | Value | Notes |
| --- | --- | --- |
| `observation_start` | live UTC at PR-time | `live-3` invocation |
| `observation_end` | live UTC at PR-time | same |
| `observation_complete` | False | rounds < 20 |
| `observation_source_mix` | replay (5) + live (0) = 5 reconstructed; canonical = 0 real | mixed |
| `rounds_observed` | 5 (synthetic) / 0 (real post-CANARY) | order requires "real" |
| `profiles_observed` | 1 (UNKNOWN_PROFILE) | order §7: documented |
| `unknown_reject_rate` | 0.0 (live) / 0.6 (replay synthetic) | not authoritative |
| `signal_too_sparse_rate` | 0.0 | INSUFFICIENT_HISTORY proxy |
| `a1_pass_rate` | 0.0 | A1 absent in fixtures |
| `a2_pass_rate` | 0.0 | minimal in fixtures |
| `a3_pass_rate` | 0.0 (live) / 0.231 (replay synthetic) | not authoritative |
| `oos_fail_rate` | 0.0 (live) / 0.5 (replay synthetic) | fixture artifact |
| `deployable_count` | 0 (live) / 3 (replay synthetic) | fixture artifact |
| `deployable_density` | 0.0 (live) / 1.0 (replay synthetic) | fixture artifact |
| `composite_score` | 0.0 (live) / 0.292 (replay synthetic) | INSUFFICIENT_BASELINE |
| `baseline_composite_score` | null (INSUFFICIENT_BASELINE) | per `sparse_canary_baseline.json` |
| `composite_delta` | null | INSUFFICIENT_BASELINE |
| `profile_diversity_score` | 0.0 | UNKNOWN_PROFILE only |
| `profile_collapse_detected` | False (suppressed at zero real rounds) | order §7 |
| `consumer_plan_stability` | 0.0 | no consumer plans available locally |
| `rollback_required` | False | no real failure observed |
| `production_allowed` | False | always |

## 5. Authoritative interpretation

The combined replay + live evidence supports the **OBSERVING_NOT_COMPLETE**
verdict per order §12:

> "Use if: rounds_observed < 20 OR baseline insufficient prevents
> meaningful verdict OR telemetry insufficient OR observation could
> not run enough rounds."

All four conditions hold:

- rounds_observed (real) < 20 ✓
- baseline INSUFFICIENT_BASELINE per `sparse_canary_baseline.json` ✓
- telemetry insufficient (no post-CANARY arena_batch_metrics) ✓
- observation could not run enough rounds in single CI execution ✓
