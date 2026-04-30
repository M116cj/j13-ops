# 0-9AD — FINAL REPORT

**Order**: 0-9AD-C-AXIS-SHADOW-ALPHA-MINING-START
**Date**: 2026-04-30
**Mode**: SHADOW-ONLY / NORMAL MINING

## Verdict

```
C_AXIS_SHADOW_MINING_STARTED_GREEN
```

All 14 GREEN criteria from order §12 are met (see acceptance table below).

## Tournament / Mining Summary

```
generation_id:     0-9ad-c-axis-mining-v1
axis:              C (Regime Conditional)
mode:              SHADOW
symbols:           14 (full available universe)
timeframe:         15m
side modes:        LONG, SHORT
candidates:        1792   (target 1024 ✓; min 512 ✓)
unique formulas:   64     (target ≥ 64 ✓)
collisions:        0
unsupported ops:   0
duration:          44.36 s
```

## Status Distribution

| Status | Count |
|---|---:|
| PASSED | 39 |
| REJECTED | 1753 |
| NOT_EVALUATED | 0 |
| ERROR | 0 |
| UNKNOWN_REJECT | 0 |

## Per-Side Result

| Side | n | PASSED | REJECTED | Realized LONG | Realized SHORT | Near-survivors |
|---|---:|---:|---:|---:|---:|---:|
| LONG | 896 | 36 | 860 | 3,610,239 | 0 | 460 |
| SHORT | 896 | 3 | 893 | 0 | 3,420,868 | 606 |

## Dominant Reject Reasons

1. `no_trades_generated`: 60.4% (1058/1753)
2. `non_positive_net`: 33.4% (585/1753)
3. `too_few_trades`: 6.3% (110/1753)
4. `UNKNOWN_REJECT`: 0

## Best Symbols (by survivor count)

| Symbol | Survivors |
|---|---:|
| AVAXUSDT, SOLUSDT | 5 each |
| AAVEUSDT, BNBUSDT | 4 each |
| 1000SHIBUSDT, DOGEUSDT, ETHUSDT | 3 each |
| 1000PEPEUSDT, BTCUSDT, FILUSDT, GALAUSDT, LINKUSDT, XRPUSDT | 2 each |
| DOTUSDT | 0 |

## Feedback Weights (overall, status = OK)

| Reason | Weight |
|---|---:|
| no_trades_generated | 0.6035 |
| non_positive_net | 0.3337 |
| too_few_trades | 0.0627 |

## Next-Batch Weights (recommended actions for 0-9AE)

1. **NO_TRADES_GENERATED** (60.4%) → increase trigger density / adjust regime condition. Δ = -0.10
2. **TRAIN_NEG_PNL** (33.4%) → reduce similar grammar family. Δ = -0.20
3. **SIGNAL_TOO_SPARSE** (6.3%) → increase denser signal variants. Δ = -0.15

UNKNOWN_REJECT: 0 → no taxonomy gap.

## Controlled Diff

forbidden_diff = **0**. All 17 STOP conditions clean. See 10.

## Acceptance Criteria — All PASS

| AC | Status |
|---|---|
| AC1 — HEAD locked | PASS (00) |
| AC2 — C only | PASS |
| AC3 — SHADOW | PASS |
| AC4 — no new axes | PASS |
| AC5 — target 1024 attempted | PASS (1792 actual) |
| AC6 — min 512 | PASS |
| AC7 — unique_formula_count reported (≥ 64) | PASS (= 64) |
| AC8 — formula_collision_rate reported (0) | PASS |
| AC9 — unsupported_operator_count reported (0) | PASS |
| AC10 — candidate_manifest.jsonl produced | PASS |
| AC11 — shadow_batch_results.jsonl produced | PASS |
| AC12 — every candidate has status | PASS |
| AC13 — every evaluated rejection has reject_reason | PASS |
| AC14 — NOT_EVALUATED candidates carry blocker_reason | PASS (rule enforced; 0 in run) |
| AC15 — UNKNOWN_REJECT explicitly reported | PASS (= 0) |
| AC16 — long_short_summary.csv produced | PASS |
| AC17 — survivor_report.csv produced | PASS |
| AC18 — near_survivor_report.csv produced | PASS |
| AC19 — feedback_weights.json produced | PASS |
| AC20 — next_batch_weights.json produced | PASS |
| AC21 — tests pass | PASS (54/54) |
| AC22 — controlled diff forbidden_diff = 0 | PASS |
| AC23 — A2_MIN_TRADES = 25 | PASS |
| AC24 — Arena thresholds unchanged | PASS |
| AC25 — champion promotion unchanged | PASS |
| AC26 — deployable_count unchanged | PASS |
| AC27 — no live trading | PASS |
| AC28 — no CANARY | PASS |
| AC29 — no production rollout | PASS |
| AC30 — no production DB mutation | PASS |
| AC31 — no execution / capital / risk | PASS |
| AC32 — final verdict allowed | PASS (`C_AXIS_SHADOW_MINING_STARTED_GREEN` ∈ allowed set) |
| AC33 — next finite order produced | PASS (`0-9AE-C-AXIS-MINING-BATCH-2`) |

## Internal Team Decision Discussion

Per §14 / §6, all autonomous-category decisions made internally:
- Set `--candidate-count-per-axis 1792` to force 64 unique formulas given the 14×2 expansion (rather than adding a new CLI flag — Category A formatting choice)
- Used `sign_flip` trigger for C (axis-C default; band-crossing belongs to D)
- Added `survivor_report.csv` and `next_batch_weights.json` outputs by patching shadow_batch_runner only (no broader runtime change)
- Generated 12 evidence reports + 14 machine outputs without invoking new prerequisite chains

No Category C decisions taken (no verdict change, no new axis, no threshold touch, no DB touch).

## Next Order

```
0-9AE-C-AXIS-MINING-BATCH-2
```

Scope (per order §22 mapping):
- Continue C-axis mining loop with feedback applied.
- Apply next_batch_weights (above) to bias generator toward denser-signal grammars.
- Same SHADOW-only safety stance.
- Same A2_MIN_TRADES = 25.
- No new axis. No maker-only. No VIP. No orderbook capture. No execution architecture.

## Final Statement

ZANGETSU is now in normal SHADOW alpha-mining mode on the C Regime-Conditional axis. The full loop ran end-to-end: generate (1792) → assess (1792/1792) → reject/survive (1753/39) → near-survivor classify (1066) → feedback (status OK) → next-batch weights (3 actionable). No production runtime / DB / live-trading touched. Controlled diff = 0 forbidden mutations.
