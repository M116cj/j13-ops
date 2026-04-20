# Zangetsu Engine — Project-level CLAUDE.md
# Extends (never contradicts) ~/.claude/CLAUDE.md. Per global §14.

## Scope

Neutral alpha-discovery training engine. Zangetsu provides the shared
infrastructure; strategy projects (`j01`, `j02`, future `jNN`) sit on
top and contribute their own fitness functions and threshold bundles.

## Hard rules (this engine)

1. Zangetsu never imports from a strategy project. The dependency flows
   one way: strategy imports engine. Violations break the clean split.
2. `alpha_engine._evaluate` delegates scoring to a strategy-provided
   `fitness_fn` callable injected at `AlphaEngine.__init__`. No fitness
   lives in engine code. If a PR adds a fitness constant/formula under
   `zangetsu/`, it's rejected.
3. Every production process must have `STRATEGY_ID` env set. Arena
   pipeline startup raises on missing / unknown value.
4. Any row write to `champion_pipeline` must include `strategy_id`.
   Engine-level SQL (arena23/45 SELECT/UPDATE) must preserve
   `strategy_id` — never reset or reassign.
5. Engine version bumps (`feat(zangetsu/vX.Y)`) follow global §17.5 via
   `bin/bump_version.py` + Calcifer witness + decision record.
6. Engine-level VIEW `zangetsu_engine_status` aggregates across
   strategies; it is the monitoring surface for Calcifer / watchdog.
   Per-strategy monitoring reads `{strategy}_status` VIEW (§17.1).

## DEPLOYABLE tiers

The tier schema (`historical / fresh / live_proven`) lives on the engine
(DB column + CHECK constraint). Strategies inherit the tier semantics.
A strategy may tighten promotion criteria (e.g. J02 plans a DSR filter on
live_proven) but cannot relax the schema.

## Arena gate logic

| Gate | Home | Shared? |
|------|------|---------|
| A1   | engine + strategy | engine provides GP loop; strategy provides `fitness_fn` |
| A2   | engine (`services/arena_gates.arena2_pass`) | yes |
| A3   | engine (`services/arena_gates.arena3_pass` + `build_a3_segments`) | yes |
| A4   | engine (`services/arena_gates.arena4_pass`) | yes |
| A5   | engine (shadow service — v0.8.0 roadmap) | yes |

Strategies may parameterize gates via `jNN/config/thresholds.py` but
cannot replace the gate implementation.

## Folder conventions (this engine)

- `engine/components/` — pure algorithms (no IO)
- `services/` — long-running orchestrators (systemd)
- `live/` — realtime data subscription + execution
- `dashboard/`, `console/` — HTTP API
- `scripts/` — one-shot tools (seed / analysis / migration)
- `tests/` — pytest
- `docs/decisions/` — ADRs (Traditional Chinese)
- `docs/retros/` — per-`/team` retros
- `docs/arch/` — draw.io XML
- `docs/research/` — non-deletable research archives (per global §11)
- `docs/refactor-history/` — archival spec/meeting notes
- `migrations/postgres/` — versioned schema migrations
- `secret/` — gitignored credentials
- `secret.example/` — committed template
- `archive/` — frozen prior-version snapshots (read-only)
- `scratch/` — experiments (global §17.8 reaper applies)
- `data/`, `logs/`, `.venv/`, `graphify-out/`, `.pytest_cache/`,
  `__pycache__/` — gitignored
