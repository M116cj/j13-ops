# P7-PR1 SHADOW — Rejection Breakdown

Per TEAM ORDER 0-9G §10.

Consolidated view of rejection events observed during SHADOW, broken down by
Arena stage × canonical reason × category × severity.

## 1. Source

- `zangetsu/logs/engine.jsonl` (308,579 lines) + `zangetsu/logs/engine.jsonl.1` (14,213 lines)
- Combined scanned: 322,792 lines
- Window: 2026-04-16 → 2026-04-23 (~7 days)
- Total classified rejection events: **3,651**

## 2. Stage × Reason matrix

| Stage | Reason | Count | % of stage |
|---|---|---:|---:|
| A1 | SIGNAL_TOO_SPARSE | 227 | 100 % |
| A2 | SIGNAL_TOO_SPARSE | 2,582 | 76.1 % |
| A2 | UNKNOWN_REJECT    | 813   | 23.9 % |
| A3 | OOS_FAIL          | 29    | 100 % |

A0 and A4: zero observed rejection events in this window. This is consistent with Arena being frozen since MOD-3 — no fresh A0 entries were produced during the observation window.

## 3. Raw-string distribution (top 20 by frequency)

| Rank | Raw reason string | Count | Mapped canonical reason |
|---:|---|---:|---|
| 1 | `<2 valid indicators after zero-MAD filter` | 2,582 | SIGNAL_TOO_SPARSE |
| 2 | `[V10]: pos_count=0` | 783 | **UNKNOWN_REJECT** (needs mapping) |
| 3 | `reject_few_trades` | 227 | SIGNAL_TOO_SPARSE |
| 4 | `validation split fail` | 17 | OOS_FAIL |
| 5 | `[V10]: trades=1 < 25` | 13 | **UNKNOWN_REJECT** (needs mapping) |
| 6 | `train/val PnL divergence` | 12 | OOS_FAIL |
| 7 | `[V10]: pos_count=0 < 2` | 8 | **UNKNOWN_REJECT** (needs mapping) |
| 8 | `[V10]: trades=0 < 25` | 8 | **UNKNOWN_REJECT** (needs mapping) |
| 9 | `[V10]: trades=4 < 25` | 1 | **UNKNOWN_REJECT** (needs mapping) |

## 4. Category distribution

| Category | Count | % |
|---|---:|---:|
| SIGNAL_DENSITY | 2,809 | 76.9 % |
| UNKNOWN | 813 | 22.3 % |
| OOS_VALIDATION | 29 | 0.8 % |

## 5. Severity distribution

| Severity | Count | % |
|---|---:|---:|
| BLOCKING | 2,838 | 77.7 % |
| WARN | 813 | 22.3 % |

(WARN is UNKNOWN_REJECT's default per REJECTION_METADATA. After the 5-pattern mapping patch, the 813 WARN events would reclassify to BLOCKING — reason SIGNAL_TOO_SPARSE — matching the expected A2 severity for sparse-signal rejections.)

## 6. Dominance story

1. **A2 dominates** (93.0 % of all rejections). Arena 2 is where the candidate funnel narrowest.
2. Within A2, the single largest rejection cause is the **zero-MAD indicator filter** (2,582 events, 76 % of A2). This rejects candidates whose indicators have near-zero variance across the holdout window.
3. **Position / trade-count gates** (`pos_count=0`, `trades<25`) produce 813 additional A2 rejections, currently showing as UNKNOWN because the V10 raw-string pattern is not in `RAW_TO_REASON`. Semantically these are SIGNAL_TOO_SPARSE.
4. **A3** produces only 29 rejections — all `validation split fail` / `train/val PnL divergence` (both map to OOS_FAIL). A3 is cleanly classified.
5. **A1** produces 227 rejections, all `reject_few_trades` → SIGNAL_TOO_SPARSE. A1 is cleanly classified.

Arena 2 is the real bottleneck. After the mapping patch, Arena 2's top two reasons would become:
- SIGNAL_TOO_SPARSE (non-V10 variant): 2,582
- SIGNAL_TOO_SPARSE (V10 variant): 813 → total SIGNAL_TOO_SPARSE = 3,395

A2 rejection cause becomes: **100 % SIGNAL_TOO_SPARSE** — Arena 2 is telling us that current candidates fire too few trades / positions to satisfy statistical significance floors.

## 7. No behaviour change (invariant)

This breakdown is a read-only classification of historical log data. No Arena runtime file was modified, no threshold was changed, no candidate outcome was mutated, no service was restarted. Controlled-diff confirms 0 forbidden diffs between pre- and post-SHADOW snapshots.
