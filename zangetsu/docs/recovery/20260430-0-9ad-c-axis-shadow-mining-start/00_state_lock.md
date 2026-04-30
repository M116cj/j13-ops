# 00 — State Lock

**ORDER**: 0-9AD-C-AXIS-SHADOW-ALPHA-MINING-START
**Date**: 2026-04-30
**Mode**: SHADOW-ONLY / NORMAL MINING

## Frozen Baseline

| Item | Value |
|---|---|
| Branch | `phase-7/0-9ad-c-axis-shadow-mining-start` |
| Base HEAD | `d3450a53` (parent: 0-9AC-CLOSE squash merge) |
| Parent order | 0-9AC-CLOSE-ROUND2-FINAL-CONVERGENCE-AND-MAINLINE-DEPLOYMENT |
| Parent verdict | `AXIS_C_SELECTED_FOR_SCALEUP` |
| Selected mining axis | C — Regime Conditional |
| arena_pipeline workers | unchanged |
| zangetsu_status.deployable_count | 0 (unchanged) |
| A2_MIN_TRADES | 25 (verified at services/arena_gates.py:48 + config/settings.py:29) |
| CANARY | not started |
| Production rollout | not started |
| Live trading | not started |

## STOP Verification

- STOP-1 (live trading): not attempted
- STOP-2 (exchange API key): not used
- STOP-3 (production execution): unchanged
- STOP-4 (capital/risk): unchanged
- STOP-5 (production DB): not mutated
- STOP-6 (CANARY): not started
- STOP-7 (production rollout): not started
- STOP-8 (Arena threshold): unchanged
- STOP-9 (A2_MIN_TRADES): 25 unchanged
- STOP-10 (champion promotion): unchanged
- STOP-11 (deployable_count semantics): unchanged
- STOP-12 (new axis): NO — only C
- STOP-13 (maker-only / VIP / orderbook): NO drift
- STOP-14 (NOT_EVALUATED → survivor): NO (rule enforced + tested)
- STOP-15 (near-survivor → deployable): NO (rule enforced + tested)
- STOP-16 (faked economic result): NO (real OHLCV evaluation)
- STOP-17 (forbidden mutation in diff): NO (see 10)

## Working-Tree Sanity

Working tree only modifications: long-running runtime byproducts (calcifer, engine.jsonl rotation) — NOT staged.
