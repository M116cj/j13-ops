# 00 — State Lock

**ORDER**: 0-9AF-REDESIGN-EXCHANGE-STYLE-INTERNAL-OBSERVABILITY-TERMINAL-V2
**Date**: 2026-05-01
**Mode**: UI/UX REDESIGN / READ-ONLY OBSERVABILITY TERMINAL

## Frozen Baseline

| Item | Value |
|---|---|
| Branch | `phase-7/0-9af-dashboard-terminal-redesign` |
| Base HEAD | `a4ac5785` (parent: 0-9AF V1 squash merge) |
| Parent order | 0-9AF-INTERNAL-OBSERVABILITY-DASHBOARD-V1 |
| Owner complaint | V1 too article/report-like; wants exchange-terminal feel |
| zangetsu_status.deployable_count | 0 (unchanged, verified live) |
| A2_MIN_TRADES | 25 (unchanged) |
| Live trading / CANARY / production rollout | NONE |

## STOP Verification

- STOP-1 (write controls): NONE — read-only widgets only; no buttons trigger mutation
- STOP-2 (mining trigger): NONE
- STOP-3 (execution trigger): NONE
- STOP-4 (production DB mutation): NONE
- STOP-5 (Arena logic change): NONE
- STOP-6 (threshold change): NONE
- STOP-7 (deployable semantics change): NONE
- STOP-8 (public exposure): NONE — bind 100.123.49.102 (Tailscale) only
- STOP-9 (NO DATA shown as 0): rule enforced via theme + view-model None handling
- STOP-10 (NOT_EVALUATED shown as REJECTED): rule enforced — separate fields in arena VM
- STOP-11 (NEAR_SURVIVOR shown as SURVIVOR): rule enforced — two distinct artifacts + tables
- STOP-12 (forbidden mutation in diff): NONE (see 12)

## Working-Tree Sanity

Modifications limited to runtime byproducts (calcifer logs, engine.jsonl rotation) — NOT staged.
