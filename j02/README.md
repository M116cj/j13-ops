# J02 — ICIR K=5 alpha strategy

## Purpose

J02 runs on the Zangetsu engine and evolves alpha formulas that show
stable sign-and-magnitude IC across five contiguous folds of the
training window. It matches AlphaForge / Warm-Start GP / Numerai
industry practice.

**Strategy class**: worst-fold-robust stability search.
**Fitness**: `mean(|IC_k|) - lambda*std(|IC_k|) - height_penalty`,
sign-agreement across all K folds, per-fold magnitude floor.
**Data**: shared with engine — 1m OHLCV × 14 symbols.
**Output**: `champion_pipeline` rows with `strategy_id = 'j02'`.

## Pointers

| Aim                 | See                                          |
|---------------------|-----------------------------------------------|
| Fitness definition  | [`fitness.py`](./fitness.py)                 |
| Threshold bundle    | [`config/thresholds.py`](./config/thresholds.py) |
| Single-truth VIEW   | [`config/sql/j02_status_view.sql`](./config/sql/j02_status_view.sql) |
| Project rules       | [`CLAUDE.md`](./CLAUDE.md)                    |
| Version history     | [`VERSION_LOG.md`](./VERSION_LOG.md)          |
| Decision records    | [`docs/decisions/`](./docs/decisions/)        |

## Runtime

Launched by Zangetsu `zangetsu_ctl.sh` with `STRATEGY_ID=j02`. The
launcher imports `j02.fitness.fitness_fn` and injects it into
`AlphaEngine`.

## Differences from J01

| | J01 | J02 |
|---|---|---|
| Fitness | harmonic K=2 | ICIR K=5 |
| Folds | 2 | 5 |
| Sign gate | across halves | across all 5 folds |
| Magnitude floor | 5e-3 per half | 3e-3 per fold |
| Expected output rate | higher | lower |
| Expected style | medium-horizon, some trend | short-horizon, statistical |

See `zangetsu/docs/research/research-gp-fitness-stability-20260420.md`.
