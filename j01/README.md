# J01 — Harmonic K=2 alpha strategy

## Purpose

J01 is one of the strategy tracks built on top of the Zangetsu engine.
It evolves alpha formulas whose IC is same-sign and magnitude-balanced
across two halves of the training window.

**Strategy class**: time-symmetric signal search.
**Fitness**: sign-gated harmonic mean of `|IC_early|` and `|IC_late|`.
**Data**: shared with engine — 1m OHLCV × 14 symbols.
**Output**: `champion_pipeline` rows with `strategy_id = 'j01'`.

## Pointers

| Aim                 | See                                          |
|---------------------|-----------------------------------------------|
| Fitness definition  | [`fitness.py`](./fitness.py)                 |
| Threshold bundle    | [`config/thresholds.py`](./config/thresholds.py) |
| Single-truth VIEW   | [`config/sql/j01_status_view.sql`](./config/sql/j01_status_view.sql) |
| Project rules       | [`CLAUDE.md`](./CLAUDE.md)                    |
| Version history     | [`VERSION_LOG.md`](./VERSION_LOG.md)          |
| Decision records    | [`docs/decisions/`](./docs/decisions/)        |
| Rescan legacy script| [`scripts/rescan_j01_legacy.py`](./scripts/rescan_j01_legacy.py) |

## Runtime

J01 does not have its own worker process yet — it runs inside the
Zangetsu `arena_pipeline.py` workers launched by `zangetsu_ctl.sh` with
`STRATEGY_ID=j01`. When k worker slots are dedicated to J01 they import
`j01.fitness.fitness_fn` at startup and feed it to `AlphaEngine`.

## Differences from J02

| | J01 | J02 |
|---|---|---|
| Fitness | harmonic K=2 | ICIR K=5 + DSR (post-hoc) |
| Splits | 2 halves | 5 contiguous folds |
| Strength | captures medium-horizon trends | captures short-horizon consistency |
| Expected output rate | higher (looser gate) | lower (stricter gate) |
| Expected live survival | medium | higher |

See `zangetsu/docs/research/research-gp-fitness-stability-20260420.md`
for the research archive that motivated the split.
