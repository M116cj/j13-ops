# 0-9J CANARY — Rejection Breakdown

Per TEAM ORDER 0-9J §13.

## 1. Source

- `zangetsu/logs/engine.jsonl` (308,579 lines, 38.6 MB, mtime 2026-04-23T00:35Z)
- `zangetsu/logs/engine.jsonl.1` (14,213 lines, 2.5 MB, mtime 2026-04-16T04:25Z)
- Combined lines scanned: 322,792
- Window: 2026-04-16 → 2026-04-23 (~7-day rolling segment; latest available production-adjacent state)
- Total classified rejection events: **3,651**

## 2. Stage × Reason matrix

| Stage | Reason | Count | % of stage |
|---|---|---:|---:|
| A1 | SIGNAL_TOO_SPARSE | 227 | 100 % |
| A2 | SIGNAL_TOO_SPARSE | 3,395 | 100 % |
| A3 | OOS_FAIL          | 29  | 100 % |

A0, A4, A5: **0 events** (Arena frozen since MOD-3; no A0 entries or A4/A5 promotions emitted in this window).

## 3. Raw-string distribution (top patterns, complete enumeration)

| Rank | Raw reason | Count | Canonical reason |
|---:|---|---:|---|
| 1 | `<2 valid indicators after zero-MAD filter` | 2,582 | SIGNAL_TOO_SPARSE |
| 2 | `[V10]: pos_count=0` | 783 | SIGNAL_TOO_SPARSE (via V10 prefix alias from 0-9H) |
| 3 | `reject_few_trades` | 227 | SIGNAL_TOO_SPARSE |
| 4 | `validation split fail` | 17 | OOS_FAIL |
| 5 | `[V10]: trades=1 < 25` | 13 | SIGNAL_TOO_SPARSE (via V10 prefix alias) |
| 6 | `train/val PnL divergence` | 12 | OOS_FAIL |
| 7 | `[V10]: pos_count=0 < 2` | 8 | SIGNAL_TOO_SPARSE (via V10 prefix alias) |
| 8 | `[V10]: trades=0 < 25` | 8 | SIGNAL_TOO_SPARSE (via V10 prefix alias) |
| 9 | `[V10]: trades=4 < 25` | 1 | SIGNAL_TOO_SPARSE (via V10 prefix alias) |

**Every raw string maps to a canonical reason.** Residual unmapped = **0**.

## 4. Category distribution

| Category | Count | % |
|---|---:|---:|
| SIGNAL_DENSITY | 3,622 | 99.2 % |
| OOS_VALIDATION | 29 | 0.8 % |
| UNKNOWN | 0 | 0.0 % |

## 5. Severity distribution

| Severity | Count | % |
|---|---:|---:|
| BLOCKING | 3,651 | 100 % |
| WARN | 0 | 0 % |
| FATAL | 0 | 0 % |
| INFO | 0 | 0 % |

Every rejection is BLOCKING severity. No UNKNOWN_REJECT WARN events remain.

## 6. Before / after comparison vs SHADOW baseline

| Metric | 0-9G SHADOW | 0-9H re-SHADOW | 0-9J CANARY |
|---|---:|---:|---:|
| Events | 3,651 | 3,651 | 3,651 |
| Mapped | 2,838 | 3,651 | **3,651** |
| UNKNOWN_REJECT | 813 | 0 | **0** |
| UNKNOWN_REJECT ratio | 22.27 % | 0.00 % | **0.00 %** |
| A2 UNKNOWN_REJECT ratio | 23.9 % | 0.00 % | **0.00 %** |
| V10 mapping | gap | covered | **covered (unchanged)** |

0-9J confirms the 0-9H patch holds on the post-merge main state (`665298fb`).

## 7. Arena 2 root cause (exposed, not solved)

Arena 2 produces 93 % of all rejections, and 100 % of A2 rejections are now `SIGNAL_TOO_SPARSE`. The real Arena 2 bottleneck is:

> Candidates produced by the upstream A1 pipeline do not generate enough trades or positions on the A2 holdout window to satisfy the `A2_MIN_TRADES=25` threshold and paired position-count gate.

This is a **candidate-quality** signal, not an Arena 2 defect. Arena 2 is performing exactly what its gate specifies. The solution space (NOT in 0-9J scope) includes:
- Lowering A2_MIN_TRADES (threshold mutation — forbidden without separate order)
- Improving A1 candidate generation so candidates produce more trades
- Broadening signal windows
- Accepting that current Volume L9 DOE configuration produces sparse signals (status quo)

## 8. Invariance verification

- No Arena runtime file executed, modified, or restarted during CANARY.
- CANARY wrapper (`/tmp/shadow_wrapper.py`) is read-only against engine.jsonl.
- Controlled-diff confirms 0 forbidden diffs on all Arena runtime SHAs and branch protection.
- P7-PR1 test suite (58 tests) passes before and after CANARY.
