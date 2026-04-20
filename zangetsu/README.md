# Zangetsu — Alpha Discovery Pipeline

Genetic-programming alpha discovery for Sub-Account A (Sharpe Quant Class).
Live on Alaya. Managed by the five-agent team (Claude lead, Gemini adversary,
Codex executor, Calcifer infra, Markl research).

## Quick pointers

| Aim                    | See                                   |
|------------------------|----------------------------------------|
| Project constitution   | `../CLAUDE.md` §17 (global)            |
| Project-level rules    | [`CLAUDE.md`](./CLAUDE.md)             |
| Version history        | [`VERSION_LOG.md`](./VERSION_LOG.md)   |
| Canonical `*_status` VIEW | [`config/sql/zangetsu_status_view.sql`](./config/sql/zangetsu_status_view.sql) |
| Decisions (dated)      | [`docs/decisions/`](./docs/decisions/) |
| Retros (per /team run) | [`docs/retros/`](./docs/retros/)       |
| Architecture XML       | [`docs/arch/`](./docs/arch/)           |
| Arena A1→A5 orchestrators | [`services/`](./services/)          |
| GP engine              | [`engine/components/`](./engine/components/) |
| Secrets template       | [`secret.example/`](./secret.example/) |
| Real secrets           | `secret/` (gitignored, 700/600)        |

## Pipeline (A1 → A5)

A1 GP evolve → A2 OOS PnL gate → A3 time-segment stability → A4 regime
stability → A5 real-world validation (live paper-trade shadow). Only
`tier=live_proven` DEPLOYABLE alphas auto-enter the active pool.

See `docs/decisions/20260420-arena-reconstruction.md` for the current gate
specifications.

## Running locally

Zangetsu is not designed to run on macOS. Development happens in `scratch/`
sandboxes; production runs under systemd on Alaya. Bring-up steps live in
`deploy/` and `zangetsu_ctl.sh`.
