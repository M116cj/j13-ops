# 00 — Strategic Redesign Decision Matrix

**Master Order:** 0-9Y-FINAL-ZANGETSU-ALPHA-EDGE-RESTORATION-PROGRAM
**Sub-order:** TEAM ORDER 0-9Y-D-STRATEGIC-REDESIGN-DECISION
**Phase:** 1
**Date (UTC):** 2026-04-28T02:55Z

## Inputs from FINAL-0 (carry-forward from 0-9Y-C verdict `DECOMPOSED_GROSS_EDGE_LOST_TO_COST`)

| Anchor | Value |
|---|---|
| `train_gross_pnl_median` | +2.46 bps |
| `train_gross_minus_net_median` (cost charged) | +3.60 bps |
| `train_net_pnl_median` | -1.33 bps |
| `cost / gross` ratio | 1.54× |
| Edge gap to breakeven | 1.32 bps short |
| `train_win_rate_median` | 0.32 (max 0.494) |
| `train_total_trades_median` | 989 |
| `signal_density_per_bar` | 0.00702 |
| Truly tradeable batches | 1.9 % (2/106) |
| Cohort uniformity | 0/14 cells with median(gross) > median(cost) |
| Train→val divergence | none (both negative when val ran) |

## Scoring rubric

For each path, evaluate seven dimensions on a 1–5 scale (5 = best). The combined score is the weighted average; the recommended default selects the **highest-score combination achievable in parallel**.

| Dimension | Weight | What it captures |
|---|---|---|
| Expected edge improvement | 30 % | Probability of moving net from −1.33 bps toward breakeven |
| Implementation time | 15 % | Faster = better (pipeline change vs new data infra) |
| Governance risk | 15 % | Forbidden-ops surface (validator / cost / promotion change risk) |
| Data requirement | 10 % | Marginal data infra cost (already-available > new fetch) |
| Validation compatibility | 10 % | Whether existing A1/A2/A3/A4 gates still apply |
| Artifact risk | 10 % | Risk of SINGLE_SYMBOL_ARTIFACT or overfit alphas surviving |
| Chance to restore deployables | 10 % | Probability that this path alone produces `deployable_count > 0` |

## Path-by-path analysis

### Path A — Target / Horizon Redesign

| Dimension | Score (1–5) | Rationale |
|---|---|---|
| Expected edge improvement | **4** | Larger horizon (180–360 bars) typically increases per-trade gross by 3–6× empirically (Lin & Han 2024 crypto multi-horizon studies; carry: gross 2.46 bps × 3–6 = 7–15 bps would beat 3.6 bps cost) |
| Implementation time | **4** | Plumbing-level change to label function + telemetry; ~1–2 hours code; no new data |
| Governance risk | **4** | Touches `target_label` + `BacktestResult` plumbing only; validator unchanged; cost unchanged |
| Data requirement | **5** | Existing 1m K-line data already loaded (140k bars); no new fetch |
| Validation compatibility | **5** | A1/A2/A3/A4 gates unchanged; trade count semantics unchanged |
| Artifact risk | **3** | Longer horizon may surface symbol-specific carry effects; need cohort-uniformity audit per horizon |
| Chance to restore deployables | **3** | Necessary but possibly not sufficient; if pure target change isn't enough, fall through to B/C |
| **Weighted score** | **3.95** | strongest single-path candidate |

### Path B — Feature-Space Expansion

| Dimension | Score (1–5) | Rationale |
|---|---|---|
| Expected edge improvement | **4** | Cross-asset / regime / vol-normalized features can lift WR from 0.32 toward 0.40+; high-impact but requires search-space redesign |
| Implementation time | **2** | Adding new operators / primitive features = multi-day code; new feature builders + GP operator wiring |
| Governance risk | **3** | Touches `alpha_engine.AlphaEngine.__init__` operator set; must ensure no fitness leak into engine (engine CLAUDE.md hard rule §2) |
| Data requirement | **3** | Some features (cross-asset) need symbol-pair data alignment; available but adds load |
| Validation compatibility | **4** | A1/A2/A3/A4 still apply |
| Artifact risk | **3** | Larger feature space increases overfit risk if fewer-trade alphas survive |
| Chance to restore deployables | **3** | Depends on which features are added; cross-asset highest probability |
| **Weighted score** | **3.20** | strong second candidate |

### Path C — Trade-Frequency / Signal Aggregation

| Dimension | Score (1–5) | Rationale |
|---|---|---|
| Expected edge improvement | **3** | 0-9Y-C Phase 5 inverse density-vs-net correlation (sparser quartile: net −0.29 vs Q3's −1.75) implies fewer-stronger trades reduce cost burn; but does not raise gross-per-trade |
| Implementation time | **3** | Diagnosis is read-only and quick; aggregation prototype is medium-effort |
| Governance risk | **5** | Read-only diagnosis has zero source-touch surface; aggregation prototype touches signal layer only |
| Data requirement | **5** | Existing telemetry sufficient |
| Validation compatibility | **5** | A1/A2/A3/A4 unchanged; A2_MIN_TRADES=25 unchanged |
| Artifact risk | **4** | Aggregating high-confidence signals naturally reduces low-conviction-trade noise; lower artifact risk |
| Chance to restore deployables | **2** | Likely improves edge but rarely sufficient alone — best paired with Path A |
| **Weighted score** | **3.65** | strong complementary path; best paired with A |

### Path D — Alpha Zoo Dry-Run (later optional)

| Dimension | Score (1–5) | Rationale |
|---|---|---|
| Expected edge improvement | **3** | External formulas may have signal families not in current GP search; uncertain |
| Implementation time | **3** | Dry-run / inspect-only path likely already partially built; medium effort to wire to current schema |
| Governance risk | **2** | Master order: must remain inspect-only / dry-run / no DB write; alpha_zoo write-guard is an explicit BLOCKED constraint |
| Data requirement | **4** | External formulas → still need to evaluate against current 1m K-line data |
| Validation compatibility | **4** | A1/A2/A3/A4 still apply if dry-run output passes through them |
| Artifact risk | **3** | External formulas may carry their own overfit risk |
| Chance to restore deployables | **2** | Diagnostic ; not a primary deployable-flow restorer |
| **Weighted score** | **2.85** | optional; lower-priority |

### Path E — Microstructure / Orderbook (later optional)

| Dimension | Score (1–5) | Rationale |
|---|---|---|
| Expected edge improvement | **5** | Real edge often lives in orderbook flow / tick microstructure; highest theoretical ceiling |
| Implementation time | **1** | New data pipeline (orderbook subscription + storage + bar alignment); multi-week to multi-month |
| Governance risk | **3** | Major data infra; needs new schema; risk of leak if not carefully designed |
| Data requirement | **1** | Substantial new data fetch / storage; cost-significant |
| Validation compatibility | **3** | New features may need new gates or threshold review |
| Artifact risk | **3** | Microstructure overfitting is a known pitfall |
| Chance to restore deployables | **4** | If executed correctly, high ceiling — but requires resources beyond current scope |
| **Weighted score** | **2.65** | strategic; do not attempt before A/B/C exhausted |

## Combined-path candidates

| Combination | Combined score | Implementation feasibility |
|---|---|---|
| **A + C** | 3.80 (avg) | both quick, complementary, address different sides of cost/gross gap |
| A + B | 3.58 | strong but slower (B is multi-day); deferred to post-checkpoint |
| A only | 3.95 | strongest single but may be insufficient |
| C only | 3.65 | unlikely sufficient alone |
| B only | 3.20 | slow; deferred |
| D / E | <3.0 | optional / future |

## Recommended default (per master order spec)

Path A + Path C, executed in parallel:
- A handles **gross-per-trade** axis (target/horizon redesign 180/240/360)
- C handles **cost-burn** axis (trade-frequency diagnostic; aggregation prototype if positive)

This addresses both sides of the `cost/gross > 1` problem identified in 0-9Y-C. Path B remains a deferrable follow-up if the j13 Phase-8 checkpoint judges horizon-only insufficient.

## STOP-condition evaluation

| STOP condition | Triggered? |
|---|---|
| baseline drift | NO — FINAL-0 confirmed match |
| forbidden modification | NO — decision is docs-only |
| insufficient evidence to choose | NO — 0-9Y-C provides a clear directional finding (gross > 0, cost > gross, WR ≤ 50 %, density ample) |

**No STOP. Proceed to Phase 2 (TEAM ORDER 0-9Y-HE0-HORIZON-TARGET-DESIGN-SPEC).**
