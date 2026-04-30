# 03 — Core Factory Contract

**ORDER**: 0-9AB — Workstream A

## Package Layout (`zangetsu/core_factory/`)

| Module | Purpose |
|---|---|
| `constants.py` | A2_MIN_TRADES, cost, axis IDs, allowed verdicts/blockers |
| `axis_registry.py` | Axis identity, role, component data requirements |
| `primitive_inventory.py` | Curated wrappers around `engine.components.alpha_primitives` (fail-closed) |
| `combination_grammar.py` | Per-axis grammar producing canonical AST + alpha_hash |
| `candidate_manifest.py` | candidate_id, expand-formulas-to-candidates, JSONL writer |
| `economic_arena_adapter.py` | Shadow-only evaluator (OHLCV → trades → arena_gates A2) |
| `rejection_feedback.py` | Reject-reason aggregator + feedback_weights generator |
| `survivor_bank.py` | Survivor / near-survivor classifier |
| `long_short_summary.py` | Per-(axis, side_mode) aggregate |
| `axis_scoreboard.py` | 7-category weighted scoring + ranking |
| `io.py` | JSONL/CSV/JSON writers |
| `shadow_batch_runner.py` | Tournament entrypoint (CLI) |

## Candidate Schema

```json
{
  "candidate_id": "<sha256>",
  "generation_id": "0-9ab-shadow-v1",
  "axis_id": "H|C|D|E|A",
  "grammar_family": "axis_<id>",
  "primitive_family": "add|sub|mul|...|UNSUPPORTED",
  "formula": "<canonical_text>",
  "alpha_hash": "<sha256>",
  "symbol": "<USDT_perp>",
  "timeframe": "15m",
  "intended_side_mode": "LONG|SHORT|BOTH"
}
```

## Result Schema

```json
{
  "candidate_id": "...",
  "axis_id": "...",
  "alpha_hash": "...",
  "symbol": "...",
  "timeframe": "...",
  "intended_side_mode": "...",
  "status": "PASSED|REJECTED|ERROR|NOT_EVALUATED",
  "reject_reason": "<string|null>",
  "blocker_reason": "<one of allowed blockers|null>",
  "gross_bps": <float>,
  "cost_bps": <float>,
  "net_bps": <float>,
  "trade_count": <int>,
  "long_trade_count": <int>,
  "short_trade_count": <int>,
  "a1_pass": <bool|null>,
  "a2_pass": <bool|null>
}
```

## Identity Rules (per order §7)

- `alpha_hash = sha256(canonical_formula_text)` — excludes timestamp, generation_id, output path, created_at, random seed.
- `candidate_id = sha256(generation_id + axis_id + alpha_hash + symbol + timeframe + intended_side_mode)`.

## Status Rules (per order §8)

- Evaluated rejection: `{"status":"REJECTED","reject_reason":"<reason>"}`
- Evaluated pass: `{"status":"PASSED","reject_reason":null}`
- Not evaluated: `{"status":"NOT_EVALUATED","blocker_reason":"<one of allowed>"}`
- Errors: `{"status":"ERROR","reject_reason":"evaluation_runtime_error"}`

NOT_EVALUATED candidates are NEVER labeled REJECTED, NEVER given economic reject reasons, and NEVER contribute to feedback weights.

## Production Isolation

`zangetsu/services/arena_pipeline.py` does NOT import `core_factory` (verified by `tests/test_core_factory_invariants.py::test_core_factory_not_imported_by_production_pipeline`).
