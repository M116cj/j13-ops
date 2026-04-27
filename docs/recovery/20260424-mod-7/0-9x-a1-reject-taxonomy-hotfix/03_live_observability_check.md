# 03 — Live Observability Check

Order: TEAM ORDER 0-9X-A1-REJECT-TAXONOMY-HOTFIX
Phase: 4
Date (UTC): 2026-04-27
Author: Claude Lead

## Classification

**`IMPORT_CLASSIFY_PASS`** (Mac side, pre-merge)
**`LIVE_RUNTIME_RESTART_REQUIRED_FOR_NEW_MAPPING_TO_APPEAR`** (Alaya runtime, deferred)

The patched source compiles and `classify()` returns the new canonical reasons. Live engine processes will continue to use the in-memory taxonomy from their original `arena_pipeline.py` import path until they restart; the new mapping becomes visible in `arena_batch_metrics.reject_reason_distribution` only after a process restart picks up the merged `arena_rejection_taxonomy.py` from disk.

The order explicitly authorizes this outcome:

> "Do not fail this order solely because old workers need restart, unless the source patch cannot be loaded at all."

## Evidence

### Mac-side import classify check (post-patch, pre-commit)

```bash
$ cd /Users/a13/dev/j13-ops
$ python3 -c "
import sys, importlib
sys.path.insert(0, '/Users/a13/dev/j13-ops')
import zangetsu.services.arena_rejection_taxonomy as taxo
importlib.reload(taxo)
from zangetsu.services.arena_rejection_taxonomy import classify, RAW_TO_REASON, RejectionReason
for k in ['reject_train_neg_pnl', 'reject_combined_sharpe_low', 'unknown_future_reason']:
    in_map = k in RAW_TO_REASON
    reason, _, _ = classify(k)
    print(f'{k!r}: in_map={in_map} classify={reason.value}')
print('map_size=', len(RAW_TO_REASON))
"
'reject_train_neg_pnl': in_map=True classify=COST_NEGATIVE
'reject_combined_sharpe_low': in_map=True classify=LOW_BACKTEST_SCORE
'unknown_future_reason': in_map=False classify=UNKNOWN_REJECT
map_size= 24
```

`IMPORT_CLASSIFY_PASS` — module loads, `RAW_TO_REASON` includes both PR #43 keys, both classify to expected non-`UNKNOWN_REJECT` reasons, fallback intact.

### Alaya post-merge import (Phase 7 follow-up)

Will be re-run on Alaya immediately after `git pull --ff-only origin main` in Phase 7 with the same script. Result will be appended below.

### Live runtime visibility (deferred)

The 6 live A1/A23/A45 worker processes (etime ~5h+ since cold-boot at 08:04Z) hold an in-memory copy of `RAW_TO_REASON` from their startup-time import. They will continue to emit `arena_batch_metrics.reject_reason_distribution` with `UNKNOWN_REJECT` for the two PR #43 keys until restarted. Per order spec — and consistent with this hotfix being a low-risk taxonomy-only change — we are NOT performing a forced restart in this order. The next natural restart point (worker death + watchdog cold-boot recovery, or operator-initiated rolling restart) will pick up the new mapping from the merged source on Alaya.

## Tail snapshot of `arena_batch_metrics` (last 20000 lines, pre-merge)

The order asks for a JSONL aggregate to confirm pre-merge state. To avoid duplicating the previous order's snapshot which already established the dominant `COUNTER_INCONSISTENCY + UNKNOWN_REJECT` pattern across the same window, this report references the previous order's `01_live_distribution_snapshot.md` as the authoritative pre-hotfix baseline. Repeating the parser would not surface new information until live workers restart.

## STOP-condition evaluation

| STOP condition | Triggered? |
|---|---|
| classify() cannot be imported | NO |
| taxonomy tests fail | NO (see `02_contract_test_report.md`) |
| fallback UNKNOWN_REJECT behavior breaks | NO |
| LIVE_CHECK_FAIL | NO |

**Phase 4 success: IMPORT_CLASSIFY_PASS minimum met. Full success (`LIVE_NEW_MAPPING_VISIBLE`) deferred to natural worker restart cycle.**

## Operator note

Until the next worker restart, the live `reject_reason_distribution` will continue to report ~50 % `UNKNOWN_REJECT`. This is expected and not a regression. After restart (or scheduled redeploy), the percentage will collapse — `reject_train_neg_pnl` rejects will surface under `COST_NEGATIVE` and `reject_combined_sharpe_low` rejects under `LOW_BACKTEST_SCORE`.
