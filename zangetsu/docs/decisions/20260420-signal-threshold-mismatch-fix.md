# 20260420 Signal Threshold Mismatch Fix

- Status: Proposed
- Date: 2026-04-20
- Scope: `zangetsu/services/arena_pipeline.py`
- Author: Codex (diagnosis + draft) / Claude (apply + commit)

## What Decided
Raise the default signal thresholds used by Arena 1 from:

- `ALPHA_ENTRY_THR`: `0.80` -> `0.95`
- `ALPHA_EXIT_THR`: `0.50` -> `0.65`

Keep the environment variable names unchanged, and do not modify `engine/components/alpha_signal.py` in this phase.

## Why
`alpha_to_signal()` does not compare thresholds directly against rank. It first converts rolling rank to `size = 2*|rank - 0.5|` and then applies:

- entry: `size >= entry_rank_threshold - 0.5`
- exit: `size < exit_rank_threshold - 0.3`

With the old defaults:

- `ENTRY_THR=0.80` means `size >= 0.30`, which is rank outside `[0.35, 0.65]`
- `EXIT_THR=0.50` means `size < 0.20`, which is rank inside `[0.40, 0.60]`

That is too loose on entry and too stingy on exit for alphas that are already rank-like. The Phase A diagnostic formula has `p50=1.0` in both train and holdout, so its rolling rank spends long stretches near an extreme. Under the old defaults, one entry can persist for an entire slice.

The new defaults preserve the same hysteresis gap while moving both bands outward:

- `ENTRY_THR=0.95` means `size >= 0.45`, which is rank outside `[0.275, 0.725]`
- `EXIT_THR=0.65` means `size < 0.35`, which is rank inside `[0.325, 0.675]`

This makes entry materially stricter, makes exit materially easier, and keeps the entry/exit `size` gap at `0.10`, so the state machine behavior remains familiar.

## Evidence from Phase A diagnostic (2026-04-20 16:38 UTC)
Target formula: `pow2(ts_rank_3(ts_rank_3(ts_rank_3(ts_rank_3(close)))))` (archive id=72306, arena1_pnl=0.7255 in Epoch A).

Under current v0.7.2 config:
- alpha distribution p50=1.0 on both train AND holdout
- signal: train=139441 long/0 short/559 flat, train_position_changes=1
- signal: holdout=0 long/59441 short/559 flat, holdout_position_changes=1
- all four horizons (60/120/240/480) produce negative net_pnl + sharpe + wilson < 0.45
- positive_horizons: []

One entry latched for entire slice. Train and holdout inverted because rolling-rank baseline is slice-local.

## What Rejected + Why
### Change `alpha_signal.py` to literal rank-space thresholds
Rejected for this phase. That would alter the core signal state machine for every caller, not just Arena 1 defaults, and it is no longer a one-file low-risk fix. The current bug is explainable as parameter semantics, not a broken implementation.

### Rename the env vars to reflect `size` semantics
Rejected because it would break existing live config and runbooks. Backward compatibility matters more than cosmetic correctness in this patch.

### Push defaults to `1.00 / 0.70`
Rejected as too aggressive for the evidence available. It would narrow entry from 70% active rank coverage to 50% and widen exit to a 40% middle band. That may reduce latching further, but it also increases the risk of failing the trade-count gates (`bt.total_trades < 30`, `bt_val.total_trades < 15`) without additional calibration data.

### Introduce a new config file/module
Rejected as out of scope. No such config module exists in this repo, and creating one would increase blast radius for a constants-only repair.

### Try to achieve literal top/bottom 5% entry without changing code
Rejected as impossible under the current transform. Because entry compares against `size`, the strictest env-only setting is `ENTRY_THR=1.00`, which still means rank outside `[0.25, 0.75]`, not literal 5% tails. Achieving true tail-only entry would require a code change in `alpha_signal.py`.

## Adversarial Voice
### Input boundary
PASS. `0.95` and `0.65` remain inside the existing `[0, 1]` expectation implied by current callers. No new NaN/Inf or type boundary is introduced.

### Silent failure
ISSUE -> FIXED. Old defaults silently encoded much looser behavior than their names suggested (`0.80` became `size >= 0.30`; `0.50` became `size < 0.20`). New defaults do not fix the naming mismatch, but they materially reduce the dead/stuck-signal failure observed in Phase A while preserving the existing state machine.

### External dependency
PASS. No new dependency, no schema change, no new env name. Existing `ALPHA_ENTRY_THR` and `ALPHA_EXIT_THR` overrides continue to work.

### Concurrency
PASS. Thresholds are read once per worker loop and passed as immutable scalars. This patch does not add shared mutable state or alter async control flow.

### Scope creep
PASS. Only `services/arena_pipeline.py` defaults change. Backtester, fitness modules, alpha engine, and production config shape remain untouched.

## Research
- Read `engine/components/alpha_signal.py` lines 42-79 to verify rolling-rank, `size`, entry, and exit semantics.
- Read `services/arena_pipeline.py` lines 561-564, 727-733, and 778-784 to confirm the production defaults and both train/holdout call sites.
- Read `/home/j13/strategic-research/codex-v0.7.2-diagnostic-run-20260420.log` to confirm the empirical failure mode.

## Q1 / Q2 / Q3 Status
- Q1. Why signal latches for whole window: Resolved. Already-ranked alpha plus loose entry / tight exit keeps `size` above the entry bar and out of the exit band for most of the slice.
- Q2. Why train long / holdout short: Resolved. Rolling-rank reference pools are slice-local, so the train and holdout warmup windows establish different baselines and can invert sign at the boundary.
- Q3. Correct fix: Resolved for Phase A. Tighten only Arena 1 defaults to `0.95 / 0.65`, keep env names stable, and leave signal code unchanged until a broader semantics cleanup is intentionally scoped.

## Consequences
### Positive
- Unblocks the specific dead/stuck-signal failure where rank-already alphas spend an entire window long or short after a single post-warmup entry.
- Keeps the repair minimal, one-file, and reversible.
- Preserves existing environment-variable overrides and caller behavior.

### Negative / New Risks
- Trade frequency will drop because entry is stricter.
- Some candidates will now fail `total_trades` or `val_trades` gates rather than failing on uniformly negative PnL.
- Fewer trades widen Wilson confidence intervals, so admission volume may recover more slowly than signal quality.
- The semantic mismatch in `alpha_signal.py` still exists; this ADR only chooses safer defaults under the current implementation.

## Verification
Test command to confirm fix unlocks the stuck-signal pattern:
```bash
ALPHA_ENTRY_THR=0.95 ALPHA_EXIT_THR=0.65 python zangetsu/scripts/codex_v072_horizon_diagnostic.py \
  --repo-root /home/j13/j13-ops --strategy-id j01 --symbol BTCUSDT \
  --formula 'pow2(ts_rank_3(ts_rank_3(ts_rank_3(ts_rank_3(close)))))' \
  --entry-threshold 0.95 --exit-threshold 0.65
```

Expected outcomes:
- `train_position_changes` > 10 (was 1)
- `holdout_position_changes` > 10 (was 1)
- At least one `backtests_by_horizon[i].holdout.net_pnl > 0` (was all negative)
