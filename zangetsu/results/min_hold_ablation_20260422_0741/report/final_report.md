# min_hold Ablation — Decision-Grade Report

**Project:** Zangetsu · **Date (UTC):** 2026-04-22 07:41 – 07:43 · **Session:** same-session as 421-3 MR generalization

---

## 1. Goal

> **Under the Volume family best-known candidate (`rank_window=250`, `entry_threshold=0.90`, `exit_threshold=0.50`), is `min_hold=60` still a residual blocker in A1 / val-gate?**

Not the prior question ("is min_hold=60 a blocker at production-current 500×0.80?") — the **new** question anchors against the already-optimized Volume baseline (Option Y, j13-confirmed 2026-04-22).

Allowed answers: `YES — CONFIRMED` / `MIXED — PARTIALLY CONFIRMED` / `NO — NOT CONFIRMED`.

---

## 2. Execution Summary

| Field | Value |
|---|---|
| Commit | `f098ead5d9d61e2b407951ffc3006e6b078e2d37` (same as 421-3 MR task — same session) |
| Worker | single, sequential (C → B → A per j13 order 2026-04-22) |
| Wrapper | `/tmp/min_hold_ablation_wrapper.py` (wrapper-only, no production source touched) |
| DOE input | `/tmp/doe_volume_l9.yaml` — 10 Volume L9 formulas (v01 … v10_ref) |
| Symbols | 14-symbol universe (BTC/ETH/BNB/SOL/XRP/DOGE/LINK/AAVE/AVAX/DOT/FIL/1000PEPE/1000SHIB/GALA) |
| Timeframe | 15m |
| Locked parameters across all arms | rank_window=**250**, entry_threshold=**0.90**, exit_threshold=**0.50**, cooldown unchanged, cost_model=`per_symbol_CD03`, split/window/pset/strategy/MAX_HOLD_BARS unchanged |
| Variable | only `ALPHA_MIN_HOLD` (implemented via wrapper kwarg injection) |
| Arms | Arm C=60 (control, production baseline for hold floor) · Arm B=30 · Arm A=15 |
| Cells/arm | 10 formulas × 14 symbols = 140 cells |
| Same session / data window | ✅ all 3 arms back-to-back, same commit, same session |
| §A4/A5 note | A4/A5 may hard-code `min_hold=60` downstream; this experiment is still valid — bottleneck under investigation is **A1**, not A4/A5. Documented per task constraint #7. |

---

## 3. Wrapper Proofs

Each arm printed banner + first-call proof:

```
[min-hold-wrapper] ARM_RANK_WINDOW=250 (locked)
[min-hold-wrapper] ARM_ENTRY_THR=0.9 (locked)
[min-hold-wrapper] ARM_EXIT_THR=0.5 (locked)
[min-hold-wrapper] ARM_MIN_HOLD={60|30|15}  <-- variable
[min-hold-wrapper] PROOF first generate_alpha_signals uses rank_window=250 entry_threshold=0.9 min_hold={60|30|15} exit_threshold=0.5
```

**Smoke (P2, 1×1×3, vol_v10_ref × BTCUSDT):**

| Arm | trades | avg_hold | p50 | pile_15_20 | pile_30_35 | pile_60_65 | invariance |
|---|---:|---:|---:|---:|---:|---:|---|
| C=60 | 71 | 61.55 | 61 | 0 | 0 | **69** | ✓ |
| B=30 | 94 | 31.74 | 31 | 0 | **87** | 0 | ✓ |
| A=15 | 110 | 16.25 | 16 | **105** | 0 | 0 | ✓ |

Hold distribution cleanly dominated by the min_hold floor in each arm → patch propagation confirmed. Trade counts monotonically increase as min_hold decreases.

**`primary_invariance.match` (full runs):** Arm C 179/179 ✓ · Arm B 195/195 ✓ · Arm A 172/172 ✓ — 100% match across all 546 telemetry rows.

---

## 4. Topline 3-Arm Comparison

| Metric | Arm C (min=60) | Arm B (min=30) | Arm A (min=15) | ΔB vs C | ΔA vs C |
|---|---:|---:|---:|---:|---:|
| Total cells | 140 | 140 | 140 | 0 | 0 |
| **A1 survivors** | **2** | **1** | **1** | **−1** | **−1** |
| Symbols with ≥1 survivor | **2** (SOL, LINK) | **1** (DOT) | **1** (GALA) | −1 | −1 |
| Cells reaching val | 39 | 55 | 32 | +16 | −7 |
| `a1_train_neg_pnl` | 101 | 85 | **108** | −16 | **+7** |
| `a1_val_neg_pnl` | 19 | **35** | 19 | +16 | 0 |
| `a1_val_low_wr` | 17 | 13 | 7 | −4 | −10 |
| `a1_val_low_sharpe` | 1 | 6 | 5 | +5 | +4 |
| Mean train net_pnl | −0.1193 | −0.0707 | −0.1448 | +0.0486 | −0.0255 |
| Mean val net_pnl | **+0.0276** | **−0.0394** | **−0.0404** | −0.0670 | −0.0680 |
| Mean train Sharpe | −0.4528 | −0.3396 | −0.8204 | +0.1132 | −0.3676 |
| Mean val Sharpe | **+0.2088** | **−0.3259** | **−0.5193** | −0.5347 | −0.7281 |
| Total train trades | 9,264 | 12,108 | 14,003 | +2,844 | +4,739 |
| Trade-weighted avg hold | 62.89 | 33.00 | 18.63 | (floor) | (floor) |

### Surviving-symbol overlap

- Arm C survivors: **{SOLUSDT, LINKUSDT}**
- Arm B survivors: **{DOTUSDT}**
- Arm A survivors: **{GALAUSDT}**
- **Intersection = ∅** — **no symbol survives across arms.** Each lower-floor survivor is a *different* symbol, not a refinement of the higher-floor survivors. This is strong evidence of noise-driven, fragile survival rather than hold-floor-mediated edge recovery.

---

## 5. Hold / Exit Comparison

| Metric | Arm C (60) | Arm B (30) | Arm A (15) |
|---|---:|---:|---:|
| pile_15_20 | 5 | 2 | **11,686** (83.5%) |
| pile_30_35 | 1 | **10,482** (86.6%) | 368 |
| pile_60_65 | **7,951** (85.8%) | 72 | 49 |
| pile_115_120 | (residual) | (residual) | (residual) |
| `exit_signal` | 10,263 (~99%) | 14,046 (~99%) | 15,257 (~99%) |
| **`exit_atr`** | **0** | **0** | **0** |
| `exit_max_hold` | 37 | 12 | 5 |

- **A1 ATR stop is dead in all 3 arms** (0/38,531 total trades) — confirms prior RCA.
- `min_hold` floor is the dominant exit driver in each arm (≥83% of trades exit in the first bucket above floor).
- Mechanical shape changes cleanly with `min_hold` — the wrapper's intervention is clean; observed A1 survival differences are *not* artifacts of exit mechanics.

---

## 6. Arm-Specific Analysis

### Arm C (min=60) — the best of the three

- 2 survivors across 2 different symbols (SOL, LINK); mean val net_pnl **+0.028** and mean val Sharpe **+0.21** (the only arm with *positive* val quality).
- 101 `train_neg_pnl` rejects is the mid value — train gate is tight but not excessive.
- 19 `val_neg_pnl` rejects — lowest among the three.

### Arm B (min=30) — the "widened-train, collapsed-val" trap

- Train gate widens: −16 `train_neg_pnl` rejects, +16 cells reach val (39→55, +41%).
- **But all 16 extra cells are rejected at val_neg_pnl (+16)** and 5 extra at val_low_sharpe. Net A1 survivor: 2 → 1.
- Mean val Sharpe collapses from +0.21 to −0.33 (−0.53 swing). Val quality regression is *not* marginal — it's a full sign flip.
- This is the exact "improvement is only due to deferred rejection / val absorption" failure mode explicitly flagged in §13.3.

### Arm A (min=15) — broken train gate, still no val recovery

- Train gate actually worsens: `train_neg_pnl` rises 101 → **108** (+7). Lowering hold floor so far that train gate cannot discriminate — signals become too noisy.
- Cells reaching val drops 39 → **32** (−7) — fewer cells survive train.
- Mean train Sharpe collapses −0.45 → **−0.82** (worst of the 3).
- Mean val Sharpe −0.52 (worst of the 3).
- 1 survivor at GALAUSDT — a symbol neither SOL/LINK (Arm C) nor DOT (Arm B); noise-driven.

### Cross-arm pattern

| Pattern | Observation |
|---|---|
| Monotonic survivor gain with lower min_hold? | **No** — C=2, B=1, A=1 (survival peaks at floor=60). |
| Monotonic train-gate improvement? | **No** — B improves (−16 rejects), A regresses (+7 rejects). |
| Monotonic val quality gain? | **No — opposite.** Mean val Sharpe **+0.21 → −0.33 → −0.52** monotonically *deteriorates* as min_hold decreases. |
| Symbol-breadth gain? | **No** — breadth *narrows* (2 → 1 → 1). |
| Any arm matches YES criteria? | **No**, per §7 below. |

---

## 7. Verdict

Question:
> **Under Volume family best-known candidate `250×0.90`, is `min_hold=60` still a residual A1/val-gate blocker?**

### Answer: **NO — NOT CONFIRMED**

### Rule application (j13 criteria 2026-04-22)

**YES — CONFIRMED** requires that 30 or 15 relative to 60 **simultaneously** shows:
- A1 survivors up — ❌ **survivors decreased** (2 → 1 in both B and A)
- `a1_train_neg_pnl` substantially down — ❌ only B partially (−16), A worsens (+7); neither arm is monotone
- `a1_val_neg_pnl` improvement *not* via train-premature-death — ❌ B's improvements at train are fully reabsorbed into val_neg_pnl (+16); A has 0 val_neg_pnl change only because 7 fewer cells reached val
- Breadth not narrowing — ❌ breadth narrows **2 → 1** in both arms, and surviving-symbol sets are disjoint (no common survivor)
- Val quality not deteriorating — ❌ mean val Sharpe collapses **+0.21 → −0.33 → −0.52**

Every YES criterion fails. Moreover, **none of the five bullets is met for any single arm**, so neither B nor A can be labelled YES individually.

**MIXED — PARTIALLY CONFIRMED** requires partial improvement offset by meaningful degradation, OR survivors increasing without breadth, OR train-gate widening without decision-grade win.
- Arm B shows the superficial signature (train widens, more cells reach val), but survivors *drop*, breadth *narrows*, and val quality *collapses*. This is not MIXED — it is strictly worse at the decision-grade outcome layer.
- Arm A is worse on *every* dimension.

**NO — NOT CONFIRMED** per j13: "若 30/15 對 60 沒實質好處，或更差，則 min_hold=60 在最佳 candidate 下仍不是 blocker。"
- ✅ Neither B nor A delivers real benefit over C=60.
- ✅ Both arms deliver *net worse* outcomes on survivors, breadth, and val quality.
- ✅ The train-side improvement observed in B is a mirage — it manifests only as deferred rejection at val.

---

## 8. Minimal Defect Statement

> Under Volume best-known candidate 250×0.90, lowering `min_hold` below 60 does not reveal additional edge: survivor count drops (2 → 1), symbol breadth narrows (2 → 1, disjoint survivors), and mean val Sharpe collapses from +0.21 to −0.33 (min=30) and −0.52 (min=15); `min_hold=60` is **not** the residual A1/val blocker at the best-known Volume parameterization.

---

## 9. Minimal Next Action

**Keep `min_hold=60` as production floor for Volume 250×0.90.** Route diagnostic attention to one of:

1. **val-gate recalibration on val_neg_pnl / val_low_wr** — these rejection classes dominate the A1 death curve regardless of min_hold, and were also the story behind the MR MIXED result in 421-3.
2. **Signal-generation / entry-filtering quality** — since the hold-mechanic branch of the explanation tree is now closed, the next dominant hypothesis is that entry quality (rank_window × entry_threshold interaction) has diminishing returns at the current best candidate and the remaining blocker lives upstream of exits.

Do **not** proceed with a `min_hold` sweep or any lower-floor deployment for this candidate.

---

## Artifacts (on Alaya)

- `/home/j13/j13-ops/zangetsu/results/min_hold_ablation_20260422_0741/commit.txt`
- `/home/j13/j13-ops/zangetsu/results/min_hold_ablation_20260422_0741/arm_{c60,b30,a15}/arm_{c60,b30,a15}.jsonl` — 140 rows each
- `.../smoke/smoke_m{60,30,15}.jsonl` — P2 preflight smoke (3 arms × 1 formula × 1 symbol)
- `.../report/cmp_c60_vs_b30.json` — full §12 metrics (C control, B candidate)
- `.../report/cmp_c60_vs_a15.json` — full §12 metrics (C control, A candidate)
- `.../report/final_report.md` — this report
- `.../logs/arm_{c60,b30,a15}.log` — full run logs
- `/tmp/min_hold_ablation_wrapper.py` — wrapper (zero production-source modification)
- `/tmp/doe_volume_l9.yaml` — DOE input (pre-existing, unchanged)

---

## Hard-Constraint Compliance Check

| # | Constraint | Status |
|---|---|---|
| 1 | No patch to trading logic | ✅ wrapper-only; css/backtester/alpha_signal source untouched |
| 2 | No schema / DB / telemetry-table modification | ✅ no DB writes altered; DB reads identical |
| 3 | No cost-model change | ✅ `per_symbol_CD03` used in all 3 arms |
| 4 | No threshold change except ALPHA_MIN_HOLD | ✅ rank_window=250, entry_thr=0.90, exit_thr=0.50 locked (wrapper overrides force identical values) |
| 5 | Single worker only | ✅ 3 arms ran strictly sequential in same shell session |
| 6 | No commit/formula-batch mixing | ✅ commit `f098ead5…` fixed; `/tmp/doe_volume_l9.yaml` identical across arms |
| 7 | Document A4/A5 hard-coded min_hold | ✅ noted in §2; bottleneck under investigation is A1 — experiment remains valid |
| 8 | Document nondeterminism if not locked | ✅ critical path deterministic (verified in 421-3 Recon R3, same codepath); no RNG present in evaluate path |

All 8 hard constraints satisfied.
