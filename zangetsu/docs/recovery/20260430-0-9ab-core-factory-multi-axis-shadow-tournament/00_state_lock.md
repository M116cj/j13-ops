# 00 — State Lock

**ORDER**: 0-9AB-CORE-FACTORY-MULTI-AXIS-SHADOW-TOURNAMENT
**Date**: 2026-04-30
**Mode**: CORE-FACTORY / SHADOW-ONLY / MULTI-AXIS TOURNAMENT

## Frozen Baseline

| Item | Value |
|---|---|
| HEAD | `cd520d03` |
| Branch | `phase-7/0-9ab-core-factory-multi-axis-shadow` |
| Parent order | 0-9AA-NEW-ALPHA-AXIS-SELECTION |
| Parent verdict | `MULTI_AXIS_SHADOW_REQUIRED` |
| Selected axes | H (primary), C/D (shadow), E (fallback), A (deferred) |
| arena_pipeline workers | 4 (verified `ps -ef`) |
| `zangetsu_status.deployable_count` | 0 |
| `zangetsu_status.last_live_at_age_h` | NULL |
| `A2_MIN_TRADES` | 25 (verified at `zangetsu/services/arena_gates.py:48`, `zangetsu/config/settings.py:29`) |
| CANARY | not started |
| Production rollout | not started |
| Live trading | not started |

## STOP Verification (per §17)

- STOP-1 (live order): not attempted
- STOP-2 (exchange API key): not requested or used
- STOP-3 (production execution path): unchanged
- STOP-4 (capital/risk): unchanged
- STOP-5 (production DB table): not mutated
- STOP-6 (CANARY): not started
- STOP-7 (production rollout): not started
- STOP-8 (Arena threshold): unchanged
- STOP-9 (A2_MIN_TRADES): 25 — unchanged
- STOP-10 (champion promotion): unchanged
- STOP-11 (deployable_count semantics): unchanged
- STOP-23 (drift into maker-only / VIP / orderbook / execution arch): no — this order is shadow-only core-factory restoration

## Working-Tree Sanity

Working tree contains modifications to runtime byproducts only (calcifer logs, zangetsu engine.jsonl rotation) — NOT included in this branch.
