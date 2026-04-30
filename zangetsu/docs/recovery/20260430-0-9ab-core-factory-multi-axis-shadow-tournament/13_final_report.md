# MASTER ORDER 0-9AB — FINAL REPORT

**Order**: 0-9AB-CORE-FACTORY-MULTI-AXIS-SHADOW-TOURNAMENT
**Date**: 2026-04-30
**Mode**: CORE-FACTORY / SHADOW-ONLY / MULTI-AXIS TOURNAMENT

## Verdict

`MULTI_AXIS_CONTINUE_ONE_MORE_ROUND`

Two independent triggers point at this verdict:
1. **Scoreboard spread**: C=89.12, H=88.81, D=86.21 — all three axes within 2.91 points (< 3 pt threshold per order §3).
2. **Gemini unavailable**: per order §15 the verdict cap under `GEMINI_REVIEW_UNAVAILABLE` is exactly `MULTI_AXIS_CONTINUE_ONE_MORE_ROUND`.

## Baseline

| Item | Value |
|---|---|
| HEAD | `cd520d03` (parent merge SHA) |
| Branch | `phase-7/0-9ab-core-factory-multi-axis-shadow` |
| Parent order | 0-9AA-NEW-ALPHA-AXIS-SELECTION (`MULTI_AXIS_SHADOW_REQUIRED`) |
| arena_pipeline workers | 4 (untouched) |
| zangetsu_status.deployable_count | 0 (unchanged) |
| A2_MIN_TRADES | 25 (unchanged) |

## Tournament Summary

```
generation_id: 0-9ab-shadow-v1
axes:          H, C, D
symbols:       BTCUSDT, ETHUSDT, SOLUSDT
timeframe:     15m
candidates:    576 (192 per axis × 3 axes)
unique_form:   32 per axis (target met)
collisions:    0
unsupported:   0
PASSED:        8
REJECTED:      568
NOT_EVALUATED: 0
ERROR:         0
UNKNOWN_REJECT: 0
duration:      141.75 s
```

## Scoreboard

| Rank | Axis | Total | Note |
|---:|---|---:|---|
| 1 | C | 89.12 | only positive avg_net_bps on LONG side (+12.72 bps); 3 PASSED |
| 2 | H | 88.81 | 5 PASSED, but ±5000-bps net is a numerical-stability artifact (round-2 clip needed) |
| 3 | D | 86.21 | 0 PASSED; 174 near-survivors; sign-flip rule too sparse for D |

## Why Not Pick a Single Winner Now

- C and H differ by 0.31 pts — within scoring noise.
- C–D gap is 2.91 pts — also within the < 3 pt round-2 trigger.
- H's avg_net_bps is dominated by tanh ∘ protected_div blow-ups; H needs value-clip before its score is trustworthy.
- 14-symbol universe in D may need widening before D's rank-spread anchor is fairly tested.

## Why Not CORE_FACTORY_PATH_BLOCKED

The original alpha factory loop ran end-to-end:
- Primitive Universe (curated wrappers around alpha_primitives) → working
- Combination Grammar (per-axis grammars) → 96 unique formulas produced
- Alpha Generator → 576 candidate records
- Economic Arena (shadow adapter) → 576/576 evaluated
- Survivor / Near-Survivor → 8 + 406 separated
- Rejection Feedback → weights generated from 568 real rejections
- Next-batch direction → axis scoreboard ranks H/C/D

No core-factory blocker fired. Loop is restored.

## Why Not ALL_AXES_FAIL_ECONOMIC_ARENA

C-LONG produced 3 PASSED and an avg_net_bps of +12.72; H produced 5 PASSED. At least one side of at least one axis crossed A2 — the arena did not blanket-fail.

## Acceptance Criteria Status

| AC | Status | Note |
|---|---|---|
| AC1 — state locked at HEAD ≥ cd520d03 | PASS | 00_state_lock.md |
| AC2 — 0-9AA result incorporated | PASS | 01_system_reset_confirmation.md |
| AC3 — H, C, D all attempted | PASS | 192 records each |
| AC4 — A microstructure deferred | PASS | axis_registry.role = deferred |
| AC5 — 0-9ZB not used as mainline prereq | PASS | 0-9ZB referenced only as parallel track in 13 |
| AC6 — system reset confirmation | PASS | 01 |
| AC7 — candidate unit defined exactly | PASS | 03 + candidate_manifest.py |
| AC8 — H ≥ 128 records | PASS | 192 |
| AC9 — C ≥ 128 records | PASS | 192 |
| AC10 — D ≥ 128 records | PASS | 192 |
| AC11 — total ≥ 384 | PASS | 576 |
| AC12 — unique formulas ≥ 32 per axis | PASS | 32 each |
| AC13 — manifest jsonl produced | PASS | shadow_outputs/candidate_manifest.jsonl |
| AC14 — alpha_hash deterministic | PASS | test |
| AC15 — candidate_id deterministic | PASS | test |
| AC16 — formula collision rate reported | PASS | 0 collisions |
| AC17 — unsupported operators fail closed | PASS | UnsupportedOperatorError |
| AC18 — intended side metadata preserved | PASS | manifest carries it |
| AC19 — realized counts not fabricated | PASS | from simulator output |
| AC20 — Economic Arena safely attempted | PASS | shadow adapter |
| AC21 — no production DB mutation | PASS | read-only SELECT |
| AC22 — NOT_EVALUATED ≠ REJECTED | PASS | enforced + tested |
| AC23 — REJECTED carry reject_reason | PASS | 568/568 |
| AC24 — NOT_EVALUATED carry blocker_reason | PASS | rule enforced (0 in this run) |
| AC25 — UNKNOWN_REJECT explicit | PASS | count = 0 |
| AC26 — long/short report | PASS | 06 + long_short_summary.csv |
| AC27 — survivor/near-survivor report | PASS | 08 + near_survivor_report.csv |
| AC28 — NOT_EVALUATED never survivor | PASS | rule enforced |
| AC29 — NOT_EVALUATED never near-survivor | PASS | rule enforced |
| AC30 — no fake deployables | PASS | deployable_count VIEW = 0 |
| AC31 — feedback_weights valid OR empty_with_reason | PASS | OK overall |
| AC32 — axis scoreboard ranks H/C/D | PASS | 10 + axis_scoreboard.csv |
| AC33 — A2_MIN_TRADES = 25 | PASS | tested |
| AC34 — Arena thresholds unchanged | PASS | tested |
| AC35 — champion promotion unchanged | PASS | 11 |
| AC36 — deployable_count semantics unchanged | PASS | 11 |
| AC37 — execution / capital / risk unchanged | PASS | 11 |
| AC38 — no live trading | PASS |
| AC39 — no CANARY | PASS |
| AC40 — no production rollout | PASS |
| AC41 — controlled diff = 0 forbidden | PASS | 11 |
| AC42 — tests pass | PASS | 32/32 |
| AC43 — Gemini review complete OR unavailability documented | PASS | 12 documents unavailable + self-substitute |
| AC44 — final verdict allowed | PASS | MULTI_AXIS_CONTINUE_ONE_MORE_ROUND |
| AC45 — next order finite | PASS | 0-9AC-MULTI-AXIS-ROUND2-BOUNDED |

## STOP-Condition Checklist

All 23 STOP conditions clean — see 11_controlled_diff_report.md.

## Next Order

`0-9AC-MULTI-AXIS-ROUND2-BOUNDED`

Round-2 scope (bounded):
1. Add value-clip in primitive_inventory (cap |signal| at p99 of empirical distribution) before computing trades.
2. Replace pure sign-flip with band-crossing (signal must cross ±k × signal_stddev) for trade-generation.
3. Widen symbol universe to all 14 for D's cross-sectional rank.
4. Configure Gemini auth and re-run adversarial review.
5. Re-run tournament with same H/C/D axes; expect either a clear single-axis winner or a CORE_FACTORY_PATH_BLOCKED with exact internal blocker named.

Out of scope for round 2:
- Adding new axes (A is still deferred until 0-9ZB; E remains fallback).
- Changing A2_MIN_TRADES, Arena thresholds, or any production runtime.
- Maker-only / VIP / orderbook capture (parked).

## Final Statement

0-9AB restored the original ZANGETSU alpha factory loop in shadow mode. The tournament ran end-to-end across H/C/D axes with full identity discipline (deterministic alpha_hash + candidate_id, 0 collisions, 0 unsupported operators, 0 UNKNOWN_REJECT). Verdict is bounded by both scoreboard spread and Gemini unavailability to MULTI_AXIS_CONTINUE_ONE_MORE_ROUND. No source mutation, no DB mutation, no live trading, no CANARY, no rollout. Controlled diff = 0 forbidden mutations.
