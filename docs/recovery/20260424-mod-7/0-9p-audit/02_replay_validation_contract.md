# 02 — Replay Validation Contract

## 1. Purpose

Re-run `resolve_attribution_chain` over a corpus of passports (live
or fixture) to tally exactly which precedence level was hit, and
optionally check whether resolved ids match an expected value.

## 2. Inputs

`replay_validate(passports, *, expected_profile_id=None,
orchestrator_profile_id=None, orchestrator_profile_fingerprint=None)`:

- `passports`: iterable of dict-like passport snapshots; non-dict
  entries are skipped silently.
- `expected_profile_id`: optional sanity-check value; if supplied,
  count how many resolved ids match it (`expected_match_rate`).
- `orchestrator_*`: simulate an A2/A3 orchestrator's consumer profile
  for level-3 fallback measurement.

## 3. Output schema (`ReplayValidationResult`)

| Field | Description |
| --- | --- |
| `total_passports` | Count of dict-shaped inputs processed |
| `matched_passport_arena1` | Resolutions that hit precedence level 1 |
| `matched_passport_root` | Hits at level 2 |
| `matched_orchestrator` | Hits at level 3 |
| `matched_fallback` | Hits at level 4 (UNKNOWN / UNAVAILABLE) |
| `expected_match_count` | Count where resolved id == expected (if supplied) |
| `expected_match_rate` | `expected_match_count / total_passports` |
| `sources_observed` | Sorted list of unique source labels seen |

## 4. Round-trip property

When PR-A 0-9P writes `passport.arena1.generation_profile_id` and the
audit then runs `replay_validate(passports)` on the same passports,
all results have `source == "passport_arena1"`. Verified by
`test_passport_identity_round_trips_through_attribution_chain`
(in PR-A) and `test_replay_groups_metrics_by_profile`
+ `test_replay_keeps_unknown_profile_visible` (in PR-B).

## 5. Exception safety

`replay_validate` wraps each per-passport resolution in try/except
and never propagates. Pathological inputs reduce `total_passports`
without crashing.

## 6. Audit ↔ replay interplay

`audit(events)` operates on aggregate `arena_batch_metrics` — already
post-resolution; the source label is read from `attribution_source`
field if present, else conservatively classified as "passport".
`replay_validate(passports)` operates on the original passport blobs —
exact source classification.

The two functions are complementary:

- `audit` answers *production-side* coverage: are batches in the wild
  carrying clean identity?
- `replay_validate` answers *fixture-side* correctness: does the
  4-level precedence chain do what the contract says?
