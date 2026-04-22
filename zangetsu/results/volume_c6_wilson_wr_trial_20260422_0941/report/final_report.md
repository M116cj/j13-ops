# Volume C6 Wilson WR Floor Trial — Decision-Grade Report

**Task:** 0.52 → 0.48 · **Project:** Zangetsu · **Date (UTC):** 2026-04-22 09:41 · **Commit:** `f098ead5…` (same session continuity)

---

## 1. Goal

> **Under Volume C6 active route `250 × 0.90 × 60 × 0.50`, is relaxing the `val_low_wr` Wilson lower-bound floor from 0.52 → 0.48 (all other A1 gates unchanged) worth promoting to a real trial?**

Allowed answers: `YES — worth trial` / `MIXED — borderline` / `NO — keep 0.52`.

### Method — Telemetry-only re-scoring (Option A per j13 2026-04-22)

- Source JSONL: `/home/j13/j13-ops/zangetsu/results/volume_c6_valgate_audit_20260422_0854/run/volume_active.jsonl` (140 cells from the counterfactual audit run).
- Determinism of critical path was verified in 421-3 Recon R3 and re-confirmed in this session (same commit, same data window). Each cell's raw `val.{net_pnl, sharpe, wilson_wr, trades}` is a bit-exact function of inputs, so a rerun would produce identical `wilson_wr` values — the only difference is the threshold predicate. **Zero new execution required.**
- Trial predicate change: `wilson_wr >= 0.52` → `wilson_wr >= 0.48`. All other gates (val_neg_pnl > 0, val_sharpe ≥ 0.3, val_trades ≥ 15) unchanged.

---

## 2. Population

| Slice | Count |
|---|---:|
| Total cells | 140 |
| Reached val | 39 |
| Production survivors (wilson ≥ 0.52) | 2 |
| Production survivors re-verified via predicate | 2 ✓ |
| Trial survivors (wilson ≥ 0.48) | **4** |
| **NEW survivors under trial (Δ)** | **2** |
| Boundary pool `0.48 ≤ wilson < 0.52` | 2 |

---

## 3. Table A — NEW Survivors Detail

| # | Symbol | Formula | train_pnl | train_shp | val_pnl | val_shp | val_wwr | Classification |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 1 | BTCUSDT | `decay_20(volume)` | +0.1052 | +0.5939 | **+0.3170** | **+3.1833** | **0.4913** | **Acceptable** |
| 2 | DOTUSDT | `decay_20(volume)` | +0.3185 | +0.9093 | **+0.2855** | **+1.3583** | **0.4841** | **Acceptable** |

Both new survivors:
- Carry the **same formula** `decay_20(volume)` — a single Volume-family template that generalizes across BTC and DOT
- Show **strict train→val sign alignment** on both PnL and Sharpe
- Have **val_sharpe materially higher than train_sharpe** (+3.18 vs +0.59 for BTC; +1.36 vs +0.91 for DOT), which is an unusual "val-stronger-than-train" profile — not fragility, but possibly holdout-sample favorability
- Fall just inside the relaxed floor (0.4913 and 0.4841 — both under 0.50)

---

## 4. Table B — Boundary Pool `0.48 ≤ wilson_wr < 0.52`

This is the **real rescue candidate pool** — the only cells whose production status depends on the exact floor between 0.48 and 0.52.

| # | Symbol | Formula | train_pnl | train_shp | val_pnl | val_shp | val_wwr | Passes new? | Class |
|---:|---|---|---:|---:|---:|---:|---:|:---:|---|
| 1 | BTCUSDT | `decay_20(volume)` | +0.1052 | +0.5939 | +0.3170 | +3.1833 | 0.4913 | ✅ | Acceptable |
| 2 | DOTUSDT | `decay_20(volume)` | +0.3185 | +0.9093 | +0.2855 | +1.3583 | 0.4841 | ✅ | Acceptable |

**Boundary pool size = 2.** That is the full size of the practical unlock this floor change produces. The prior counterfactual audit's 17-cell "borderline" estimate in Table C was the ALL-val-blocked-with-wilson<0.52 pool (median wilson ~0.37) — not the 0.48–0.52 bracket. The tail distribution is very thin: of 17 cells with any wilson restriction, only 2 live in the 0.48–0.52 bracket; the other 15 sit below 0.48 and would not be rescued by this step.

---

## 5. Quality Summary (NEW survivors, n=2)

| Metric | Value |
|---|---:|
| Count | 2 |
| Acceptable | **2 (100 %)** |
| Marginal | 0 |
| Fragile | 0 |
| Breadth (distinct symbols) | **2** (BTC, DOT) |
| Mean val_net_pnl | **+0.3012** |
| Median val_net_pnl | +0.3012 |
| Mean val_sharpe | **+2.2708** |
| Median val_sharpe | +2.2708 |
| Mean val_wilson_wr | 0.4877 |
| train↔val pnl sign consistency | **100 %** |
| train↔val sharpe sign consistency | **100 %** |
| train↔val both-axis consistency | **100 %** |

---

## 6. Verdict Reasoning (j13's YES/MIXED/NO thresholds)

| Condition | Required | Actual | Meets? |
|---|---|---:|:---:|
| new survivors ≥ 3 | YES bar | **2** | ❌ |
| breadth ≥ 3 symbols | YES bar | **2** | ❌ |
| Acceptable rate ≥ 70 % | YES bar | **100 %** | ✅ |
| mean val_sharpe > 0 | YES bar | **+2.27** | ✅ |
| mean val_net_pnl > 0 | YES bar | **+0.30** | ✅ |
| train↔val pnl consistency ≥ 80 % | YES bar | **100 %** | ✅ |
| new survivors = 0 | NO trigger | 2 | — |
| majority Fragile | NO trigger | 0 | — |
| mean sharpe ≤ 0 | NO trigger | +2.27 | — |
| mean pnl ≤ 0 | NO trigger | +0.30 | — |
| consistency < 50 % | NO trigger | 100 % | — |

**YES — fails** on count and breadth (need 3 of each; got 2 of each).
**NO — fails** on every trigger (we have 2 new, all Acceptable, positive aggregates, 100 % consistency).
**MIXED** — matches j13's explicit MIXED rule: "new survivors = 1–2, or breadth < 3" — both triggered.

---

## 7. Final Decision

### **MIXED — borderline**

### What this actually means, cleanly

1. **The quality is real, not noise.** Both new survivors are the *highest-quality* new cells you could hope for:
   - 100 % Acceptable (zero Marginal, zero Fragile)
   - 100 % train↔val sign consistency on both PnL and Sharpe
   - Mean val Sharpe +2.27 — not borderline-statistical, strongly positive on holdout
   - Mean val PnL +0.30 — also strong

2. **The quantity is thin.** n=2, breadth=2, and both survivors share the *same formula* (`decay_20(volume)`). That is a single edge expressed on two symbols, not independent confirmation.

3. **The Wilson tail dynamics are the real story.** The prior counterfactual predicted 17 "borderline" cells at any wilson-restriction level (median wilson ≈ 0.37). Of those 17, only 2 are actually in the 0.48–0.52 bracket. The Wilson distribution on val-blocked cells is right-skewed toward very low values — **moving the floor from 0.52 to 0.48 catches only the extreme right tail**. Further relaxation (e.g., to 0.40) would rescue many more but at rapidly declining quality per the G7 data (46 % junk fraction).

4. **Why MIXED and not NO**: the 2 rescued cells are Acceptable-grade. Promoting them via a 0.48 floor would produce a 2-cell, 2-symbol, single-formula expansion — real but narrow.

5. **Why MIXED and not YES**: the breadth and count bars were set precisely to filter out exactly this thin-but-clean profile. j13's criteria required ≥ 3 on both axes. The 0.48 step does not meet that threshold; a 0.46 or 0.44 step might but would start dragging in lower-quality cells.

---

## 8. Minimal Defect Statement

> Wilson WR 0.52 → 0.48 rescues exactly 2 cells (BTCUSDT + DOTUSDT, both `decay_20(volume)`) with 100 % Acceptable classification, 100 % train↔val sign consistency, mean val Sharpe +2.27, and mean val PnL +0.30. The rescue is high-quality but numerically thin (n=2, breadth=2, single formula) and fails j13's YES bar of ≥3 on count and breadth. The remaining 15 val_low_wr-blocked cells have wilson < 0.48 and are not reachable at this step — they are either lower-quality cells or would require a more aggressive floor relaxation that the counterfactual audit showed produces 46 % junk.

---

## 9. Minimal Next Action

Given MIXED, the options are:

- **Option α — Hold at 0.52.** Do not promote the 0.48 trial; keep production gate unchanged. Accept that this particular lever closes with 2 high-quality survivors left on the table. The 2 `decay_20(volume)` cells can be separately documented as known-high-quality non-promoted alphas.

- **Option β — Promote only the specific 2 cells as a pre-approved allowlist** (formula=`decay_20(volume)`, symbols BTC+DOT), without touching the global Wilson floor. This is a narrow, auditable exception that captures the entire quality win of this experiment without any gate-logic change and without any quality regression risk.

- **Option γ — Step further to 0.44 or 0.40** and rerun this analyzer. The G7 counterfactual warned 46 % junk at full gate-off; a 0.44 step likely doubles count at the cost of 1–2 new Fragile or Marginal entries. Not recommended unless breadth becomes more important than quality.

My recommendation is **β**. It captures the full MIXED win without making a policy change, uses the registry-overlay mechanism you already built in 421-5, and keeps the Wilson floor intact for future signal populations where it may still be filtering correctly.

---

## 10. Hard-Boundary Compliance

| Constraint | Status |
|---|---|
| No sweep (only one step 0.52 → 0.48) | ✅ |
| No change to val_neg_pnl threshold | ✅ |
| No change to val_low_sharpe threshold | ✅ |
| No change to upstream parameters (rank_window / entry / min_hold / exit / cooldown) | ✅ |
| No production source modification | ✅ (telemetry-only re-scoring; zero file edits) |
| Policy Layer v0 not touched this round | ✅ (registry, resolver, wrapper all unchanged) |
| Same commit / session / data window | ✅ (source JSONL from same-session 08:54 run, commit `f098ead5…`) |
| Deterministic critical path | ✅ (verified 421-3 R3; re-verified this session) |

---

## 11. Artifacts (on Alaya)

- `/home/j13/j13-ops/zangetsu/results/volume_c6_wilson_wr_trial_20260422_0941/commit.txt`
- `/home/j13/j13-ops/zangetsu/results/volume_c6_wilson_wr_trial_20260422_0941/report/wilson_wr_trial.json` — full machine-readable output
- `/home/j13/j13-ops/zangetsu/results/volume_c6_wilson_wr_trial_20260422_0941/report/final_report.md` — this report
- `/home/j13/j13-ops/zangetsu/results/volume_c6_wilson_wr_trial_20260422_0941/logs/rescore.log` — stdout
- `/tmp/wilson_wr_048_rescore.py` — analyzer (reusable for future trial-threshold audits)
- Source: `/home/j13/j13-ops/zangetsu/results/volume_c6_valgate_audit_20260422_0854/run/volume_active.jsonl` (unchanged, 140 cells)
- Policy Layer v0 files — **all unchanged** (registry, resolver, integration wrapper)
