# 0-9O-A — Generation Profile Identity Design

## 1. Purpose

Give ZANGETSU a stable, black-box identity for each generation profile so
Arena pass-rate telemetry can be grouped and compared by profile. No
alpha internals, no formula semantics, no per-alpha lineage are
introduced.

## 2. What a generation profile is

A generation profile is the set of stable parameters that govern the
GP-based alpha generator:

- `generator_type` — e.g. `"gp_v10"`
- `strategy_id` — e.g. `"j01"`, `"j02"`
- `n_gen`, `pop_size`, `top_k` — GP loop shape
- `entry_thr`, `exit_thr` — signal thresholds
- `min_hold`, `cooldown` — hold / cooldown bars
- optional future additions (cost model, regime set, guidance version)

Volatile fields are explicitly excluded (see §4).

## 3. Module contract

`zangetsu/services/generation_profile_identity.py` exports:

| Symbol | Purpose |
|--------|---------|
| `UNKNOWN_PROFILE_ID = "UNKNOWN_PROFILE"` | fallback id |
| `UNAVAILABLE_FINGERPRINT = "UNAVAILABLE"` | fallback fingerprint |
| `canonical_json(obj)` | sorted-keys, compact-separators JSON |
| `profile_fingerprint(config)` | `"sha256:<hex>"` or `UNAVAILABLE` |
| `profile_id_from_fingerprint(fp)` | `"gp_<first-16-hex>"` or `UNKNOWN_PROFILE` |
| `resolve_profile_identity(config, *, profile_name)` | full identity dict |
| `safe_resolve_profile_identity(...)` | exception-safe wrapper |

`resolve_profile_identity(...)` always returns a dict with three keys
(`profile_id`, `profile_fingerprint`, `profile_name`).
`safe_resolve_profile_identity(...)` is the preferred entry point for
runtime callers.

## 4. Volatile fields excluded from fingerprinting

The following keys are stripped recursively before hashing:

```
timestamp, timestamp_start, timestamp_end,
created_at, updated_at, last_updated_at,
run_id, batch_id, worker_id,
now, ts, clock, nonce
```

Rationale: two identical profiles must fingerprint identically across
runs, so that telemetry aggregation can group them.

## 5. Fingerprint derivation

```
stripped   = _strip_volatile(profile_config)
payload    = json.dumps(stripped, sort_keys=True, separators=(",", ":"))
digest     = sha256(payload.encode("utf-8")).hexdigest()
fingerprint = "sha256:" + digest
profile_id  = "gp_" + digest[:16]
```

All transformations are pure. The same input always yields the same
output.

## 6. Fallback policy

| Condition | Returned value |
|-----------|----------------|
| `profile_config` is `None` | `UNAVAILABLE_FINGERPRINT` |
| `profile_config` is empty (after stripping) | `UNAVAILABLE_FINGERPRINT` |
| Hashing raises | `UNAVAILABLE_FINGERPRINT` |
| Fingerprint not prefixed `sha256:` | `UNKNOWN_PROFILE_ID` |
| Fingerprint hex too short | `UNKNOWN_PROFILE_ID` |

No exception ever propagates out of the module. The helpers are safe to
call inside `arena_pipeline`'s worker loop.

## 7. Tests covering this doc

- `test_profile_fingerprint_is_sha256_prefixed`
- `test_profile_fingerprint_is_stable_for_key_order_changes`
- `test_profile_fingerprint_excludes_timestamps`
- `test_profile_fingerprint_excludes_run_id`
- `test_profile_fingerprint_handles_unavailable_config`
- `test_profile_id_uses_upstream_identity_when_available`
- `test_profile_id_falls_back_to_unknown_when_missing`
- `test_profile_identity_failure_does_not_block_telemetry`
- `test_canonical_json_sorts_keys`
- `test_canonical_json_uses_compact_separators`
- `test_canonical_json_rejects_non_serializable_values_safely`
