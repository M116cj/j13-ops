# 06 — Recommended Candidate Selection

## 1. Synthesizing Phases 1-5

| Phase | Verdict | Implication for next order |
| --- | --- | --- |
| 1 — Inventory | 71 survivors total; 8 at cost=0.5x all SOL; 0 at cost=1.0x | calibration window exists but is narrow |
| 2 — Economic realism | cost=0.5x is OPTIMISTIC_BUT_PLAUSIBLE; current cost is realistic for taker-only execution; needs execution-mode split | model abstraction is too crude; can't go lower without measurement |
| 3 — Survivor robustness | 8/8 = SINGLE_SYMBOL_ARTIFACT; ALL train-val divergent | none of the surviving cells are actually promotable |
| 4 — Calibration risk | HIGH_RISK + BLOCKED; 5 HIGH-severity blockers | a global cost change is unsafe right now |
| 5 — Options | A REJECT, B/C/D defer, E + F recommended, G parallel track | calibration implementation is NOT the next step |

## 2. Decision Logic

| Allowed recommendation | Triggered by | Conclusion |
| --- | --- | --- |
| R1 — Proceed to controlled dry-run calibration implementation | survivors are robust + cost=0.5x economically realistic | NO (Phase 3 + Phase 4 reject) |
| R2 — Do not implement; expand calibration evidence first | survivor evidence is narrow | partial — Option F supports this |
| **R3 — Do not lower cost globally; implement execution-mode-aware cost model** | cost reduction requires execution split | partial — but execution-mode model alone without observation is inert |
| R4 — Do not calibrate; formula universe remains too weak | Phase 8 H7 (universe weakness) is medium-confidence | yes — Option E supports this |
| **R5 — Do not calibrate; survivor evidence is single-symbol artifact** | 8/8 SINGLE_SYMBOL_ARTIFACT classification | **YES — strongest evidence** |
| R6 — Implement only offline validator harness improvement | gates need tightening before re-running matrix | yes — combined-sharpe + multi-symbol gates needed |

## 3. Primary Recommendation

→ **R5 — REJECT calibration. Survivor evidence is single-symbol artifact.**

The 8 cost=0.5x survivors are exclusively on SOLUSDT, all train-val divergent (negative train PnL), and all collapse at neighboring cost levels. This is the textbook signature of curve fit / regime artifact, not a stable edge. Lowering cost to "unlock" these candidates would promote artifacts into staging and create false-positive survivor pools.

## 4. Secondary Recommendation

→ **R6 + R4 (combined) — Tighten validator gates AND redesign formula universe**

Concrete next steps (in priority order):
1. **Tighten val_filter chain** to require:
   - `train_pnl > 0 AND val_pnl > 0` (rejects train-val divergent cells)
   - `combined_sharpe ≥ 0.4`
   - `cross_symbol_consistency` ≥ 2/3 symbols positive at the same parameter set
2. **Re-run a wider calibration matrix** (Option F) with the new gates active to see whether ANY survivor remains
3. **Redesign alpha generation priors** (Option E) to include longer-horizon and multi-timeframe formulas
4. **Defer cost-model changes** until either maker order routing (Option G) or universe redesign (Option E) demonstrates an edge at the current 1.0x cost

## 5. Exact Next TEAM ORDER

`TEAM ORDER 0-9X-VAL-FILTER-CONTRACT-UPGRADE-AND-EXPANDED-CALIBRATION-MATRIX`

### Scope (allowlist)
- `zangetsu/services/arena_pipeline.py` — val_filter chain (specifically the gate ordering at lines ~1010-1100; preserve ALL existing semantics, ADD new gates only)
- `zangetsu/engine/components/val_filter.py` (if exists) — combined-sharpe + cross-symbol-consistency new gate logic
- `tests/test_val_filter_v{N}_smoke.py` — unit + smoke tests for new gates
- `docs/recovery/20260427-mod-7/0-9x-val-filter-contract-upgrade-and-expanded-calibration-matrix/` — evidence
- `0-9x-replay.py` — expanded calibration matrix script (offline, no DB) over all 14 symbols × 5 formulas × 3 cost × 5 ET × 5 MH = ~5,250 cells

### Scope (blocklist — explicitly forbidden)
- DO NOT change `cost_bps` values
- DO NOT change `taker_bps`, `slippage_bps`, `funding_8h_avg_bps`
- DO NOT change `ENTRY_THR=0.80`
- DO NOT change `MAX_HOLD_BARS=120`
- DO NOT change `A2_MIN_TRADES=25`
- DO NOT change `TRAIN_SPLIT_RATIO=0.7`
- DO NOT weaken existing val gates (val_neg_pnl, val_few_trades, val_low_sharpe, val_low_wr)
- DO NOT inject alpha_zoo formulas
- DO NOT write to champion_pipeline_*
- DO NOT start CANARY
- DO NOT touch execution / capital / risk

### Acceptance criteria
- New val gates implemented with explicit on/off feature flag (default ON)
- Unit tests for each new gate
- Expanded matrix shows whether any cell survives ALL gates
- Evidence package complete; PR signed; Gate-A/B PASS

### No-go conditions
- If new gates reject 100% of cells in expanded matrix → defer formula universe redesign + acknowledge "no calibration window exists at current alpha edge"
- If maker order routing (Option G) is initiated separately → coordinate so the cost model maker_fill_rate becomes consumable

## 6. Explicit No-Go Conditions for Calibration

A calibration implementation order will NOT be opened until:
- **NG1**: Maker order routing exists in zangetsu and provides per-symbol observed maker fill rate
- **NG2**: Combined train+val Sharpe gate is in place and active in val_filter chain
- **NG3**: Cross-symbol consistency gate is in place and active
- **NG4**: Expanded calibration matrix (Option F) shows ≥3 cells classified as ROBUST_CANDIDATE under tightened gates
- **NG5**: At least 2 of those candidates exist on different symbols and have positive train AND positive val PnL

If NG1-NG5 are not all met, calibration implementation remains BLOCKED.

## 7. Phase 6 Verdict

→ **Primary: R5 — REJECT calibration as artifact.**
→ **Secondary: R6 + R4 — tighten gates, redesign universe, expand matrix.**
→ **Next order: `TEAM ORDER 0-9X-VAL-FILTER-CONTRACT-UPGRADE-AND-EXPANDED-CALIBRATION-MATRIX`.**
→ **Calibration of cost_bps remains BLOCKED until NG1-NG5 are met.**
