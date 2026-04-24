# 0-9H — Short Re-SHADOW Report

Per TEAM ORDER 0-9H §10.

## 1. Source

Same log sources as 0-9G SHADOW:

- `zangetsu/logs/engine.jsonl` (308,579 lines, 38.6 MB)
- `zangetsu/logs/engine.jsonl.1` (14,213 lines, 2.5 MB)

Combined window: 2026-04-16 → 2026-04-23 (~7 days).

## 2. Event counts

| Metric | 0-9G | 0-9H |
|---|---:|---:|
| Total log lines scanned | 322,792 | 322,792 |
| Rejection candidate lines | 3,651 | 3,651 |
| Classified rejection events | 3,651 | 3,651 |

No change in volume — we re-classified the same log stream under the patched taxonomy.

## 3. Reason breakdown (before → after)

| Reason | 0-9G count | 0-9H count | Δ |
|---|---:|---:|---:|
| SIGNAL_TOO_SPARSE | 2,809 | **3,622** | +813 |
| OOS_FAIL | 29 | 29 | 0 |
| UNKNOWN_REJECT | 813 | **0** | −813 |

## 4. UNKNOWN_REJECT before / after

- Before (0-9G): **22.27 %** (813 / 3,651)
- After (0-9H):  **0.00 %** (0 / 3,651)
- Delta: **−22.27 pp** → drop below the 10 % GREEN threshold.

## 5. Arena 2 breakdown (before → after)

### Before (0-9G)

| Reason | Count | % of A2 |
|---|---:|---:|
| SIGNAL_TOO_SPARSE | 2,582 | 76.1 % |
| UNKNOWN_REJECT | 813 | 23.9 % |

### After (0-9H)

| Reason | Count | % of A2 |
|---|---:|---:|
| SIGNAL_TOO_SPARSE | **3,395** | **100.0 %** |

Arena 2 is now fully classified — 0 % UNKNOWN.

## 6. V10 mapping confirmation

All 5 patterns previously UNKNOWN are now classified as SIGNAL_TOO_SPARSE via the 2 new `RAW_TO_REASON` prefix aliases:

| Pattern | Freq | Pre-patch | Post-patch |
|---|---:|---|---|
| `[V10]: pos_count=0` | 783 | UNKNOWN_REJECT | SIGNAL_TOO_SPARSE |
| `[V10]: trades=1 < 25` | 13 | UNKNOWN_REJECT | SIGNAL_TOO_SPARSE |
| `[V10]: pos_count=0 < 2` | 8 | UNKNOWN_REJECT | SIGNAL_TOO_SPARSE |
| `[V10]: trades=0 < 25` | 8 | UNKNOWN_REJECT | SIGNAL_TOO_SPARSE |
| `[V10]: trades=4 < 25` | 1 | UNKNOWN_REJECT | SIGNAL_TOO_SPARSE |
| **Total** | **813** | | |

Mapping mechanism: substring-match against `"[V10]: pos_count"` or `"[V10]: trades"`. The classifier's existing substring-fallback logic covers every suffix variation in a single alias each.

## 7. Residual unknowns

**None.** `unmapped_raw_top20` from re-SHADOW summary: `{}` (empty).

## 8. Per-stage summary (post-patch)

| Stage | Events | Reason breakdown |
|---|---:|---|
| A1 | 227 | SIGNAL_TOO_SPARSE ×227 |
| A2 | 3,395 | SIGNAL_TOO_SPARSE ×3,395 |
| A3 | 29 | OOS_FAIL ×29 |

A0, A4, A5: 0 events in window (consistent with Arena frozen state).

## 9. Invariance verification

- No Arena runtime file was executed, modified, or restarted during re-SHADOW.
- Re-SHADOW wrapper (`/tmp/shadow_wrapper.py`) is read-only against engine.jsonl.
- Controlled-diff between pre-patch (0-9G) and post-patch (0-9H) snapshots confirms 0 forbidden diffs on all Arena runtime SHAs.
- Pre-existing test suite still passes (including `test_arena_gates_thresholds_unchanged` pinning A2_MIN_TRADES=25, A3_WR_FLOOR=0.45, etc.).

## 10. Interpretation

The post-patch re-SHADOW now surfaces the actual Arena 2 diagnostic message unambiguously:

> Every Arena 2 rejection in the observed 7-day window is SIGNAL_TOO_SPARSE — candidates fail to produce enough trades / positions to satisfy the A2_MIN_TRADES=25 gate or the paired position-count check.

This is a **candidate-quality** signal, not an Arena 2 defect. Arena 2 is performing exactly what its gate specifies. The question of whether to:
- Lower A2_MIN_TRADES (threshold mutation — forbidden without separate order),
- Improve A1 candidate generation so candidates produce more trades (out of 0-9H scope),
- Broaden signal windows (also out of scope),
- Accept that current Volume L9 DOE configuration produces sparse signals (status quo),

is a strategy decision for j13, not a taxonomy problem.
