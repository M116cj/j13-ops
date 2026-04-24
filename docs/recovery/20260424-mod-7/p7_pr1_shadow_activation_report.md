# P7-PR1 SHADOW Activation Report

Per TEAM ORDER 0-9G.

## 1. Status

| Field | Value |
|---|---|
| SHADOW status | **COMPLETE (RED verdict)** |
| Start timestamp (UTC) | 2026-04-24T07:39:04Z (pre-snapshot) |
| End timestamp (UTC) | 2026-04-24T07:41:04Z (post-snapshot) |
| origin/main SHA | `dd98f34bcf15bd28b43187c4ba1838a97b887c0c` |
| Local HEAD | `dd98f34bcf15bd28b43187c4ba1838a97b887c0c` (== origin/main, ahead/behind=0/0) |
| Branch protection | `{enforce_admins:true, required_signatures:true, linear_history:true, force_push:false, deletions:false}` — intact |
| Runtime mutation | **NONE** (Arena SHAs unchanged per controlled-diff; zero service restart) |

## 2. Observation source

- **Primary log**: `zangetsu/logs/engine.jsonl` (38,638,779 bytes, 308,579 lines, mtime 2026-04-23T00:35Z).
- **Rotated predecessor**: `zangetsu/logs/engine.jsonl.1` (2,540,779 bytes, 14,213 lines, mtime 2026-04-16T04:25Z).
- **Combined observation window**: 2026-04-16 → 2026-04-23 (~7 days of Arena pipeline runs).
- **SHADOW wrapper**: `/tmp/shadow_wrapper.py` (read-only classifier; not committed — infrastructure scaffold for SHADOW-only operation).

## 3. Telemetry classifier result

| Metric | Value |
|---|---|
| Total log lines scanned | 322,792 |
| Rejection candidate lines (after filtering out summaries) | 3,651 |
| Classified rejection events | 3,651 |
| Mapped to canonical reason | 2,838 |
| UNKNOWN_REJECT events | 813 |
| **UNKNOWN_REJECT ratio** | **22.27%** (813 / 3,651) |

**Verdict threshold** (0-9G §5):
- Green: < 10 % → not met
- Yellow: 10–15 % → not met
- **Red: > 15 % → MET**

### 3.1 Reason breakdown (total 3,651 events)

| Reason | Count | % |
|---|---|---|
| SIGNAL_TOO_SPARSE | 2,809 | 76.9 % |
| UNKNOWN_REJECT | 813 | 22.3 % |
| OOS_FAIL | 29 | 0.8 % |

### 3.2 Category breakdown

| Category | Count |
|---|---|
| SIGNAL_DENSITY | 2,809 |
| UNKNOWN | 813 |
| OOS_VALIDATION | 29 |

### 3.3 Severity breakdown

| Severity | Count |
|---|---|
| BLOCKING | 2,838 |
| WARN | 813 |

### 3.4 Arena-stage breakdown

| Stage | Count | % |
|---|---|---|
| A2 | 3,395 | 93.0 % |
| A1 | 227 | 6.2 % |
| A3 | 29 | 0.8 % |

**Arena 2 is the dominant rejection stage** — 93 % of observed rejections happen at A2.

## 4. Arena 2 breakdown (3,395 A2 rejections)

| Canonical reason | Count | % of A2 |
|---|---|---|
| SIGNAL_TOO_SPARSE | 2,582 | 76.1 % |
| UNKNOWN_REJECT | 813 | 23.9 % |
| FRESH_FAIL | 0 | 0 % |
| OOS_FAIL | 0 | 0 % |
| REGIME_FAIL | 0 | 0 % |
| SIGNAL_TOO_DENSE | 0 | 0 % |
| PROMOTION_BLOCKED | 0 | 0 % |
| COST_NEGATIVE | 0 | 0 % |

Raw-string distribution behind A2 SIGNAL_TOO_SPARSE (2,582): the single dominant pattern is `<2 valid indicators after zero-MAD filter` — all 2,582 occurrences. This is an A2 dedup / indicator-variance rejection.

All 813 UNKNOWN_REJECT events are **A2 V10 patterns** not yet mapped in `RAW_TO_REASON`. See `p7_pr1_shadow_unknown_reject_register.md` for the full enumeration.

## 5. deployable_count provenance

- **deployable_count observed**: not directly computed in this SHADOW pass. `engine.jsonl` events describe rejection trajectories but not final deployable pool size.
- **Source path**: no authoritative field. `engine.jsonl` emits event-stream summaries like `"A2 stats: processed=1 promoted=1 rejected=0"` — promoted counter implies deployable, but promotion is not the same as deployable (deployable requires A3+A4 clearance per CandidateLifecycle contract).
- **Lifecycle reconstruction**: partial — rejections are tied to `id=<N>` per log line; a full `CandidateLifecycle` record requires joining A1 origin events with A2/A3 outcomes. This SHADOW pass focused on rejection classification and does not include the join.
- **rejected_ids_by_stage / non_deployable_reasons**: not computed in this pass. See `p7_pr1_shadow_rejection_breakdown.md` for the per-stage reason distribution that would populate these fields if the candidate_id → lifecycle join were performed.
- **Gap**: to answer `deployable_count == 0` provenance fully, a follow-up pass must parse A1 "promoted" events AND link them to downstream A2/A3/A4 outcomes. This requires a richer observation query than this SHADOW pass (a full candidate dataframe join rather than a rejection-stream classification).

## 6. Invariance verification (0-9G §3 — no forbidden change)

| Invariant | Verified NOT occurred |
|---|---|
| Alpha formula change | ✓ (no code modification) |
| Alpha generation change | ✓ |
| Arena runtime logic change | ✓ (Arena file SHAs unchanged in controlled-diff) |
| Arena threshold change | ✓ |
| Arena 2 relaxation | ✓ |
| Champion promotion change | ✓ |
| Trade execution change | ✓ |
| Capital behavior change | ✓ |
| Risk limit change | ✓ |
| Production runtime change | ✓ (no service restart; engine.jsonl only read, never written) |
| cp_api behavior change | ✓ |
| Branch protection change | ✓ (all 5 fields unchanged) |
| CANARY activation | ✓ NOT STARTED |
| P7-PR2 | ✓ NOT STARTED |
| Production rollout | ✓ NOT STARTED |

## 7. Controlled-diff

- Pre-snapshot: `docs/governance/snapshots/2026-04-24T073904Z-pre-0-9g-shadow.json` (manifest `2214767c3e846833b063b3a46607cb8886f5f7dfd0c9b1807a532b30efe15a74`).
- Post-snapshot: `docs/governance/snapshots/2026-04-24T074104Z-post-0-9g-shadow.json` (manifest `1d7135198c6fbc366bd0f6eb90828e579c8970c29f82ade943de04d0d93d6f02`).
- Classification: **EXPLAINED**.
- Zero diff: 43 fields (all Arena runtime + config + systemd + branch protection SHAs unchanged).
- Explained diff: 1 field (`repo.git_status_porcelain_lines 1 → 2` reflecting the new post-snapshot artifact on disk).
- **Forbidden diff: 0**.

## 8. Final verdict

```
Verdict: RED

Rationale:
  UNKNOWN_REJECT ratio = 22.27 % (> 15 % threshold per 0-9G §5).
  All 813 unknowns concentrate on 5 A2 V10 raw-reason patterns not yet in RAW_TO_REASON.
  Taxonomy classifier works structurally — classification is deterministic and
  never raised. The gap is mapping coverage, not engine correctness.

Positive findings:
  - 76.9 % of rejections cleanly map to SIGNAL_TOO_SPARSE (dominant signal).
  - 100 % of A3 rejections clean-mapped (all OOS_FAIL).
  - 100 % of A1 rejections clean-mapped (all SIGNAL_TOO_SPARSE).
  - Zero forbidden diffs; zero runtime mutation.
  - Branch protection and all governance invariants preserved.
  - Arena 2 is identified as the 93 %-dominant rejection stage.

Next-action recommendation (choose one, each needs a separate order):
  (A) P7-PR1 taxonomy mapping patch — add 5 V10 patterns to RAW_TO_REASON.
      After this patch, SHADOW re-run should produce < 1 % UNKNOWN_REJECT.
      This is the cleanest YELLOW→GREEN transition path.
  (B) Extended SHADOW window — continue observation with current mapping to
      gather more patterns before patching. Not recommended given (A) is a
      surgical 5-string addition.
  (C) P7-PR2 — next module migration. NOT RECOMMENDED. Taxonomy is not yet
      ready for production-adjacent observation given the 22 % UNKNOWN rate.
  (D) STOP further Phase 7 work — j13 decision.

CANARY: NOT recommended until at least Option A completes and re-SHADOW
produces < 10 % UNKNOWN_REJECT.

proceed to CANARY:     NO (unknown ratio > 10 %)
proceed to P7-PR2:     NO (taxonomy incomplete)
need taxonomy patch:   YES (5 V10 patterns identified)
need longer SHADOW:    NO (after mapping patch, a short re-SHADOW suffices)
```

STOP.
