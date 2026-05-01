# 01 — Scope Lock

**ORDER**: 0-9AF — Phase 1

## In Scope (per order §3.1)

10 pages: Overview, Core Factory, A1, A2, A3, Candidates, Survivors, Rejects, Feedback, System Health.
- Internal-only deployment (127.0.0.1:8785 via systemd user unit)
- Read-only adapters reading `shadow_outputs/*` artifacts
- Freshness badges, no-fake-zero, NOT_EVALUATED separate from REJECTED, survivor separate from near-survivor

## Out of Scope (per order §3.2)

- live trading UI
- control plane / write controls
- threshold editor
- execution / capital / risk controls
- champion promotion controls
- maker-only / VIP / orderbook tooling
- new mining / arena / axis logic
- production rollout
