# 0-9O-A — Profile Fingerprint Contract

## 1. Canonical JSON

`canonical_json(obj)` returns a deterministic JSON string:

- `sort_keys=True`
- `separators=(",", ":")` (no whitespace)
- `default=str` (non-serializable values fall back to `repr` via `str()`)

Example:

```python
canonical_json({"b": 1, "a": 2})
# -> '{"a":2,"b":1}'
```

## 2. Volatile field exclusion

Before canonicalization the config is stripped of timestamps, run ids,
batch ids, worker ids, and other per-invocation noise (full list in
`01_generation_profile_identity_design.md` §4). This exclusion is
recursive; nested mappings are cleaned the same way.

## 3. Hashing

```
sha256(canonical_json(stripped).encode("utf-8")).hexdigest()
```

The return value is prefixed with `"sha256:"`, giving a 71-character
fingerprint:

```
sha256:<64 hex chars>
```

## 4. Profile id derivation

```
profile_id = "gp_" + <first 16 hex chars of digest>
```

16 hex chars = 64 bits, collision probability ≈ 2⁻³² after
≈ 2³² profiles. This is sufficient for operational use; aggregations
match on the full fingerprint, not the id.

## 5. Fallback rules

| Case | Fingerprint | Profile id |
|------|-------------|------------|
| `None` config | `UNAVAILABLE` | `UNKNOWN_PROFILE` |
| Empty config (post-strip) | `UNAVAILABLE` | `UNKNOWN_PROFILE` |
| Canonicalization raises | `UNAVAILABLE` | `UNKNOWN_PROFILE` |
| Valid config | `sha256:<hex>` | `gp_<hex[:16]>` |

## 6. Determinism guarantees

- Key order in the input mapping MUST NOT affect the fingerprint.
- Timestamps / run ids MUST NOT affect the fingerprint.
- Equivalent configs (same fields, same values) MUST produce the same
  fingerprint regardless of run.

These are all covered by the unit tests enumerated in
`01_generation_profile_identity_design.md` §7.

## 7. Non-goals

- Human-readable diff between profiles is NOT the fingerprint's
  responsibility. Use stored profile configs for diffing.
- Security / cryptographic integrity is NOT a design concern — SHA256 is
  used as a deterministic canonical hash, not a signing mechanism.
- Forward compatibility with future fields: adding a new stable field
  will change the fingerprint. This is desired: historical metrics must
  NOT silently aggregate with post-change metrics.
