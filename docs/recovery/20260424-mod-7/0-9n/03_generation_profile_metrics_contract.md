# 03 — Generation Profile Metrics Contract

TEAM ORDER 0-9N §9.3 + §12.2 deliverable.

## 1. Purpose

A **generation profile** is a reusable configuration fingerprint for the black-box
alpha generator. Examples of what a profile parameterizes:

- `N_GEN`, `POP_SIZE`, `TOP_K` — GP loop shape
- Indicator sampling preferences (read-only observation — we do not design internal operators)
- ENTRY_THR / EXIT_THR / MIN_HOLD / COOLDOWN — signal configuration from `settings.py`
- Cost model (`cost_bps`)
- Regime set / symbol set
- A13 downstream-truth guidance version

0-9N treats the profile as an opaque fingerprint. We do NOT design operator-level
policy. We ONLY design the **metrics that scores each profile** based on Arena pass-rate outcomes.

## 2. `generation_profile_metrics` schema

```json
{
  "event_type": "generation_profile_metrics",
  "generation_profile_id": "gp_v10_volume_l9_2026-05",
  "profile_name": "v10 Volume L9 baseline",
  "profile_fingerprint": "sha256:a3f1b82...",
  "total_batches": 37,
  "total_candidates_generated": 5421,
  "avg_a1_pass_rate": 0.14,
  "avg_a2_pass_rate": 0.065,
  "avg_a3_pass_rate": 0.17,
  "avg_deployable_count": 0.4,
  "dominant_reject_reason": "SIGNAL_TOO_SPARSE",
  "signal_too_sparse_rate": 0.88,
  "oos_fail_rate": 0.008,
  "unknown_reject_rate": 0.0,
  "profile_score": 0.043,
  "next_budget_weight": 0.12,
  "last_updated_at": "2026-05-01T03:00:00Z",
  "telemetry_version": "1"
}
```

### 2.1 Required fields

| Field | Type | Semantics |
|---|---|---|
| `generation_profile_id` | string | Stable identifier. Derivation: `SHA256(profile_fingerprint)` first 16 hex chars, prefixed with `gp_`. |
| `profile_name` | string | Human-readable name (operator-assigned). |
| `profile_fingerprint` | string | `sha256:<hex>` of a JSON-canonicalized profile config dict. Deterministic. |
| `total_batches` | int | Total batches observed under this profile across all runs. |
| `total_candidates_generated` | int | Sum of entered_count at A1 across all batches. |
| `avg_a1_pass_rate` | float | Batch-weighted mean of A1 pass_rate from `arena_batch_metrics`. |
| `avg_a2_pass_rate` | float | Same for A2. |
| `avg_a3_pass_rate` | float | Same for A3. |
| `avg_deployable_count` | float | Mean deployable_count per batch. |
| `dominant_reject_reason` | string | Top canonical reason across all batches under this profile. |
| `signal_too_sparse_rate` | float | Fraction of rejections classified SIGNAL_TOO_SPARSE. |
| `oos_fail_rate` | float | Fraction classified OOS_FAIL. |
| `unknown_reject_rate` | float | Fraction classified UNKNOWN_REJECT. Target: < 1%. |
| `profile_score` | float | Composite score. See §04 for formula. |
| `next_budget_weight` | float | Normalized weight in [0, 1] for next round's budget allocator. |
| `last_updated_at` | RFC3339 | Most recent batch close contributing to this profile. |
| `telemetry_version` | string | Schema version marker. Currently `"1"`. |

### 2.2 Optional fields

| Field | Type | Use |
|---|---|---|
| `n_deployable_ever` | int | Count of candidates that ever reached A3 COMPLETE under this profile. |
| `best_batch_deployable_count` | int | Max deployable in a single batch. |
| `worst_batch_pass_rate` | float | A2 floor observation. |
| `stability_index` | float | Variance of per-batch pass_rate. High variance → unstable profile. |
| `notes` | string | Operator annotation. |

## 3. Profile fingerprint canonicalization

A profile fingerprint is computed from a canonical-JSON representation of the
profile config:

```python
import json, hashlib
canonical = json.dumps(profile_config, sort_keys=True, separators=(",", ":"))
profile_fingerprint = "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
profile_id = "gp_" + profile_fingerprint.split(":")[1][:16]
```

Where `profile_config` is a dict containing EXACTLY the fields the generator
reads that affect alpha production. The canonicalization is deterministic across
invocations — same config → same fingerprint → same profile_id.

**Guardrail**: the fingerprint MUST include all threshold-relevant config
(ENTRY_THR, EXIT_THR, MIN_HOLD, COOLDOWN, cost_bps, `A2_MIN_TRADES`, A3_* etc).
If a future PR changes `A2_MIN_TRADES` under a separate threshold order, the
fingerprint changes — making historical metrics NOT comparable to post-change
metrics, forcing an explicit baseline reset.

## 4. Profile scoring model (design — implementation in 0-9O)

The composite `profile_score` is a weighted sum:

```
profile_score =
    w1 * avg_a1_pass_rate
  + w2 * avg_a2_pass_rate
  + w3 * avg_a3_pass_rate
  + w4 * normalized_deployable_count
  - w5 * signal_too_sparse_rate
  - w6 * oos_fail_rate
  - w7 * unknown_reject_rate
  - w8 * instability_penalty
```

Where:
- `normalized_deployable_count = avg_deployable_count / theoretical_max`
- `instability_penalty = stddev(pass_rate across batches) / mean(pass_rate)`

### 4.1 Initial weight suggestions (0-9O will tune empirically)

```
w1 = 0.10    # A1 pass rate (low weight — A1 has many known rejection reasons)
w2 = 0.30    # A2 pass rate (HIGH — this is the current bottleneck)
w3 = 0.20    # A3 pass rate (medium — important but gated by A2)
w4 = 0.30    # normalized deployable (HIGH — this is the ultimate success metric)
w5 = 0.40    # SIGNAL_TOO_SPARSE penalty (HIGH — current dominant failure mode)
w6 = 0.20    # OOS_FAIL penalty
w7 = 0.50    # UNKNOWN_REJECT penalty (HIGH — any unknown is a telemetry bug)
w8 = 0.15    # instability penalty
```

Weights are illustrative. 0-9O may re-tune after observing the first few profiles.

### 4.2 Guardrails on scoring

- **No pass_rate above 1.0** (would indicate counter bug; cap at 1.0 before scoring).
- **No profile_score below -1.0** (cap). Scores ≤ 0 mean "disable this profile".
- **Score never used to modify arena decisions directly** — only used to modify
  generation BUDGET allocation in 0-9O's budget allocator.
- **Scoring MUST NOT create incentive to weaken Arena**. If lowering `A2_MIN_TRADES` would increase pass_rate, the scoring framework must NOT reward that — 0-9M's `NEVER_TRACE_ONLY_AUTHORIZABLE` guard (for `zangetsu_settings_sha`) combined with explicit j13 authorization-only for threshold changes enforces this at the governance layer.

## 5. Budget allocation model (design — implementation in 0-9O)

The `next_budget_weight` field drives a future budget allocator:

```python
# In 0-9O budget allocator (conceptual)
total_budget_next_round = FIXED_BUDGET   # e.g., 1000 GP generations
weights = normalize({
    profile.id: max(0.0, profile.profile_score + EXPLORATION_FLOOR)
    for profile in active_profiles
})
allocation = {
    profile.id: int(total_budget_next_round * weights[profile.id])
    for profile in active_profiles
}
```

`EXPLORATION_FLOOR` ensures every active profile gets a minimum of budget (e.g., 5%) to explore. Profiles with `profile_score <= -EXPLORATION_FLOOR` get zero allocation (effectively disabled for the next round).

## 6. `feedback_decision_record` — how budget shifts are audit-logged

Every budget reallocation emits a decision record:

```json
{
  "event_type": "feedback_decision_record",
  "decision_id": "dec-2026-05-01T04-00-00Z",
  "run_id": "...",
  "previous_profile_weights": {"gp_v10_volume_l9": 0.50, "gp_v10_momentum_l4": 0.50},
  "new_profile_weights": {"gp_v10_volume_l9": 0.30, "gp_v10_momentum_l4": 0.70},
  "reason": "gp_v10_volume_l9 SIGNAL_TOO_SPARSE_rate=0.92 >> gp_v10_momentum_l4 SIGNAL_TOO_SPARSE_rate=0.55",
  "observed_bottleneck": "A2 SIGNAL_TOO_SPARSE",
  "expected_effect": "↑ A2 pass rate by ~8pp based on observed profile delta",
  "safety_constraints": [
    "A2_MIN_TRADES unchanged",
    "Arena pass/fail logic unchanged",
    "No profile at 0% budget — EXPLORATION_FLOOR=0.05 enforced",
    "Gate-A + Gate-B must pass on the implementing PR"
  ],
  "created_at": "2026-05-01T04:00:00Z",
  "telemetry_version": "1"
}
```

Every decision record is:
- Emitted to engine.jsonl (trace-native stream) OR a dedicated `feedback_decisions.jsonl`.
- Append-only; NEVER revised.
- Signed via Gate-A / Gate-B / signed PR flow if it implies a config change.

## 7. Lifecycle mapping from profile perspective

Each `arena_batch_metrics` event carries `generation_profile_id`. The profile
aggregator then:

1. Reads all `arena_batch_metrics` with matching `generation_profile_id`.
2. Computes aggregates per §2.
3. Computes `profile_score` per §4.
4. Emits a `generation_profile_metrics` event.

No per-alpha join required.

## 8. What this contract **does NOT** provide

- Per-alpha reasoning ("why did this specific alpha fail at A2?"). That's P7-PR2 territory and remains available on demand but is NOT the feedback loop's input.
- Formula lineage / ancestry.
- Semantic interpretability.
- Live risk / drawdown monitoring (that's a CANARY-era concern, out of 0-9N scope).
