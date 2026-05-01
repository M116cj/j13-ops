# 00 — State Lock

**ORDER**: 0-9AF-MOBILE-TERMINAL-V3 (response to owner: V2 unusable on mobile)
**Date**: 2026-05-01
**Mode**: MOBILE-FIRST UI/UX REDESIGN / READ-ONLY OBSERVABILITY

## Frozen Baseline

| Item | Value |
|---|---|
| Branch | `phase-7/0-9af-mobile-terminal-v3` |
| Base HEAD | `3ce5153c` (parent: 0-9AF V2 redesign squash merge) |
| Parent verdict | DASHBOARD_TERMINAL_V2_DEPLOYED_GREEN |
| Owner verdict | V2 unusable on phone — needs mobile-first OKX-style |
| zangetsu_status.deployable_count | 0 (unchanged, verified live) |
| A2_MIN_TRADES | 25 (unchanged) |
| Live trading / CANARY / production rollout | NONE |

## STOP Verification

- STOP-1 (write controls): NONE — FastAPI route enumeration test rejects POST/PUT/PATCH/DELETE
- STOP-2 (mining trigger): NONE
- STOP-3 (execution trigger): NONE
- STOP-4 (production DB mutation): NONE — file IO only
- STOP-5 (Arena logic change): NONE
- STOP-6 (threshold change): NONE
- STOP-7 (deployable semantics change): NONE
- STOP-8 (public exposure): NONE — bind 100.123.49.102 (Tailscale) only
- STOP-9 (NO DATA shown as 0): rule enforced via template conditionals + explicit 'NO DATA' / 'NOT_REACHED' strings
- STOP-10 (NOT_EVALUATED shown as REJECTED): rule enforced — separate topbar pills + arena VM fields
- STOP-11 (NEAR_SURVIVOR shown as SURVIVOR): rule enforced — two distinct `<table>` blocks on /survivors
- STOP-12 (forbidden mutation in diff): NONE (see 12)

## Working-Tree Sanity

Modifications limited to runtime byproducts (calcifer logs, engine.jsonl rotation) — NOT staged.
