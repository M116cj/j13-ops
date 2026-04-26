# 03 — Live Observation Report

## 1. Tool

`zangetsu/tools/run_sparse_canary_observation.py` (shipped by
0-9S-OBSERVE-FAST PR #26).

## 2. Invocations during this PR

```
python -m zangetsu.tools.run_sparse_canary_observation \
  --output-dir docs/recovery/20260424-mod-7/0-9s-canary-observe-complete \
  --run-id live-1 --attribution-verdict GREEN
python -m zangetsu.tools.run_sparse_canary_observation \
  --output-dir docs/recovery/20260424-mod-7/0-9s-canary-observe-complete \
  --run-id live-2 --attribution-verdict GREEN
python -m zangetsu.tools.run_sparse_canary_observation \
  --output-dir docs/recovery/20260424-mod-7/0-9s-canary-observe-complete \
  --run-id live-3 --attribution-verdict GREEN
```

Each invocation uses no `--batch-events` / `--plans` argument because
no live JSONL feed is available during a single CI execution — the
production telemetry stream lives on Alaya behind a long-running A1/A2/A3
pipeline that does not run on the local Mac.

## 3. Per-invocation output

Each live run produced a record with:

```
rounds_observed = 0
profiles_observed = 0
observation_window_complete = False
status = OBSERVING_NOT_COMPLETE
rollback_required = False
```

The runner's zero-round status guard (added in 0-9S-OBSERVE-FAST)
correctly suppressed F-criteria evaluation during empty-input runs to
avoid false F6 (no profiles → diversity=0) triggers.

## 4. Total observation records collected (combined replay + live)

`docs/recovery/20260424-mod-7/0-9s-canary-observe-complete/sparse_canary_observations.jsonl`:

- 1 record from replay phase (`replay-1`)
- 3 records from live phase (`live-1`, `live-2`, `live-3`)
- **Total: 4 observation records**

## 5. Limitation

To meet order §7's "rounds_observed >= 20" requirement under live
observation alone:

- Run runner periodically against actual production
  `arena_batch_metrics.jsonl` stream emitted by P7-PR4B-instrumented
  arena23_orchestrator after PR-A 0-9P passport persistence has been
  observable in production for ≥ 1 day.
- Single-CI live execution cannot substitute for multi-day
  observation. This PR explicitly does not synthesize fake rounds.

## 6. Conclusion

Live observation phase confirmed:

1. The runner is healthy and produces well-formed records under empty
   input.
2. The status machine correctly returns OBSERVING_NOT_COMPLETE rather
   than FAILED_OBSERVATION at zero real rounds.
3. Real continuous observation requires a separate continuation order
   that runs against a real telemetry feed for ≥ 24h or ≥ 20 batch
   events.
