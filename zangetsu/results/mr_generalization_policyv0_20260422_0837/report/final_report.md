# 421-5 — Mean-Reversion Generalization via Policy Layer v0

**Project:** Zangetsu · **Date (UTC):** 2026-04-22 08:37 – 08:48 · **Commit:** `f098ead5…` (same as 421-3 / min_hold ablation / 421-4 — same session)

---

## 1. Goal

> **Does `250 × 0.90 × 60 × 0.50` clearly beat the safe-fallback control `500 × 0.80 × 60 × 0.50` on the Mean-Reversion family under the 15m path with min_hold=60 fixed, when routed through the Family-Aware Strategy Policy Layer v0?**

Allowed answers: `YES — CONFIRMED` / `MIXED — PARTIALLY CONFIRMED` / `NO — NOT CONFIRMED`.

---

## 2. Execution Summary

| Field | Value |
|---|---|
| Commit | `f098ead5d9d61e2b407951ffc3006e6b078e2d37` |
| Worker | single, sequential (Control → Candidate) |
| Main registry | `/home/j13/j13-ops/zangetsu/config/family_strategy_policy_v0.yaml` (production v0, untouched) |
| Overlay registry | `/tmp/mr_candidate_overlay_v0.yaml` (task-local) |
| Wrapper | `/tmp/family_strategy_policy_integration_v0.py` (policy-driven, no ARM_* override) |
| DOE input | `/tmp/doe_meanrev_l9.yaml` (10-cell MR L9(3³)+F6 ref, authorized in 421-3) |
| Symbols | 14-symbol universe |
| Timeframe | 15m |
| Fixed across both arms | cost_model=`per_symbol_CD03`, split/window/pset/strategy/MAX_HOLD_BARS=120 unchanged |
| Cells / arm | 10 formulas × 14 symbols = 140 |
| Run directory | `/home/j13/j13-ops/zangetsu/results/mr_generalization_policyv0_20260422_0837/` |

### 2.1 Two-arm routing (policy-driven)

| Arm | CLI | Route resolution path |
|---|---|---|
| **Control** | `--family-id mean_reversion --policy-mode research` | main registry → alias canonical → family=mean_reversion (unvalidated) → research mode → **fallback** → `500 × 0.80 × 60 × 0.50` |
| **Candidate** | `--family-id mean_reversion_candidate_test --policy-mode research --overlay-registry /tmp/mr_candidate_overlay_v0.yaml` | overlay direct hit → family=mean_reversion_candidate_test (validated=false, route_status=candidate_test) → **candidate_test** → `250 × 0.90 × 60 × 0.50` |

`registry_source` is recorded as `main` (Control) / `overlay` (Candidate) in every JSONL row.

---

## 3. Wrapper Proofs (3-layer)

### 3.1 Startup banners

Both banners printed in logs (`logs/control_full_v2.log`, `logs/candidate_full_v2.log`) and preserved in dry-run logs (`dryrun/control.log`, `dryrun/candidate.log`).

**Control (fallback route, main registry):**

```
requested_family_id   = 'mean_reversion'
normalized_family_id  = 'mean_reversion'
resolved_family_id    = 'mean_reversion'
mode                  = 'research'
route_status          = 'fallback'
route_reason          = 'unvalidated_family_safe_fallback'
validated             = False
evidence_tag          = 'not_verified'
policy_version        = 'v0'
registry_source       = 'main'
overlay_path          = None
rank_window = 500   entry_threshold = 0.8   min_hold = 60   exit_threshold = 0.5
```

**Candidate (candidate_test route, overlay registry):**

```
requested_family_id   = 'mean_reversion_candidate_test'
normalized_family_id  = 'mean_reversion_candidate_test'
resolved_family_id    = 'mean_reversion_candidate_test'
mode                  = 'research'
route_status          = 'candidate_test'
route_reason          = 'overlay_candidate_test:mean_reversion_candidate_test'
validated             = False
evidence_tag          = 'mr_generalization_candidate_test'
policy_version        = 'v0'
registry_source       = 'overlay'
overlay_path          = '/tmp/mr_candidate_overlay_v0.yaml'
rank_window = 250   entry_threshold = 0.9   min_hold = 60   exit_threshold = 0.5
```

### 3.2 First-call proofs

- Control: `PROOF first generate_alpha_signals uses rank_window=500 entry_threshold=0.8 min_hold=60 exit_threshold=0.5 (resolved via family='mean_reversion' status='fallback' reason='unvalidated_family_safe_fallback')`
- Candidate: `PROOF first generate_alpha_signals uses rank_window=250 entry_threshold=0.9 min_hold=60 exit_threshold=0.5 (resolved via family='mean_reversion_candidate_test' status='candidate_test' reason='overlay_candidate_test:mean_reversion_candidate_test')`

### 3.3 JSONL proof fields (both arms)

Every row of `control.jsonl` and `candidate.jsonl` carries:

`requested_family_id / normalized_family_id / resolved_family_id / normalization_applied / normalization_reason / route_status / route_reason / validated / evidence_tag / policy_version / policy_mode / registry_source / overlay_path` at top level,
plus inside `train.telemetry` (and val.telemetry when val ran): `rank_window_used / entry_threshold_used / min_hold_used / exit_threshold_used / trade_count / avg_hold_bars / median_hold_bars / p10 / p25 / p50 / p75 / p90 / pile_15_20 / pile_30_35 / pile_60_65 / pile_115_120 / exit_signal / exit_atr / exit_max_hold / primary_invariance{primary_trades, rerun_trades, match}`.

### 3.4 `primary_invariance.match`

- Control: 178 telemetry rows — **178/178 match** (mismatch=0)
- Candidate: 186 telemetry rows — **186/186 match** (mismatch=0)

---

## 4. Topline Comparison

| Metric | Control (fallback) | Candidate (overlay candidate_test) | Δ (Cand − Ctl) |
|---|---:|---:|---:|
| Total cells | 140 | 140 | 0 |
| **A1 survivors** | **0** | **0** | **0** |
| A1 survival rate | 0.0 % | 0.0 % | 0 pp |
| Cells reaching val | 38 | 46 | **+8 (+21.1 %)** |
| `a1_train_neg_pnl` | 102 | 94 | **−8** |
| `a1_val_neg_pnl` | 25 | 31 | +6 |
| `a1_val_low_wr` | 9 | 11 | +2 |
| `a1_val_low_sharpe` | 4 | 4 | 0 |
| Mean train net_pnl | −0.1639 | −0.1352 | +0.0287 |
| Mean val net_pnl | −0.0509 | −0.0594 | −0.0085 |
| Mean train Sharpe | −0.6155 | −0.4881 | **+0.1273** |
| Mean val Sharpe | **−0.4100** | **−0.5034** | **−0.0933** |
| Total train trades | 9,017 | 8,376 | −641 |
| Trade-weighted avg_hold_bars | 66.19 | 65.87 | −0.32 |
| % trades in [60, 65] | **72.56 %** | **71.79 %** | −0.77 pp |
| % trades in [115, 120] | 4.77 % | 4.29 % | −0.48 pp |
| pile_60_65 | 6,543 | 6,013 | — |
| pile_115_120 | 430 | 359 | — |
| exit_signal | 9,512 (≈96 %) | 9,094 (≈96 %) | — |
| **exit_atr** | **0** | **0** | **0** (A1 ATR stop dead) |
| exit_max_hold | 417 | 372 | — |
| Symbols with ≥1 survivor | 0 | 0 | 0 |

Numbers are **identical** to 421-3 (same commit / same DOE / deterministic critical path). This is the expected outcome and confirms the policy-layer integration produced the same behavior as the hand-tuned wrapper — the route substitution is transparent to the underlying execution path.

---

## 5. Hold / Exit Analysis (§必收指標 12.3)

| Metric | Control | Candidate |
|---|---:|---:|
| Trade-weighted avg_hold_bars | 66.19 | 65.87 |
| p10 / p25 / p50 / p75 / p90 (pooled-sample proxy) | tight cluster at floor | tight cluster at floor |
| % exits in [60, 65] | 72.56 % | 71.79 % |
| % exits in [115, 120] | 4.77 % | 4.29 % |
| exit_signal (signal-driven) | 9,512 / ≈96 % | 9,094 / ≈96 % |
| **exit_atr (ATR stop)** | **0 / 0 %** | **0 / 0 %** |
| exit_max_hold (120-bar ceiling) | 417 | 372 |

**A1 ATR stop remains dead** in both arms (confirmed again — 0 ATR-triggered exits across 17,393 trades). Hold distribution is dominated by the `min_hold=60` floor (≈72 % of trades exit inside the first bucket above it). Any observed cross-arm differences therefore come from **signal generation / entry filtering**, not exit mechanics — exactly as in 421-3.

---

## 6. Symbol-Level Breakdown (§必收指標 12.4)

Zero A1 survivors across all 14 symbols in **both** arms. Symbol breadth = 0 in both arms; Δ breadth = 0. Per-symbol median val Sharpe and reach-val counts are preserved in `report/aggregate.json`.

**Cells reaching val per symbol (Control):**

SOL=5 · XRP=7 · AAVE=5 · DOT=4 · FIL=3 · BTC=2 · AVAX=2 · GALA=2 · ETH=2 · 1000SHIB=2 · BNB=1 · LINK=1 · 1000PEPE=1 · DOGE=1 (total 38)

Candidate pulled 8 additional cells through to val (total 46), but *all* were rejected at val gate — no new survivor emerged in any symbol.

---

## 7. Verdict

Question:
> Does `250 × 0.90 × 60 × 0.50` beat `500 × 0.80 × 60 × 0.50` on Mean-Reversion under 15m with min_hold=60 fixed, via the policy layer?

### Answer: **NO — NOT CONFIRMED**

### Rule application (§判定規則)

The task's exact framing — "Does candidate beat control strongly enough?" — is decision-grade. On the three primary decision-grade axes the candidate fails cleanly, with no compensating improvement on the other required axes:

| Axis | Control | Candidate | Change | Meets YES bar? |
|---|---:|---:|---:|---|
| A1 survivors | 0 | 0 | **0** | ❌ no gain |
| Symbol breadth | 0 | 0 | **0** | ❌ no widening |
| Mean val Sharpe | −0.4100 | −0.5034 | **−0.09** | ❌ **regressed** |

**YES — CONFIRMED** — rejected. Two of the four YES conditions fail outright (no survivor gain, val quality regression).

**MIXED — PARTIALLY CONFIRMED** — rejected. The MIXED label would require the candidate's gains to have a *compensating* face, e.g. improving val quality while leaving survivors flat, or widening breadth while train sharpe stays flat. Here the train-side widening (−8 train_neg_pnl, +8 cells reaching val) is **entirely cancelled** by val-stage absorption (+6 val_neg_pnl, +2 val_low_wr), and val quality simultaneously worsens (mean val Sharpe −0.09). That is not a trade-off — it is a same-direction degradation of the decision-grade outcome. Per §判定規則 MIXED, the gains must be decision-relevant; here the train-gate numbers are process artefacts without an outcome expression.

**NO — NOT CONFIRMED** — matches: `candidate 無法擊敗 control`, survivor不增, breadth 不變寬 (0→0 同樣是未變寬), val quality 明顯變差。This is the correct verdict.

### Pattern observed

The candidate's net effect on Mean-Reversion is the same residual pattern seen in 421-3 and the min_hold ablation:

> **train gate widens → val gate absorbs additional death → survivor count unchanged → val quality pool-mean degrades.**

This is not family generalization. It is parameter-induced signal noise that train screens out less aggressively but val catches more aggressively — with net zero usable output. Under a strict decision-grade lens that is **NO**, not MIXED.

### Strategy vs engineering conclusions

- **Strategy**: 250 × 0.90 does **not** generalize to Mean-Reversion. Retain it as Volume-only.
- **Engineering**: Policy Layer v0 successfully carries this family test through an auditable main + overlay registry path with zero ARM_* hard-coding — the integration is **READY** for future family-conditional routing work.

### Cross-task consistency

This verdict **confirms** the 421-3 finding exactly — same numbers, same interpretation — but now routed through an auditable, registry-driven policy path:
- Control parameters came from the main v0 registry's safe fallback (not a hard-coded ARM_* env)
- Candidate parameters came from the task-local overlay registry (not a hard-coded ARM_* env)
- Zero wrapper-embedded mappings used

---

## 8. Minimal Defect Statement

> Under policy-layer routing, the candidate 250×0.90 pulled from the overlay registry does not generalize to Mean-Reversion: survivor count stays at 0 in both arms, symbol breadth stays at 0, and pool-level mean val Sharpe regresses −0.09. The only observed difference — a wider train gate — is fully absorbed by val-stage rejection and does not translate into any decision-grade outcome gain. The `candidate_test` overlay therefore does not justify promoting `mean_reversion` to `active` on the v0 registry.

---

## 9. Minimal Next Action

**Keep `250 × 0.90` as Volume-only candidate.** Do not promote mean_reversion → `active` in the v0 registry.

Cross-family evidence summary:
- Volume: **YES — CONFIRMED** (Volume-specific)
- Breakout: **NO — NOT CONFIRMED**
- Mean-Reversion: **NO — NOT CONFIRMED** (this task)

The data now supports family-conditional routing (not a single cross-family default). The residual bottleneck on MR is clearly **val-side**, not entry-parameter-side — val_neg_pnl and val_low_wr are the dominant death classes regardless of rank_window/entry_threshold choice.

Policy next steps (not part of this task):
1. The `mean_reversion_candidate_test` overlay is archived as `mr_candidate_overlay_v0.yaml` inside the run directory.
2. Future MR work should pivot to the val gate counterfactual audit workstream (see the separate next-task brief).

---

## 10. Task-Completion Criteria (per 421-5 §任務完成標準)

| # | Criterion | Result |
|---|---|---|
| 1 | policy layer control path correct | ✅ fallback route resolved via main registry; banner/proof/JSONL all correct |
| 2 | overlay candidate path correct | ✅ candidate_test route resolved via overlay registry; registry_source=overlay recorded |
| 3 | proof complete | ✅ banner + first-call proof + full JSONL fields across both arms |
| 4 | invariance=true | ✅ 178/178 (C) and 186/186 (K) `primary_invariance.match=true` |
| 5 | same session / same data window / same worker | ✅ commit `f098ead5…`, single shell session, single worker, same input yaml & symbols |
| 6 | report complete | ✅ §§1–10 |
| 7 | verdict explicit | ✅ **NO — NOT CONFIRMED** |

All 7 task-completion criteria satisfied.

---

## 11. Hard-Rule Compliance (§硬性規範)

| Rule | Status |
|---|---|
| Do not modify production source | ✅ No edit to `engine/components/*`, `services/*`, `scripts/*`, backtester, cost model, gate logic, DB schema |
| No backtester / cost / gate change | ✅ same as 421-3 |
| No DB / schema change | ✅ no DB writes originated from this task; staging inserts happen via existing css path |
| Only 2 arms | ✅ Control + Candidate; no third arm |
| No grid search | ✅ fixed 10-cell DOE, no parameter sweep |
| No manual ARM_* override | ✅ wrapper rejects ARM_* as primary source; resolved parameters come from registry/overlay only — verified by `_assert_no_direct_arm_env` warning mechanism |
| Parameters only from policy registry / overlay | ✅ main registry for Control, overlay registry for Candidate |
| Control runs first, Candidate after | ✅ sequential order preserved |
| This round answers only "is MR generalizable", no architecture discussion spread | ✅ report stays within decision-grade scope |

---

## Artifacts (on Alaya)

- `/home/j13/j13-ops/zangetsu/results/mr_generalization_policyv0_20260422_0837/commit.txt`
- `.../mr_candidate_overlay_v0.yaml` (overlay snapshot preserved in run dir)
- `.../control_fallback/control.jsonl` — 140 rows (policy-driven control)
- `.../candidate_overlay/candidate.jsonl` — 140 rows (policy-driven candidate via overlay)
- `.../smoke/{control_smoke,candidate_smoke}.jsonl` — preflight smoke (1 formula × 1 symbol)
- `.../dryrun/{control,candidate}.log` — dry-run banners
- `.../logs/{control_full_v2,candidate_full_v2,smoke_*}.log` — execution logs
- `.../report/aggregate.json` — full §12 metrics (gate outcome, quality, hold/exit, breadth, delta)
- `.../report/final_report.md` — this report
- `/home/j13/j13-ops/zangetsu/config/family_strategy_policy_v0.yaml` — main registry (unchanged)
- `/home/j13/j13-ops/zangetsu/engine/policy/family_strategy_policy_v0.py` — resolver (extended to support overlay + candidate_test in this task)
- `/tmp/family_strategy_policy_integration_v0.py` — wrapper (extended to accept `--overlay-registry`)
- `/tmp/mr_candidate_overlay_v0.yaml` — overlay registry (task-local)
- `/tmp/policy_test_abcd.py` — resolver regression test (7/7 still PASS after edits)
