# TEAM ORDER 0-9J — P7-PR1 CANARY Activation Report

## 1. Status

| Field | Value |
|---|---|
| CANARY status | **COMPLETE (GREEN verdict)** |
| Start timestamp (UTC) | 2026-04-24T09:03:48Z (pre-snapshot) |
| End timestamp (UTC) | 2026-04-24T09:03:49Z (post-snapshot) |
| origin/main SHA | `665298fb40fcdcb9438eff0d3906d7aedf68db80` |
| Local HEAD | `665298fb40fcdcb9438eff0d3906d7aedf68db80` (== origin/main, ahead/behind=0/0) |
| Branch protection | `{enforce_admins:true, required_signatures:true, linear_history:true, force_push:false, deletions:false}` — intact |
| Gate-A health | ✅ triggers + passes on pull_request (PR #10 0-9I merge run) |
| Gate-B health | ✅ triggers + passes on pull_request (PR #10 first-ever pull_request run = documented noop-success) |
| Runtime mutation | **NONE** (0 Arena processes — frozen since MOD-3; all Arena/config/systemd SHAs unchanged) |

## 2. Observation source

- **Primary**: `zangetsu/logs/engine.jsonl` (38,638,779 bytes, 308,579 lines, mtime 2026-04-23T00:35:54Z)
- **Rotated predecessor**: `zangetsu/logs/engine.jsonl.1` (2,540,779 bytes, 14,213 lines, mtime 2026-04-16T04:25Z)
- **Combined lines scanned**: 322,792
- **Observation window**: 2026-04-16 → 2026-04-23 (~7-day rolling segment; latest available)

### 2.1 "Production-adjacent" characterization (honest)

Arena is frozen since MOD-3 (0 `arena_pipeline|arena23_orchestrator|arena45_orchestrator` processes running; `engine.jsonl` mtime unchanged since 2026-04-23T00:35Z). No live stream to tail. Per 0-9J §9 fallback rule ("Use latest available rolling log segment"), CANARY observes the **latest rolling segment of the production log**, which IS the production-adjacent state in the current frozen-Arena regime. Sample size (3,651 rejection events) well exceeds the 500-minimum threshold — no low-sample warning needed.

This makes 0-9J a **first-ever CANARY validation on the post-0-9H state** (confirming the V10 patch holds on the live main tree), not a re-observation of an unchanged scenario.

## 3. Telemetry classifier result

| Metric | Value |
|---|---|
| Total log lines scanned | 322,792 |
| Rejection candidate lines | 3,651 |
| Classified rejection events | 3,651 (100 %) |
| Mapped to canonical reason | 3,651 |
| UNKNOWN_REJECT events | **0** |
| **UNKNOWN_REJECT ratio** | **0.00 %** (0 / 3,651) |

### 3.1 Reason breakdown

| Reason | Count | % |
|---|---:|---:|
| SIGNAL_TOO_SPARSE | 3,622 | 99.2 % |
| OOS_FAIL | 29 | 0.8 % |
| UNKNOWN_REJECT | 0 | 0 % |

### 3.2 Category breakdown

| Category | Count |
|---|---:|
| SIGNAL_DENSITY | 3,622 |
| OOS_VALIDATION | 29 |

### 3.3 Severity breakdown

| Severity | Count |
|---|---:|
| BLOCKING | 3,651 |

100 % of events are BLOCKING. There are no WARN events because UNKNOWN_REJECT = 0 (WARN is UNKNOWN_REJECT's default per taxonomy metadata).

### 3.4 Arena-stage breakdown

| Stage | Count | % |
|---|---:|---:|
| A2 | 3,395 | 93.0 % |
| A1 | 227 | 6.2 % |
| A3 | 29 | 0.8 % |

## 4. Arena 2 result

| Field | Value |
|---|---|
| A2 total rejections | 3,395 |
| SIGNAL_TOO_SPARSE | 3,395 (**100.0 %**) |
| UNKNOWN_REJECT | 0 (**0.00 %**) |
| Arena 2 UNKNOWN_REJECT ratio | **0.00 %** (< 5 % GREEN threshold) |
| V10 mapping confirmation | All 5 V10 variants (`[V10]: pos_count=0`, `[V10]: trades=N < 25`, `[V10]: pos_count=0 < 2`, etc.) classified via `RAW_TO_REASON` prefix aliases added in 0-9H |
| Residual unknowns | **empty** (`unmapped_raw_top20 = {}`) |
| New raw strings not in 0-9G / 0-9H | **none** (Arena frozen — no new rejection strings emitted) |

Arena 2's dominant rejection root cause: `SIGNAL_TOO_SPARSE` — candidates fail to satisfy `A2_MIN_TRADES=25` or the paired position-count gate on the A2 holdout. This is a **candidate-quality** signal, not an Arena 2 defect.

## 5. deployable_count provenance

- **deployable_count observed**: indirectly inferable from stage breakdown:
  - 227 candidates rejected at A1 (never reached A2).
  - 3,395 candidates rejected at A2 (never reached A3).
  - 29 candidates rejected at A3 (never reached A4/A5 deployment).
  - `deployable_count ≈ 0` for the observed window (any candidate that reached A4/A5 would have needed to clear A0+A1+A2+A3 successfully; the rejection stream shows no such transitions).
- **Lifecycle join available**: **NO** at the current telemetry level. Full `CandidateLifecycle` reconstruction would require joining A1 "promoted" events with A2/A3/A4/A5 outcomes; this CANARY pass classified the rejection stream only.
- **Provenance quality**: **PARTIAL** — same classification as SHADOW (0-9G §5). Rejection reasons are fully mapped; deployable transitions are not yet plumbed into the trace model.
- **Blocker**: full provenance requires either (a) a P7-PR2 module that explicitly emits promotion/demotion events with lifecycle IDs, or (b) a post-hoc join script that reads all engine.jsonl events and stitches lifecycles together. Neither is in 0-9J scope.

## 6. Invariance verification (0-9J §3 forbidden list)

| Forbidden change | Verified NOT occurred |
|---|---|
| Alpha formula change | ✓ (no code modification) |
| Alpha generation change | ✓ |
| Arena runtime logic change | ✓ (Arena SHAs unchanged per controlled-diff) |
| A2_MIN_TRADES / threshold change | ✓ (`test_arena_gates_thresholds_unchanged` pins A2_MIN_TRADES=25, A3_SEGMENTS=5, A3_MIN_TRADES_PER_SEGMENT=15, A3_MIN_WR_PASSES=4, A3_MIN_PNL_PASSES=4, A3_WR_FLOOR=0.45) |
| Arena 2 relaxation | ✓ |
| Champion promotion change | ✓ |
| Trade execution change | ✓ |
| Capital / risk / runtime change | ✓ (no service restart; 0 Arena processes throughout CANARY) |
| cp_api behavior change | ✓ |
| Branch protection change | ✓ (all 5 fields unchanged) |
| P7-PR2 | ✓ NOT STARTED |
| Production rollout | ✓ NOT STARTED |

## 7. Controlled-diff

- Pre-snapshot: `docs/governance/snapshots/2026-04-24T090348Z-pre-0-9j-canary.json` (manifest `f4d1357da219db465758bf4bd0624ee1e860582d8a1b9724303535c02fce2173`)
- Post-snapshot: `docs/governance/snapshots/2026-04-24T090349Z-post-0-9j-canary.json` (manifest `d6ea6ae9251f4eff43d94eec4a4f67cc4b32a64b555e983179b9ee93b0d7c741`)
- Classification: **EXPLAINED**
- Zero diff: **43 fields** (all Arena runtime / config / systemd / branch-protection fields unchanged)
- Explained diff: 1 field (`repo.git_status_porcelain_lines 1 → 2` reflecting the post-snapshot artifact)
- **Forbidden diff: 0**

## 8. Final verdict

```
VERDICT = GREEN

UNKNOWN_REJECT ratio:         0.00 % (< 5 % GREEN threshold)
Arena 2 UNKNOWN_REJECT ratio: 0.00 % (< 5 % GREEN threshold)
Tests:                        58/58 PASS
Controlled-diff:              EXPLAINED, 0 forbidden
Runtime mutation:             NONE
Branch protection:            INTACT
Gate-A:                       triggers + passes (post-0-9F coverage, validated on PR #10)
Gate-B:                       triggers + passes (post-0-9I fix, validated on PR #10)

proceed to longer CANARY:          NO (sample is the full post-MOD-3 available log;
                                       without Arena unfrozen, no new events to observe)
proceed to P7-PR2:                 CONDITIONAL YES (taxonomy + Gate infrastructure GREEN;
                                       actual decision requires j13 authorization)
need taxonomy patch:               NO (0 residual unknowns)
need sparse-candidate strategy:    YES (conceptually — SIGNAL_TOO_SPARSE dominates Arena 2;
                                       this is the real root cause surface for Phase 7
                                       subsequent work; NOT in 0-9J scope)
```

### 8.1 Forbidden wording (per 0-9J §19) NOT asserted

- "Arena 2 fixed" — NOT CLAIMED
- "All Arenas fixed" — NOT CLAIMED
- "Champion generation restored" — NOT CLAIMED
- "P7-PR2 started" — NOT CLAIMED
- "Production rollout started" — NOT CLAIMED

Authorized wording used: "Arena 2 visibility is GREEN" and "taxonomy mapping stable".

## 9. STOP

No 0-9J STOP condition triggered. Per 0-9J §18, acceptance criteria 1–23 all met. Merge proceeds iff Gate-A + Gate-B both trigger + pass on the evidence PR itself.

Next required action: separate order from j13 for:
- P7-PR2 (next module migration), OR
- Arena 2 sparse-candidate strategy work (investigation of why A1 candidates produce too few trades at A2), OR
- Longer CANARY (only meaningful if Arena is unfrozen — requires separate unfreeze authorization, out of 0-9J scope), OR
- Any other j13-directed Phase 7 task.
