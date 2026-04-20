# Zangetsu — Project-level CLAUDE.md
# Extends (never contradicts) ~/.claude/CLAUDE.md. Per global §14.

## Scope

Alpha discovery pipeline for Sub-Account A (Sharpe Quant Class).
Primary goal: produce at least one DEPLOYABLE alpha per month that
shows stable PnL / win-rate / trade-count under live market conditions.

## Hard rules (this project)

1. No code path may read a password/API key with a fallback default.
   Use `os.environ['KEY']` exclusively; let a missing key raise.
2. All DB/Redis/LLM secrets live in `secret/` (gitignored).
   `secret.example/` is the committed schema — update both together.
3. Any "done / deployed / version bumped" claim must be verified against
   `SELECT * FROM zangetsu_status;` — global §17.1. Inline count queries
   or git-commit-message claims are not acceptable.
4. Service restart check (global §17.6) is mandatory before any version
   bump: `systemctl show <svc> ActiveEnterTimestamp >= source mtime`.
5. `feat(zangetsu/vX.Y)` commits may only be emitted by
   `bin/bump_version.py` (global §17.5). Manual version-bump commits are
   rejected by the pre-commit hook.

## DEPLOYABLE tiers

`champion_pipeline.deployable_tier` ∈ { `historical`, `fresh`, `live_proven` }.
Only `live_proven` may auto-enter `card_status='ACTIVE'`. The others are
watchlist items and require j13 explicit approve.

## Arena layout (post-2026-04-20 reconstruction)

| Gate | Data              | Check                                                        |
|------|-------------------|--------------------------------------------------------------|
| A1   | training window   | GP fitness = mean(IC_early) × mean(IC_late) − |diff|; same sign |
| A2   | holdout first 1/3 | trades ≥ 25 ∧ total PnL > 0                                  |
| A3   | holdout mid 1/3, 5 segments | ≥ 4/5 segments with WR > 0.45 ∧ PnL > 0            |
| A4   | holdout last 1/3, regime-tagged | train regime WR > 0.40 ∧ ≥ 1 other regime WR > 0.40 |
| A5   | 14-day live paper-trade shadow | WR > 0.45 ∧ total PnL > 0 ∧ max_consecutive_neg_days < 3 |

See `docs/decisions/20260420-arena-reconstruction.md` for full rationale.

## Folder conventions (this project, consistent with global §18)

- `config/` — parameters, no hardcoded magic numbers. SQL in `config/sql/`.
- `engine/` — pure algorithm (no IO).
- `services/` — long-running orchestrators (systemd-managed).
- `live/` — realtime data subscription and execution.
- `dashboard/`, `console/` — HTTP API surfaces.
- `scripts/` — one-shot tools (seed / analysis / migration helpers).
- `tests/` — pytest. Smoke tests required for every `vX.Y` bump.
- `docs/decisions/` — dated ADRs, Traditional Chinese.
- `docs/retros/` — dated retros, one per /team session.
- `docs/arch/` — draw.io XML.
- `docs/refactor-history/` — historical spec/meeting notes kept for archaeology.
- `archive/` — frozen snapshots of prior versions, read-only.
- `migrations/postgres/` — versioned SQL migrations.
- `secret/` — gitignored runtime credentials.
- `secret.example/` — committed template.
- `scratch/` — local experiments (global §17.8 reaper applies).
- `data/`, `logs/`, `.venv/`, `graphify-out/` — gitignored.
