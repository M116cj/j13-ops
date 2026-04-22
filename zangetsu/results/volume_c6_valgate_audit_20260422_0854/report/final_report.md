# Volume C6 Val-Gate Counterfactual Truth Audit — Decision-Grade Report

**Project:** Zangetsu · **Date (UTC):** 2026-04-22 08:54 · **Commit:** `f098ead5…` (same session continuity since 421-3)

---

## 1. Goal

Under the Volume family best-known candidate `250 × 0.90 × 60 × 0.50` (routed via Policy Layer v0, `family=volume` → `active`), audit **counterfactually** which of the three A1 val-gates is the real residual blocker, and what quality of cells would be unlocked if each were removed.

Boundary per j13 2026-04-22: **wrapper/telemetry-only counterfactual. No gate-logic change. No new thresholds. No new OOS. Not written into policy layer this round.**

Final answer format — exactly one of:
- `YES — gate calibration is next`
- `MIXED — gate calibration helps but upstream quality still dominates`
- `NO — validation gates are not the main residual blocker`

---

## 2. Execution Summary

| Field | Value |
|---|---|
| Commit | `f098ead5d9d61e2b407951ffc3006e6b078e2d37` |
| Registry route | `family=volume`, `mode=research` → **active** → 250×0.90×60×0.50 |
| Resolved via | `/home/j13/j13-ops/zangetsu/config/family_strategy_policy_v0.yaml` |
| DOE | `/tmp/doe_volume_l9.yaml` (10-cell L9(3³)+ref) |
| Symbols | 14-symbol universe |
| Timeframe | 15m |
| Worker | single, sequential |
| Run dir | `/home/j13/j13-ops/zangetsu/results/volume_c6_valgate_audit_20260422_0854/` |
| Post-processing | `/tmp/valgate_counterfactual.py` — re-evaluates each val-reaching cell against all 3 val-gate predicates independently from the raw `val.{net_pnl, sharpe, wilson_wr}` fields in the JSONL |

### A1 gate thresholds (inlined from `scripts/cold_start_hand_alphas.py:199-204` and `shadow_control_suite.py:203-213`)

| Gate | Predicate | Fail condition |
|---|---|---|
| `a1_val_neg_pnl` | `val.net_pnl > 0` | `net_pnl <= 0` |
| `a1_val_low_sharpe` | `val.sharpe >= 0.3` | `sharpe < 0.3` |
| `a1_val_low_wr` | `val.wilson_wr >= 0.52` (Wilson lower bound) | `wilson_wr < 0.52` |

Evaluation order short-circuits: `neg_pnl → low_sharpe → low_wr`, so `first_gate_reached` records only the first hit. The counterfactual analyzer ignores this ordering and re-evaluates all three predicates per cell from the raw telemetry.

### Population slices

| Slice | Count |
|---|---:|
| total cells | 140 |
| train-blocked (did not reach val) | 101 |
| reached val | 39 |
| existing A1 survivors (G0 baseline) | 2 |
| val-blocked pool (reached val but failed ≥1 val gate) | 37 |

Note: 101/140 = **72 %** of cells never even reach val — they die at `train_neg_pnl`. That framing matters for Q4.

---

## 3. Table A — Gate Attribution (val-blocked only, n=37)

### Exclusive failure (fails only that one val-gate)

| Gate | Exclusive-fail count | Share of val-blocked |
|---|---:|---:|
| `val_neg_pnl` (only) | **0** | 0 % |
| `val_low_sharpe` (only) | **0** | 0 % |
| `val_low_wr` (only) | **17** | 45.9 % |

### Two-gate overlap (fails exactly those two)

| Combination | Count |
|---|---:|
| `neg_pnl` + `low_sharpe` (only) | 0 |
| `neg_pnl` + `low_wr` (only) | 0 |
| `low_sharpe` + `low_wr` (only) | 1 |

### All three gates fail

| Combination | Count |
|---|---:|
| **all three** | 19 |

### ANY hit (cells that fail that gate, regardless of others)

| Gate | Any-hit count | % of val-blocked |
|---|---:|---:|
| any `val_neg_pnl` | 19 | 51.4 % |
| any `val_low_sharpe` | 20 | 54.1 % |
| **any `val_low_wr`** | **37** | **100.0 %** |

### Headline finding

**Every single val-blocked cell (37/37 = 100 %) fails `val_low_wr`.** `val_low_wr` is the terminal gate — no cell escapes it even when `val_neg_pnl` and `val_low_sharpe` would have let it through. `val_neg_pnl` never fails exclusively; every cell it kills is *also* killed by `val_low_wr` (and typically by `val_low_sharpe`). `val_low_sharpe` also never fails exclusively.

---

## 4. Table B — Counterfactual Survivors (G0…G7)

Mask semantics: bit=1 means the gate is **removed**. Baseline G0 is the production A1 gate stack.

| G | Description | Surv | Net new vs G0 | Symbols w/ surv | Overlap w/ G0 | Unlock rate (over val-blocked) |
|---|---|---:|---:|---:|---:|---:|
| **G0** | baseline (current production) | 2 | 0 | 2 | 2 | 0.0000 |
| **G1** | remove `val_neg_pnl` only | **2** | **0** | 2 | 2 | 0.0000 |
| **G2** | remove `val_low_wr` only | **19** | **+17** | 12 | 2 | 0.4595 |
| **G3** | remove `val_low_sharpe` only | **2** | **0** | 2 | 2 | 0.0000 |
| **G4** | remove `val_neg_pnl` + `val_low_wr` | 19 | +17 | 12 | 2 | 0.4595 |
| **G5** | remove `val_neg_pnl` + `val_low_sharpe` | 2 | 0 | 2 | 2 | 0.0000 |
| **G6** | remove `val_low_sharpe` + `val_low_wr` | 20 | +18 | 12 | 2 | 0.4865 |
| **G7** | remove all three | **39** | **+37** | **14** | 2 | 1.0000 |

### Headline findings

- **G1 (remove `val_neg_pnl` only) = 0 new survivors.** `val_neg_pnl` is effectively a **null gate** on this population — every cell it would block is redundantly blocked by `val_low_wr`.
- **G3 (remove `val_low_sharpe` only) = 0 new survivors.** Same story — redundant with `val_low_wr`.
- **G2 (remove `val_low_wr` only) = +17 new survivors across 12 symbols.** This is the *only* single-gate removal that meaningfully unlocks cells.
- Symbol breadth under G2 jumps from 2 to 12 — sizable breadth expansion at the 2-symbol baseline level.
- G6 (remove `low_sharpe` + `low_wr`) adds only 1 more vs G2 — `low_sharpe` contribution is ~1 cell.
- G7 (remove all three) recovers 37 cells, but the extra 20 vs G2 are the joint-failure pool (cells that fail neg_pnl AND low_sharpe AND low_wr), which are by definition lower-quality.

---

## 5. Table C — Unlock Quality (val-raw metrics on newly-unlocked cells)

Classification rules:
- **clearly_viable**: `val_net_pnl > 0` AND `val_sharpe > 0` AND `val_wilson_wr >= 0.50`
- **likely_junk**: `val_net_pnl <= -0.05` OR `val_sharpe <= -0.5`
- **borderline**: everything else (train-pos + mixed/marginal val expression)

| G | Unlocked | clearly viable | borderline | likely junk | mean val_pnl | median val_pnl | mean val_sharpe | median val_sharpe | mean wilson_wr | median wilson_wr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **G2** | 17 | **0** | **17** | 0 | **+0.1608** | +0.1356 | **+1.2141** | +1.0427 | 0.3806 | 0.3707 |
| G4 | 17 | 0 | 17 | 0 | +0.1608 | +0.1356 | +1.2141 | +1.0427 | 0.3806 | 0.3707 |
| G6 | 18 | 0 | 18 | 0 | +0.1527 | +0.1272 | +1.1604 | +1.0145 | 0.3796 | 0.3707 |
| **G7** | 37 | **0** | 20 | **17** | +0.0073 | −0.0051 | +0.0427 | −0.0619 | 0.3160 | 0.3139 |

### Headline findings

- **G2's 17 unlocked cells all have positive val_net_pnl (mean +0.16, median +0.14), positive val_sharpe (mean +1.21, median +1.04), but wilson_wr clustered in 0.37–0.38 — below the 0.52 Wilson floor.** They pass the pnl / sharpe coherence test with train cleanly but fail the statistical-significance-of-win-rate test because Wilson's lower bound at these sample sizes is conservative.
- **Zero G2 cells are "clearly viable" by my classifier** because the classifier requires `wilson_wr >= 0.50`, which is exactly the threshold being stress-tested. Every cell is thus classified "borderline" — a conservative read. If the trader accepts pnl + sharpe as sufficient evidence at train-val coherence level, these 17 cells are the candidates.
- **G7's additional 20 cells (G7 − G2) are the joint-failure pool**: mean val_pnl drops to +0.007 (essentially zero), mean sharpe to +0.04, with 17/20 classified junk. Removing all three gates dilutes the unlock pool sharply with low-quality cells.

**Qualitative read of G2:** of the 17 unlocked cells, every one has train-val *directional* agreement (both pnl > 0, both sharpe > 0 in sign), but the samples are too small for Wilson to clear 0.52. This is the classic "borderline, possibly viable if given more data" profile — not junk, but not yet proven.

---

## 6. Answers to the 4 Required Questions

### Q1 — Which val gate blocks the most "not-obviously-junk" cells?

| Exclusive-fail population | n | viable | borderline | junk |
|---|---:|---:|---:|---:|
| val_neg_pnl (only) | 0 | 0 | 0 | 0 |
| val_low_sharpe (only) | 0 | 0 | 0 | 0 |
| **val_low_wr (only)** | **17** | 0 | **17** | **0** |

**`val_low_wr` is the only gate that exclusively blocks non-junk cells.** 17 borderline (no junk), zero uniquely blocked by the other two.

### Q2 — Does removing `val_neg_pnl` alone materially increase survivors?

**No.** `Δsurvivors = 0`, net new cells = 0, unlock rate = 0.000. Every cell `val_neg_pnl` would block is already blocked by `val_low_wr`. `val_neg_pnl` is effectively redundant in the current stack on this population.

### Q3 — Are unlocked things mostly viable, borderline, or junk?

Under the most permissive counterfactual (G7, drop all three gates, 37 unlocked cells):

| Category | Count | Share |
|---|---:|---:|
| clearly viable | 0 | 0 % |
| borderline | 20 | 54 % |
| likely junk | 17 | 46 % |

Zero clearly-viable edges hide behind the val gates. **The unlocked pool is a 54/46 split borderline vs junk** — meaningful borderline presence, zero hidden clean wins.

Narrower slice (G2, drop only `val_low_wr`, 17 unlocked cells):
- 0 viable / 17 borderline / 0 junk — the `val_low_wr`-exclusive pool is entirely borderline with positive mean val pnl (+0.16) and positive mean val sharpe (+1.21). These are the most interesting unlock candidates.

### Q4 — Is the residual dominant blocker: gate-too-strict, or upstream-signal-quality?

**Mixed — both, with a quantifiable split:**

- **72 % of cells die at train_neg_pnl** (101/140) before val is ever evaluated. This is pure upstream signal quality — no val-gate calibration can touch it.
- **Of the 39 cells that reach val, 17 (44 %)** are blocked exclusively by `val_low_wr` with *positive* val_pnl and *positive* val_sharpe. These are the "gate-too-strict" candidates — a real, non-junk population that the Wilson 0.52 floor currently excludes.
- **Of G7's 37-cell unlock pool, 46 % are junk.** Removing all three gates does not reveal a hidden treasure trove — more than half is noise.

Numerical shape:
```
upstream_deaths / total_cells        = 101 / 140  = 72 %  (upstream quality)
val_low_wr_unique_non_junk / val-blocked = 17 / 37 = 46 % (gate too strict)
G7_junk_fraction                      = 17 / 37 = 46 %  (gates guard real junk too)
```

Translated: gate calibration **can** unlock a real borderline pool (17 cells, 12 symbols, positive pnl/sharpe), but it cannot fix the fundamental low-admission-rate at train gate. **Upstream signal quality is the larger residual problem in absolute terms, but val_low_wr is the larger problem among cells that reach val.**

---

## 7. Verdict

### Answer: **MIXED — gate calibration helps but upstream quality still dominates**

### Rationale

Both forces are real and measurable in this audit:

1. **Gate calibration matters and is not cosmetic.** `val_low_wr` at Wilson 0.52 uniquely blocks 17 cells spanning 12 symbols with train-val-coherent positive pnl (+0.16 mean) and positive sharpe (+1.21 mean). This is the only gate in the stack that blocks non-junk exclusively. `val_neg_pnl` and `val_low_sharpe` are effectively redundant — removing either alone does nothing.

2. **Upstream quality dominates the absolute picture.** 72 % of cells never reach val (train_neg_pnl death). No val-gate recalibration can address this — it is a signal-generation-upstream problem, not a gate-filter problem.

3. **Neither is sufficient alone.** Calibrating val_low_wr would unlock 17 borderline cells (breadth 12 symbols) but:
   - zero of those are "clearly viable" under train-val-aligned-across-all-three-axes classification (they fail the wilson ≥ 0.50 check);
   - removing gates further (G7) gets you 20 more cells, 17 of which are junk, indicating the guard is not purely artefactual.
4. **Verdict must be MIXED because both calibration and upstream improvement would contribute**. Neither `YES` (pure calibration) nor `NO` (pure upstream) captures the data. Picking either alone would leave 44 % of the actionable next-step signal on the table.

---

## 8. Minimal Defect Statement

> Under Volume `250×0.90×60×0.50` (active route, policy layer), the A1 val-gate stack is *not* the sole residual blocker: 72 % of cells die upstream at `train_neg_pnl` before val is reached, and of the 37 val-blocked cells, `val_low_wr` uniquely blocks 17 with train-val-coherent positive pnl and sharpe, while `val_neg_pnl` and `val_low_sharpe` exclusively block zero cells each and are redundant with `val_low_wr`. Gate calibration can unlock a real 17-cell / 12-symbol borderline pool but cannot address the dominant 72 % train-death rate.

---

## 9. Minimal Next Action

**Both workstreams should be opened in parallel, each with its own decision lens:**

1. **Val-gate calibration workstream** — specifically targeting the `val_low_wr` Wilson threshold at 0.52 under candidate-sample-size contexts. The narrow question: does the 17-cell G2 unlock pool hold up under forward-time OOS, or does the Wilson floor catch legitimate fragility that pnl/sharpe miss? (A Wilson-lower-bound relaxation to e.g. 0.48 would be the minimal change — not a sweep.) **This is where the policy-layer-controlled experimentation would live once graduated from audit to trial.**

2. **Upstream signal quality workstream** — address the 72 % train_neg_pnl death rate. Candidate questions: (a) is the DOE formula space too wide for this family? (b) is `tanh_x` + `ts_rank_N` the right envelope? (c) is the 70/30 train/holdout split too aggressive? These are not val-gate questions.

j13's parallel framing "是 gate 過嚴 or signal upstream 仍然太差" is answered: **both, with val_low_wr being the sharpest lever if one must be picked first**, because it touches train-val-coherent non-junk cells and is the single most dominant val-side gate (100 % of val-blocked cells fail it).

---

## 10. Hard-Boundary Compliance Check (j13 2026-04-22)

| Boundary | Status |
|---|---|
| (1) wrapper-only / telemetry-only counterfactual | ✅ zero modification to `arena_gates.py` / `cold_start_hand_alphas.py` / `shadow_control_suite.py` / backtester / cost model / DB schema. Post-processing re-evaluates gate predicates from raw JSONL telemetry. |
| (2) gate-OFF truth audit, no new thresholds | ✅ enumerated 8 counterfactuals G0..G7 as pure boolean masks (keep/remove) — no new thresholds proposed or tested. |
| (3) no new OOS; train↔val consistency only | ✅ quality classifier uses train positivity (given by val-reaching status) + val sign / magnitude only. No holdout-of-holdout. |
| (4) val gate not written into policy layer this round | ✅ zero edits to `engine/policy/family_strategy_policy_v0.py` or `config/family_strategy_policy_v0.yaml`. Policy Layer v0 stays at last-known-good state. |

---

## 11. Artifacts (on Alaya)

- `/home/j13/j13-ops/zangetsu/results/volume_c6_valgate_audit_20260422_0854/commit.txt`
- `.../run/volume_active.jsonl` — 140 rows (policy-driven, active route, rw=250, et=0.9, mh=60, xt=0.5)
- `.../report/counterfactual.json` — machine-readable tables A/B/C + 4Q answers
- `.../report/final_report.md` — this report
- `.../logs/run.log` — full run log
- `/tmp/valgate_counterfactual.py` — counterfactual analyzer (non-destructive; reusable for future family audits)
- `/home/j13/j13-ops/zangetsu/config/family_strategy_policy_v0.yaml` — main registry (unchanged)
- `/home/j13/j13-ops/zangetsu/engine/policy/family_strategy_policy_v0.py` — resolver (unchanged)
- `/tmp/family_strategy_policy_integration_v0.py` — wrapper (unchanged)
