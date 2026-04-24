# TEAM ORDER 0-9H — P7-PR1 V10 Taxonomy Mapping Patch Report

## 1. Status

| Field | Value |
|---|---|
| 0-9H status | **COMPLETE (GREEN verdict)** |
| Branch | `phase-7/p7-pr1-v10-taxonomy-mapping` |
| PR URL | _filled by merge step_ |
| origin/main before patch | `2c319c640c9543721afd537a960630e5f6a3449c` |
| Final main SHA | _filled post-merge_ |
| Pre-snapshot manifest | `1c65d4ee58ed02b585f7496f4ac3ccb2a4904e1713b7810c2f2c63df43908d63` |
| Post-snapshot manifest | `8aad5f63de492cc63644ab7ad5ecb7f973b3d8ab3588c6bf3a4e8d2b97da9911` |

## 2. Inherited finding (0-9G)

- UNKNOWN_REJECT ratio: **22.27 %** (RED).
- All 813 unknowns concentrated on 5 A2 V10 raw-string patterns from `arena23_orchestrator.py`:
  1. `[V10]: pos_count=0` (783)
  2. `[V10]: trades=1 < 25` (13)
  3. `[V10]: pos_count=0 < 2` (8)
  4. `[V10]: trades=0 < 25` (8)
  5. `[V10]: trades=4 < 25` (1)
- Semantic classification: all 5 = SIGNAL_TOO_SPARSE.

## 3. Patch scope

### 3.1 Files changed (2 source, 5 docs/snapshots)

- `zangetsu/services/arena_rejection_taxonomy.py` — +9 lines; 2 prefix aliases added to `RAW_TO_REASON`:
  ```python
  "[V10]: pos_count": RejectionReason.SIGNAL_TOO_SPARSE,
  "[V10]: trades":    RejectionReason.SIGNAL_TOO_SPARSE,
  ```
- `zangetsu/tests/test_arena_rejection_taxonomy.py` — +87 lines; 12 new test cases (see §4).
- `docs/recovery/20260424-mod-7/0-9h_p7_pr1_v10_taxonomy_mapping_patch_report.md` — this file.
- `docs/recovery/20260424-mod-7/0-9h_short_reshadow_report.md` — re-SHADOW evidence.
- `docs/recovery/20260424-mod-7/0-9h_go_no_go.md` — verdict.
- `docs/governance/snapshots/2026-04-24T081331Z-pre-0-9h.json` — pre-snapshot.
- `docs/governance/snapshots/2026-04-24T081500Z-post-0-9h.json` — post-snapshot.

### 3.2 Classifier behavior changed?

**NO.** `classify()` already supports exact-key match first then substring fallback. The 2 new prefix aliases leverage the existing substring fallback — no classifier logic change required. The classifier file has no functional edits besides appending 2 dict entries.

### 3.3 Forbidden files intentionally untouched

- Arena runtime: `arena_pipeline.py`, `arena23_orchestrator.py`, `arena45_orchestrator.py`, `arena_gates.py`, `arena13_feedback.py` — UNCHANGED.
- Calcifer: `supervisor.py`, `zangetsu_outcome.py` — UNCHANGED.
- Control plane: `zangetsu/control_plane/cp_api/*` — UNCHANGED.
- Thresholds: `zangetsu/services/arena_gates.py` constants (A2_MIN_TRADES=25, A3_*) — UNCHANGED.
- Workflows: `.github/workflows/*` — UNCHANGED.
- Branch protection: `{enforce_admins:true, req_sig:true, linear:true, force_push:false, deletions:false}` — UNCHANGED.

## 4. Tests

### 4.1 Full P7-PR1 suite

`pytest zangetsu/tests/test_arena_rejection_taxonomy.py zangetsu/tests/test_arena_telemetry.py zangetsu/tests/test_p7_pr1_behavior_invariance.py`
→ **58 passed, 0 failed, 1 pre-existing warning** in 0.14 s.

### 4.2 New test cases (12 added in `test_arena_rejection_taxonomy.py`)

1. `test_raw_to_reason_contains_v10_prefix_aliases` — asserts both aliases present in the dict.
2. `test_classify_v10_pos_count_zero_maps_to_signal_too_sparse` — `[V10]: pos_count=0` → SIGNAL_TOO_SPARSE.
3. `test_classify_v10_pos_count_0_lt_2_maps_to_signal_too_sparse` — `[V10]: pos_count=0 < 2` → SIGNAL_TOO_SPARSE.
4. `test_classify_v10_trades_1_lt_25_maps_to_signal_too_sparse` — `[V10]: trades=1 < 25` → SIGNAL_TOO_SPARSE.
5. `test_classify_v10_trades_0_lt_25_maps_to_signal_too_sparse` — `[V10]: trades=0 < 25` → SIGNAL_TOO_SPARSE.
6. `test_classify_v10_trades_4_lt_25_maps_to_signal_too_sparse` — `[V10]: trades=4 < 25` → SIGNAL_TOO_SPARSE.
7. `test_v10_substring_match_within_full_log_line` — full-log-line substring match works.
8. `test_unknown_reject_still_fallback_for_unmapped_strings` — UNKNOWN_REJECT still returned for novel strings.
9. `test_v10_aliases_do_not_shadow_existing_a1_counter_keys` — `reject_few_trades` still classifies correctly via its own key.
10. `test_taxonomy_reason_count_unchanged_after_v10_patch` — still 18 reasons.
11. `test_taxonomy_category_count_unchanged_after_v10_patch` — still 14 categories.
12. `test_taxonomy_severity_count_unchanged_after_v10_patch` — still 4 severities.

### 4.3 Behavior-invariance tests (existing)

`test_p7_pr1_behavior_invariance.py` still passes. Specifically `test_arena_gates_thresholds_unchanged` confirms A2_MIN_TRADES / A3_* / A3_WR_FLOOR all pinned; `test_arena2_pass_*` confirms Arena gate decision outputs unchanged.

## 5. Short re-SHADOW

Run against the same log sources as 0-9G:

- `zangetsu/logs/engine.jsonl` (308,579 lines)
- `zangetsu/logs/engine.jsonl.1` (14,213 lines)

**Combined**: 322,792 lines scanned, 3,651 rejection candidate lines, 3,651 classified rejection events.

### 5.1 UNKNOWN_REJECT comparison

| Metric | 0-9G (pre-patch) | 0-9H (post-patch) | Δ |
|---|---:|---:|---|
| Rejection events | 3,651 | 3,651 | — |
| Mapped | 2,838 | 3,651 | +813 |
| UNKNOWN_REJECT | 813 | **0** | −813 |
| **UNKNOWN_REJECT ratio** | **22.27 %** | **0.00 %** | **−22.27 pp** |

### 5.2 Arena 2 UNKNOWN_REJECT comparison

| Metric | 0-9G | 0-9H |
|---|---:|---:|
| A2 rejections | 3,395 | 3,395 |
| A2 UNKNOWN_REJECT | 813 | **0** |
| A2 UNKNOWN_REJECT ratio | 23.9 % | **0.00 %** |

### 5.3 Post-patch Arena 2 breakdown (100 % mapped)

| Reason | Count | % |
|---|---:|---:|
| SIGNAL_TOO_SPARSE | 3,395 | 100.0 % |

### 5.4 Post-patch per-stage reasons

| Stage | Reason | Count |
|---|---|---:|
| A1 | SIGNAL_TOO_SPARSE | 227 |
| A2 | SIGNAL_TOO_SPARSE | 3,395 |
| A3 | OOS_FAIL | 29 |

### 5.5 Residual unmapped register

Empty. `unmapped_raw_top20 = {}` post-patch.

## 6. Controlled-diff

- Pre-snapshot: `docs/governance/snapshots/2026-04-24T081331Z-pre-0-9h.json` (manifest `1c65d4ee...`).
- Post-snapshot: `docs/governance/snapshots/2026-04-24T081500Z-post-0-9h.json` (manifest `8aad5f63...`).
- Classification: **EXPLAINED**.
- Zero-diff: 43 fields (all Arena runtime + branch-protection + systemd SHAs unchanged).
- Explained-diff: 1 field (`repo.git_status_porcelain_lines 1 → 4` reflecting the staged 0-9H artifacts).
- **Forbidden diff: 0**.

## 7. Gate results (filled post-PR-open)

- **Gate-A**: _to be filled_ (expected: triggered on `pull_request` + PASS, since PR touches `zangetsu/**` which is in main's Gate-A trigger paths post-0-9F).
- **Gate-B**: _to be filled_ (expected: triggered on `pull_request` + PASS, since PR touches `zangetsu/**` which is in main's Gate-B trigger paths post-0-9F; if Gate-B still fails to trigger on pull_request, that is classified as a Gate-B workflow-level blocker requiring a separate debugging order).

## 8. Final verdict

```
VERDICT = GREEN

UNKNOWN_REJECT ratio:         0.00 % (< 10 % GREEN threshold)
Arena 2 UNKNOWN_REJECT ratio: 0.00 % (< 10 % GREEN threshold)
Tests:                        58/58 PASS
Controlled-diff:              EXPLAINED, 0 forbidden
Runtime mutation:             NONE
Branch protection:            INTACT

CANARY recommended:           conditional — see §8.1
P7-PR2 recommended:           NO (CANARY should complete first)
further mapping patch needed: NO (0 residual unknowns, 0 unmapped strings)
Gate-B debugging needed:      YES (if Gate-B fails to trigger on this PR)
```

### 8.1 CANARY conditionality

Taxonomy coverage is now GREEN (0 % UNKNOWN). However, promotion to CANARY also depends on:
- Gate-B actually triggering + passing on this PR (pending).
- j13 explicit authorization of CANARY (not granted by 0-9H).
- SHADOW observation period policy (0-9G ran 7-day window; longer SHADOW may be desired before CANARY).

This report makes the taxonomy side of the gate GREEN; whether to proceed to CANARY is j13's call via a separate order.

## 9. Correct interpretation (0-9H §8 rule)

- Taxonomy coverage improved from 77.7 % to 100 %.
- Arena 2 visibility improved from 76.1 % mapped to 100 % mapped.
- Arena 2 **root cause** remains signal / trade sparsity — `A2_MIN_TRADES=25` is the live gate; candidates in the observed 7-day window repeatedly produced trades or pos_counts below this bar. This is a **candidate-quality** signal, not an Arena 2 flaw.
- **NOT claimed**: Arena 2 is fixed. All Arenas are fixed. Champion generation is restored. Production readiness achieved. CANARY started. P7-PR2 started.

## 10. STOP

Per 0-9H §14, no STOP condition triggered. Per 0-9H §16, `TEAM ORDER 0-9H = COMPLETE` upon merge. Next authorized action requires a separate order.
