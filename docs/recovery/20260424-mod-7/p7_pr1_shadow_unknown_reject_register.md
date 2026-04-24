# P7-PR1 SHADOW — UNKNOWN_REJECT Register

Per TEAM ORDER 0-9G §10.

Complete enumeration of the 813 UNKNOWN_REJECT events observed during
SHADOW. Purpose: identify the exact raw-string patterns that must be
added to `RAW_TO_REASON` in a future P7-PR1 taxonomy mapping patch.

## 1. Top-line

| Metric | Value |
|---|---|
| Total rejection events | 3,651 |
| UNKNOWN_REJECT events | **813** |
| UNKNOWN_REJECT ratio | **22.27 %** |
| Ratio threshold (0-9G §5) | > 15 % = RED |
| Unique unmapped raw-string patterns | **5** |

## 2. Unmapped raw-string patterns (sorted by frequency)

| # | Raw string fragment | Frequency | Arena stage observed | Proposed canonical reason | Proposed category |
|---:|---|---:|---|---|---|
| 1 | `[V10]: pos_count=0` | 783 | A2 | SIGNAL_TOO_SPARSE | SIGNAL_DENSITY |
| 2 | `[V10]: trades=1 < 25` | 13 | A2 | SIGNAL_TOO_SPARSE | SIGNAL_DENSITY |
| 3 | `[V10]: pos_count=0 < 2` | 8 | A2 | SIGNAL_TOO_SPARSE | SIGNAL_DENSITY |
| 4 | `[V10]: trades=0 < 25` | 8 | A2 | SIGNAL_TOO_SPARSE | SIGNAL_DENSITY |
| 5 | `[V10]: trades=4 < 25` | 1 | A2 | SIGNAL_TOO_SPARSE | SIGNAL_DENSITY |
| **Total** | | **813** | | | |

All 5 patterns share a semantic theme: **candidate produced too few positions / trades on A2 holdout** — which is textbook SIGNAL_TOO_SPARSE.

## 3. Source code context (arena23_orchestrator.py)

The V10 patterns originate in `zangetsu/services/arena23_orchestrator.py` at the
Arena 2 gate. Specifically:

- Lines ~517-521 emit `A2 REJECTED id=<id> <symbol> [V10]: trades=<N> < 25` when
  `bt.total_trades < A2_MIN_TRADES` (25).
- Lines ~517-521 emit `A2 REJECTED id=<id> <symbol> [V10]: pos_count=<N>` when
  `_pos` (extracted position count) is zero or below threshold.

The taxonomy as shipped in P7-PR1 mapped the earlier arena_gates-style
`too_few_trades` and `reject_few_trades` keys to SIGNAL_TOO_SPARSE, but did
NOT cover the V10 prefix variant emitted by `arena23_orchestrator.py`. This
is a mapping-coverage gap, not a taxonomy design flaw — the canonical reason
SIGNAL_TOO_SPARSE already exists; only the raw-string aliases need addition.

## 4. Proposed mapping patch (for a SEPARATE future order — NOT applied here)

Add to `RAW_TO_REASON` in `zangetsu/services/arena_rejection_taxonomy.py`:

```python
# A2 V10-era raw-string variants (surfaced by P7-PR1 SHADOW / 0-9G)
"[V10]: pos_count=0": RejectionReason.SIGNAL_TOO_SPARSE,
"[V10]: trades": RejectionReason.SIGNAL_TOO_SPARSE,       # prefix; substring match catches "trades=1 < 25", "trades=0 < 25", "trades=4 < 25"
"[V10]: pos_count": RejectionReason.SIGNAL_TOO_SPARSE,    # prefix; catches "pos_count=0", "pos_count=0 < 2"
```

The `classify()` function's substring-match fallback already handles the
"=N < 25" and "< 2" suffix variation, so only the two prefix keys are
strictly necessary to cover all 5 observed patterns.

Expected post-patch result: UNKNOWN_REJECT ratio falls from **22.27 % → ~0 %**
(all 813 events reclassify to SIGNAL_TOO_SPARSE).

## 5. No mapping patch applied in this order

0-9G authorized scope is SHADOW observation only (§2 + §3). Adding raw-string
aliases to `RAW_TO_REASON` is a code change to a production-deployed module
(`zangetsu/services/arena_rejection_taxonomy.py`), which is outside 0-9G
authorization.

A follow-up signed PR (e.g. `phase-7/p7-pr1-taxonomy-mapping-patch-v1`) would
address this with a ~3-line diff, controlled-diff EXPLAINED / 0 forbidden,
existing tests unchanged, and a fresh test case per new alias.

## 6. Status

- UNKNOWN_REJECT register: captured.
- Mapping patch: **NOT applied** (out of 0-9G scope).
- Recommended next order: **P7-PR1 taxonomy mapping patch** — 3-line addition
  to `RAW_TO_REASON` + one new test asserting the V10 patterns classify to
  SIGNAL_TOO_SPARSE. After merge, re-run SHADOW to confirm <10 % UNKNOWN
  ratio before any CANARY consideration.
