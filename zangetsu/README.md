# Zangetsu — Alpha Discovery Engine

Neutral training engine for GP-based alpha discovery. Strategies plug in
via a `fitness_fn` contract and get access to the full data pipeline,
indicator engine, arena gates, and deployment infrastructure.

Zangetsu itself does **not** own a fitness function — it is
strategy-agnostic. Strategy projects (currently `j01`, `j02`) live as
sibling packages at the `j13-ops/` root and contribute their fitness at
worker startup time.

## Strategies built on this engine

| Project | Fitness | Status |
|---------|---------|--------|
| [`../j01/`](../j01/) | Harmonic K=2 (sign-gated) | v0.1.0 live on workers w0, w1 |
| [`../j02/`](../j02/) | ICIR K=5 + sign gate | v0.1.0 live on workers w2, w3 |

Adding a new strategy `jNN` requires:
1. `jNN/fitness.py` with a `fitness_fn(alpha, forward_returns, height) -> float`.
2. `jNN/config/sql/jNN_status_view.sql` (§17.1 single-truth VIEW).
3. `jNN/CLAUDE.md` + `VERSION_LOG.md` + `README.md` + `docs/decisions/`.
4. Bump the worker split in `zangetsu/zangetsu_ctl.sh`.
5. Add a VIEW query + miniapp card in `zangetsu/scripts/zangetsu_snapshot.sh`
   and `d-mail-miniapp/static/index.html`.

## Engine pointers

| Aim                        | See                                   |
|----------------------------|----------------------------------------|
| Project constitution       | `../CLAUDE.md` §17 (global)           |
| Engine rules               | [`CLAUDE.md`](./CLAUDE.md)             |
| Version history            | [`VERSION_LOG.md`](./VERSION_LOG.md)   |
| Decision records           | [`docs/decisions/`](./docs/decisions/) |
| Retros (per /team run)     | [`docs/retros/`](./docs/retros/)       |
| Architecture XML           | [`docs/arch/`](./docs/arch/)           |
| Research archive           | [`docs/research/`](./docs/research/)   |
| Engine-rollup VIEW         | [`config/sql/zangetsu_status_view.sql`](./config/sql/zangetsu_status_view.sql) |
| GP framework               | [`engine/components/alpha_engine.py`](./engine/components/alpha_engine.py) |
| Arena gates (shared)       | [`services/arena_gates.py`](./services/arena_gates.py) |
| Holdout / regime helpers   | [`services/holdout_splits.py`](./services/holdout_splits.py), [`services/regime_tagger.py`](./services/regime_tagger.py) |
| Launcher                   | [`zangetsu_ctl.sh`](./zangetsu_ctl.sh) |
| Watchdog                   | [`watchdog.sh`](./watchdog.sh)         |
| Secrets template           | [`secret.example/`](./secret.example/) |
| Real secrets               | `secret/` (gitignored, 700/600)        |

## Pipeline

A1 GP evolve (strategy-specific fitness) → A2 OOS PnL gate →
A3 time-segment stability → A4 regime stability →
A5 real-world validation (14-day live paper-trade shadow — v0.8.0 roadmap).

Only alphas with `deployable_tier = 'live_proven'` may auto-enter the
active trading pool. `historical` and `fresh` require j13 explicit
approval.

## Running

Zangetsu is not designed to run on macOS. Development happens in `scratch/`
sandboxes on Mac; production runs under cron+watchdog on Alaya. See
[`deploy/`](./deploy/) and [`zangetsu_ctl.sh`](./zangetsu_ctl.sh).
