# 02 — Replay / Backfill Report

## 1. Tool added

`zangetsu/tools/replay_sparse_canary_observation.py` — read-only helper
that scans heterogeneous telemetry sources, classifies each by record
shape, and reconstructs synthetic ``arena_batch_metrics`` events for
the observer.

CLI:

```
python -m zangetsu.tools.replay_sparse_canary_observation \
    --output-dir docs/recovery/20260424-mod-7/0-9s-canary-observe-complete \
    --run-id replay-1 \
    --attribution-verdict GREEN
```

When `--source` not supplied, defaults are scanned:

- `zangetsu/logs/engine.jsonl.1`
- `docs/recovery/20260424-mod-7/0-9j_canary_redacted_event_sample.jsonl`
- `docs/recovery/20260424-mod-7/0-9k_lifecycle_reconstruction_sample.jsonl`
- `docs/recovery/20260424-mod-7/p7_pr1_shadow_raw_event_sample.jsonl`

## 2. Sources scanned (live PR-time output)

See `replay_source_manifest.json` for full structured detail.

| Source | Type | Records | Usable? | Reason if excluded |
| --- | --- | --- | --- | --- |
| `zangetsu/logs/engine.jsonl.1` | orchestrator_log | 14213 | partially | pre-P7-PR4B (0 arena_batch_metrics events); only "A2 stats / A3 stats" log lines reconstructable |
| `0-9j_canary_redacted_event_sample.jsonl` | per_candidate_event | 6 | yes (1 synthetic batch / stage) | redacted: PnL / sharpe numerics stripped — not usable for baseline |
| `0-9k_lifecycle_reconstruction_sample.jsonl` | lifecycle_record | 7 | yes (1 synthetic A3 batch) | provenance_quality: PARTIAL |
| `p7_pr1_shadow_raw_event_sample.jsonl` | per_candidate_event | 10 | yes (1 synthetic batch / stage) | pre-CANARY shadow data (P7-PR1 era) |

## 3. Reconstruction results

```json
{
  "manifest_sources": 4,
  "rounds_observed": 5,
  "profiles_observed": 1,
  "synthetic_batches": 5
}
```

Profile attribution: all reconstructed batches carry
`generation_profile_id = "UNKNOWN_PROFILE"` because none of the
available sources predate PR-A 0-9P passport persistence. Per order §7:

> "If only one profile exists: profiles_observed = 1 is allowed only
> if documented. Profile-diversity criteria must be marked
> INSUFFICIENT_HISTORY or NOT_APPLICABLE, not PASS."

## 4. F-criteria firing on synthetic data

The runner's auto-evaluator fires F4 (UNKNOWN_REJECT > 0.05) and F6
(profile_diversity = 0) on the reconstructed data. **These triggers
are artifacts of synthetic-data limitations**, not real CANARY
failures:

- F4 fires because reject reasons in `0-9j` / `0-9k` / shadow fixtures
  map heuristically to `UNKNOWN_REJECT` when they don't match the
  taxonomy used at fixture-emission time.
- F6 fires because the fixtures predate 0-9P attribution and all
  reconstructed batches use `UNKNOWN_PROFILE`, yielding
  `profile_diversity_score = 0`.

Per order §17 acceptance criteria:

> "Do not use GREEN or YELLOW unless: rounds_observed >= 20, real
> records exist, F criteria do not fail, runtime safety passes."

`rounds_observed = 5 < 20` AND records are fixture-grade rather than
real post-CANARY-activation telemetry → cannot promote to GREEN/YELLOW.

The F triggers ALSO make `FAILED_OBSERVATION` an inappropriate verdict
because they reflect synthetic-data limitations rather than real
CANARY failures (order §10: "FAILED_OBSERVATION" implies real failure).

## 5. Replay verdict

**Replay alone insufficient.** Sources reachable from the local
working tree do not contain real post-CANARY-activation
`arena_batch_metrics` events at the volume / quality required by
order §7.

| Requirement | Status |
| --- | --- |
| `rounds_observed >= 20` | FAIL (5 reconstructed) |
| A1/A2/A3 metrics non-empty | partial (A1 absent — fixtures are A2/A3 only) |
| baseline comparison possible | FAIL (no usable baseline source) |
| S1-S14 evaluable | partial (S6/S8 misleading on synthetic data) |
| F1-F9 evaluable | partial (F4/F6 misleading on synthetic data) |

## 6. Continuation

Live observation phase (Phase B, see `03_live_observation_report.md`)
runs the runner against an empty live source three times. Even with
both phases combined, real post-CANARY data is required.

## 7. Source manifest

Detailed `replay_source_manifest.json` snapshot pinned alongside this
doc. Includes per-source line count, time bounds, coverage flags, and
exclusion reasons.

## 8. Summary

- **Sources scanned**: 4
- **Sources usable for partial replay**: 4 (all per-candidate or log
  reconstruction)
- **Sources usable for baseline**: 0
- **Synthetic batches built**: 5
- **Rounds recovered**: 5
- **Profiles recovered**: 1 (UNKNOWN_PROFILE only)
- **Replay verdict**: insufficient → continue to Phase B
