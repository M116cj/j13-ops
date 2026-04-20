# J01 — Project-level CLAUDE.md
# Extends (never contradicts) `~/.claude/CLAUDE.md` (§14). J01 is a
# strategy project that runs on top of the Zangetsu engine.

## Scope

Harmonic-K=2 alpha strategy. Does NOT own:
- GP framework, indicators, backtester, arena gates (those live in zangetsu)
- DB schema, data layer, systemd launcher (those live in zangetsu)

J01 owns:
- `fitness.py` — its fitness function contract
- `config/thresholds.py` — tunable thresholds specific to this strategy
- `config/sql/j01_status_view.sql` — its §17.1 single-truth VIEW
- `scripts/rescan_j01_legacy.py` — strategy-specific legacy rescan
- `docs/decisions/` + `docs/retros/` — strategy-scoped ADRs
- `secret.example/` — any strategy-specific API keys (empty by default;
  most config lives in zangetsu/secret/.env)

## Hard rules

1. Fitness changes require a `docs/decisions/YYYYMMDD-*.md` ADR citing
   research (under `zangetsu/docs/research/`) that justifies the change.
   Fitness is the defining characteristic of the strategy; do not tune it
   casually.
2. Threshold changes (`config/thresholds.py`) require an ADR explaining
   observed behavior that triggered the change and the expected effect.
3. §17.1 `j01_status` VIEW is the single truth for "is J01 producing?".
   No inline count queries; all monitoring reads the VIEW.
4. J01 never writes to rows with `strategy_id != 'j01'`.

## DEPLOYABLE tiers (j01_status)

Same as engine defaults: `historical / fresh / live_proven`.
- `historical`: a J01 fitness rescan of legacy alphas that pass A2-A4
  under J01 thresholds.
- `fresh`: native J01 output from a current GP worker, arena-gated.
- `live_proven`: 14-day live shadow survivor under J01 config.

Only `live_proven` may auto-activate (`card_status = 'ACTIVE'`).

## Runtime

J01 is launched by the Zangetsu `zangetsu_ctl.sh` launcher with
`STRATEGY_ID=j01` env. That launcher imports `j01.fitness.fitness_fn`
into `AlphaEngine(fitness_fn=...)`. The engine is neutral — it never
imports from J01 directly; the launcher is the composition root.

## Out of scope

- New data sources (those are engine concerns)
- New backtester behavior (engine)
- New arena gates (engine provides `arena_gates.py` module)
- Multi-asset support (handled at engine level via `symbols` config)
