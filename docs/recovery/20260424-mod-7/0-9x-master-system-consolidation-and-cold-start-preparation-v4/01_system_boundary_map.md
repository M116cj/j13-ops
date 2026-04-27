# 01 — System Boundary Map

## A. Runtime Services

### A1 — Alpha Generation
- **Source**: `zangetsu/services/arena_pipeline.py`
- **Responsibility**: generate candidate formulas via GP; run train+val backtests; emit rejection stats; write valid candidates to `champion_pipeline_staging`
- **Forbidden**: direct champion promotion, direct production execution, validation bypass, direct fresh injection, hidden APPLY behavior
- **Inputs**: OHLCV cache (train + holdout slices); `_strategy_thresholds` (j01 defaults); cost_model
- **Outputs**: JSONL events to `engine.jsonl` + `/tmp/zangetsu_a1_*.log`; staging INSERT (when migration applied)
- **Allowed callers**: cron-launched worker invocations only

### A13 — Feedback / Guidance
- **Source**: `zangetsu/services/arena13_feedback.py` (single-shot via cron */5)
- **Responsibility**: observe candidate/champion state; compute feedback guidance; emit observe-mode weights to `config/a13_guidance.json`
- **Forbidden**: directly mutate A1 generation; production apply mode; hidden budget reallocation
- **Inputs**: `champion_pipeline_fresh` (after migration); `engine_telemetry`
- **Outputs**: `config/a13_guidance.json`; log to `/tmp/zangetsu_arena13_feedback.log`
- **Allowed callers**: cron only

### A23 — Arena Intake
- **Source**: `zangetsu/services/arena23_orchestrator.py`
- **Responsibility**: consume eligible candidates from `champion_pipeline_fresh`; run Arena 2 + 3 stage processing; emit Arena telemetry
- **Forbidden**: invent candidates; bypass DB lifecycle; bypass validation contract
- **Inputs**: `champion_pipeline_fresh` rows with appropriate status
- **Outputs**: status updates on `champion_pipeline_fresh`; logs

### A45 — Downstream
- **Source**: `zangetsu/services/arena45_orchestrator.py`
- **Responsibility**: consume A23 outputs; run Arena 4 + 5 processing; remain idle if no upstream
- **Forbidden**: promote candidates without upstream evidence; execute trading logic
- **Inputs**: `champion_pipeline_fresh` post-A23
- **Outputs**: status updates; logs

## B. Data / DB Layer

| Object | Type | Responsibility |
| --- | --- | --- |
| `champion_pipeline_staging` | TABLE | first approved materialization target; admission_state ∈ {pending, admitted, rejected, pending_validator_error} |
| `champion_pipeline_fresh` | TABLE | validated fresh candidates after admission; the canonical pool readable by A13/A23/A45/dashboard |
| `champion_pipeline_rejected` | TABLE | rejected candidate forensics (audit) |
| `champion_pipeline` | VIEW | backward-compat read shim → fresh; for code that hasn't migrated path yet |
| `champion_legacy_archive` | TABLE | historical Epoch A data, read-only via triggers |
| `engine_telemetry` | TABLE | runtime metric counters time-series |
| `admission_validator(BIGINT)` | function | controlled promotion staging → fresh; runs 3 gates |
| `fresh_insert_guard` | trigger | prevents direct INSERT to fresh outside `admission_validator()` |
| `archive_readonly_insert/update/delete` | triggers | prevent any modification to legacy archive |

## C. Validation Layer

- **Source**: `arena_pipeline.py` lines 980-1050 + new gates added in this PR
- **Responsibility**: reject weak candidates BEFORE DB materialization; enforce train AND val profitability; enforce robustness; block single-symbol artifacts
- **Active gates after this PR**:
  - `val_constant` — std < 1e-10
  - `val_error` — exception during val backtest
  - `val_few_trades` — val_trades < 15
  - `val_neg_pnl` — val net_pnl ≤ 0
  - `val_low_sharpe` — val sharpe < 0.3
  - `val_low_wr` — wilson_lb < 0.52
  - **NEW** `train_neg_pnl` — train net_pnl ≤ 0 (PR #43 / NG2)
  - **NEW** `combined_sharpe_low` — `(train_sharpe + val_sharpe) / 2 < 0.4` (PR #43 / NG2)
  - **NEW** `cross_symbol_inconsistent` — fewer than 2/3 of symbols positive at same params (PR #43 / NG3) — applied at A1 round-summary level
- **Shared usage**: same gates apply to GP candidates, alpha_zoo offline replay, calibration matrix replay, future cold-start

## D. Cold-Start Layer

- **Source**: `zangetsu/scripts/alpha_zoo_injection.py` (hardened in this PR)
- **Responsibility**: inspect formulas; dry-run against validation contract; output candidate plans
- **Forbidden** (default-safe): default write mode; direct fresh write; deprecated seed execution; validation bypass; production DB mutation without `--confirm-write` AND a future governed order
- **New flags after this PR**:
  - `--inspect-only` (default ON) — list formulas without compile or write
  - `--dry-run` — full compile + validation contract simulation; zero DB writes
  - `--no-db-write` — explicit assertion (default behavior, fails fast if DB write attempted)
  - `--confirm-write` — required for any DB write; without it, all paths are no-op + abort
- **Deprecated cold-start tools** (blocked): `seed_101_alphas.py`, `seed_101_alphas_batch2.py`, `factor_zoo.py`, `alpha_discovery.py` — all have `DEPRECATED in v0.7.1` guard that prints REFUSED and exits

## E. Governance Layer

- **Source**: branch protection + `.github/workflows/{module-migration-gate,phase-7-gate}.yml` + `.githooks/pre-commit`
- **Responsibility**: enforce signed-PR-only flow; controlled-diff classification; Gate-A entry prerequisites; Gate-B per-module checks; branch protection (5 flags); evidence production; Telegram Thread 356 notification
- **Forbidden**: unsigned commits; force pushes; direct deletion of main branch; bypassing CI checks

## Boundary Conflict-Free Statement

After this consolidation:
- A1 writes ONLY to staging (via `admission_validator()`)
- Validator promotes ONLY through gated `admission_validator()`
- Direct fresh INSERT is hard-blocked by `fresh_insert_guard`
- Legacy archive is hard-blocked by `archive_readonly_*` triggers
- Cold-start tooling refuses to write without `--confirm-write` AND DB schema check AND validation contract active

→ Boundaries are explicit, exclusive, and enforced at both code AND DB layer.
