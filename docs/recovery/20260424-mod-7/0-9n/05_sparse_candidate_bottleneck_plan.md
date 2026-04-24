# 05 — Sparse-Candidate Bottleneck Plan

TEAM ORDER 0-9N §9.4 + §14 deliverable.

## 1. Observed problem

From 0-9J CANARY (origin/main `419f3d9f`) and 0-9K / 0-9L SHADOW:

- **Arena 2 produces 93-96.5% of all rejection traffic.**
- **1,474 / 1,672 non-deployable candidates (88.2%) exit A2 labeled `SIGNAL_TOO_SPARSE`.**
- Root cause: candidate fails `A2_MIN_TRADES=25` gate or `pos_count >= 2` gate on the A2 holdout.
- Only 6 candidates became deployable in the 7-day window (70381, 70382, 70390, 70400, 70407, 70436).

## 2. Root cause categorization

`SIGNAL_TOO_SPARSE` at A2 is NOT a single condition — it covers several sub-patterns observed in the classifier's `RAW_TO_REASON`:

| Raw pattern | Observed count (0-9G / 0-9J) | Sub-meaning |
|---|---:|---|
| `<2 valid indicators after zero-MAD filter` | 2,582 | A2's indicator dedup filter rejected the candidate (too many near-zero-variance indicators) |
| `[V10]: pos_count=0` | 783 | Candidate produced zero positions on A2 holdout (alpha fires entry but never gets paired with a valid exit / position size) |
| `[V10]: pos_count=0 < 2` | 8 | Same — only 0-1 positions |
| `[V10]: trades=<N> < 25` | 22 (total) | Candidate produced < 25 total trades on A2 holdout |

Interpretation:

- **Zero-MAD indicator rejection (~76% of A2 rejections)** = candidate relies on indicators that produce no variance on the A2 holdout window. Either the holdout window is too short, or the indicator computation is pathological, or the regime mismatch between train and holdout leaves the indicator flat.
- **Pos-count-zero (~23% of A2 rejections)** = alpha produces theoretical entry signals but fails to convert them into real trades (signal-to-trade plumbing or entry threshold too tight).
- **Trades < 25 (< 1% of A2 rejections)** = textbook sparse alpha (entry threshold too tight for the alpha's signal density).

## 3. What the WRONG solution looks like (forbidden)

Lowering `A2_MIN_TRADES` from 25 to e.g. 15 would "fix" the pass rate but at the cost of Arena quality. Arena 2's `trades >= 25` gate exists to ensure statistical significance of the holdout evaluation. Weakening the gate:

- Increases OOS fragility (small-sample luck passes as success)
- Reduces downstream A3 / A4 signal-to-noise
- Creates overfit risk

**The threshold CANNOT be lowered under 0-9N / future 0-9R authorization.** 0-9M's `NEVER_TRACE_ONLY_AUTHORIZABLE = {"config.zangetsu_settings_sha"}` + explicit threshold order requirement prevents this at the governance layer.

## 4. What the CORRECT solution looks like (design)

Improve the black-box generation profile to produce candidates that NATURALLY satisfy the A2 gate. The Arena stays strict; the generator gets smarter.

### 4.1 Detection layer (P7-PR4-LITE + 0-9O)

Per generation profile, compute:

- `signal_too_sparse_rate = sum(SIGNAL_TOO_SPARSE rejections) / sum(entered_count at A2)`
- Sub-breakdown: zero-MAD vs pos-count vs trades<25 (via new raw-reason granularity in classifier; optional extension)
- Per-profile `signal_too_sparse_rate` distributed across (symbol × regime) to detect context-specific sparsity

### 4.2 Feedback layer (0-9O)

Budget allocator (see §04 §7) shifts budget AWAY from profiles with
`signal_too_sparse_rate > X`. Suggested X: start with 0.70 as "unhealthy" threshold
(vs observed 0.88 baseline). Profiles above X receive `exploration_floor`-only budget; profiles below X receive proportional boost.

### 4.3 Policy layer (future 0-9R — NOT in 0-9N scope)

Under explicit j13 authorization, 0-9R may tune generation profile parameters to reduce sparsity at source. **Specifically what 0-9R may do**:

| Adjustable | Likely effect on sparsity |
|---|---|
| Lower `ENTRY_THR` (entry threshold; in `settings.py`) | More trades, more positions — direct sparsity reduction. **Requires threshold order.** |
| Shorter `MIN_HOLD` | Faster cycling → more trades in the holdout window. **Requires threshold order.** |
| Shorter `COOLDOWN` | Same — more frequent re-entry. **Requires threshold order.** |
| Indicator sampling toward higher-volatility families | More natural variance → fewer zero-MAD rejections. Generation-policy change; **requires 0-9R order.** |
| Constrain evolved alpha arity (e.g., max 3 indicators per alpha) | Reduces brittleness from stacked rarely-firing indicators. Generation-policy change. |
| Regime-aware profile selection (e.g., activate Volume-L9 only in ranging regimes) | Cuts profile × regime mismatch. Policy change. |

### 4.4 What 0-9R may **NOT** do

- Lower `A2_MIN_TRADES` or `A3_MIN_TRADES_PER_SEGMENT` — Arena quality floor.
- Relax A2 zero-MAD filter — signal integrity.
- Change A2 `non_positive_pnl` predicate — cost honesty.
- Skip val backtest in A1 — OOS hygiene.
- Change `admission_validator` logic — admission contract.

## 5. Measurement plan

Before / after comparison requires:

1. **Pre-0-9R baseline**: current profile's `avg_a2_pass_rate`, `signal_too_sparse_rate`, `avg_deployable_count` over N batches (recommend N ≥ 20 to smooth per-batch noise).
2. **Post-0-9R observation**: same metrics after generation-profile policy change. Calculate absolute deltas AND delta relative to a control profile (if running A/B).
3. **Success criteria**:
   - `avg_a2_pass_rate` improves by ≥ 0.05 absolute (5 percentage points).
   - `signal_too_sparse_rate` drops by ≥ 0.10 absolute.
   - `avg_deployable_count` improves without worsening downstream A3 pass_rate.
   - No regression in OOS stability (`oos_fail_rate` does not rise).
4. **Failure criteria**:
   - A2 pass_rate rises, but A3 pass_rate drops by ≥ 0.10 → the candidates got sparse-friendly but quality-weak. Revert.
   - `oos_fail_rate` rises → overfit risk. Revert.
   - `instability_index` rises sharply → candidates more volatile. Investigate.

## 6. A/B capability (design — implementation in 0-9S CANARY)

0-9S (CANARY) should run two generation profiles in parallel:

- **Profile A** (control): current V10 Volume L9 baseline.
- **Profile B** (treatment): 0-9R's proposed policy change.

Budget split: 50/50 for first CANARY week; analyze per-profile deltas. Proceed to full rollout (0-9T) only if Profile B dominates across all criteria in §5.3 without regressing §5.4.

## 7. Connection to black-box direction

This plan deliberately:
- Does NOT open the alpha operator box (mutation / crossover / fitness stays black).
- Does NOT require per-alpha explainability.
- DOES require profile-level aggregate visibility (black-box alpha, white-box profile outcomes).
- DOES respect Arena's role as the integrity gate.

The sparse-candidate problem is reframed from "why does this specific alpha have too few trades" (per-alpha interpretability) to "which generation profiles produce fewer sparse candidates on average" (profile-level aggregate). The latter is exactly what the 0-9N design supports.

## 8. Residual unknowns (0-9R design must address)

- Is the zero-MAD filter's threshold the right one? (If yes, don't touch; if no, address under a separate filter-tuning order.)
- Does `pos_count=0` reflect alpha design or signal-to-trade plumbing? If plumbing, 0-9R is a different class of fix.
- Are certain symbols (e.g., XRPUSDT) inherently sparser than others in current DOE? If yes, symbol-level profile gating should be added to the feedback loop.

These are questions for 0-9R's read-only investigation phase, not 0-9N.

## 9. STOP conditions for this plan's execution

Per 0-9N §17, 0-9R work must STOP if:

- Any threshold lowering is proposed (requires separate threshold order).
- Any Arena pass/fail change is proposed.
- Any alpha operator change is proposed without separate authorization.
- A/B measurement cannot show the treatment profile's improvement is not at the cost of quality.
- Behavior-invariance tests fail.

## 10. Summary

**The plan**: improve generation profiles so candidates satisfy A2 naturally; never weaken A2. Feedback loop is profile-level; Arena stays strict. Measurement is pass-rate + deployable_count + quality regressions. Implementation unfolds across P7-PR4-LITE (telemetry) → 0-9O (feedback optimizer) → 0-9R (policy change under authorization) → 0-9S (CANARY) → 0-9T (production).
