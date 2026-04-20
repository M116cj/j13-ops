# J02 — Project-level CLAUDE.md
# Extends global CLAUDE.md §14. J02 is a strategy project on top of the
# Zangetsu engine.

## Scope

ICIR K=5 alpha strategy. Does NOT own: GP framework, indicators,
backtester, arena gates, DB schema, data layer, systemd launcher.

J02 owns:
- `fitness.py` — ICIR-style mean-std-lambda fitness with sign gate
- `config/thresholds.py` — J02-specific thresholds (may diverge from J01)
- `config/sql/j02_status_view.sql` — §17.1 single-truth VIEW
- `docs/decisions/` + `docs/retros/`
- `secret.example/` — strategy-specific placeholders (empty initially)

## Hard rules

1. Fitness changes require a `docs/decisions/YYYYMMDD-*.md` ADR citing
   research (`zangetsu/docs/research/`).
2. Threshold changes (`config/thresholds.py`) require an ADR citing
   observed behavior.
3. §17.1 `j02_status` VIEW is the single truth for J02 output.
4. J02 never writes to rows with `strategy_id != 'j02'`.
5. J02's A5 live-proven upgrade requires an additional DSR
   (Deflated Sharpe Ratio) post-hoc filter computed over the live
   shadow window — this is the v0.2.0 roadmap item (J02 is stricter
   than J01 about live-proven promotion).

## DEPLOYABLE tiers

Same schema as engine: `historical / fresh / live_proven`.
Only `live_proven` may auto-activate.

## Out of scope

Same as J01. J02 and J01 share engine; they only differ in fitness
and thresholds. No infra duplication.
