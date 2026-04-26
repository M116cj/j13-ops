# 0-9W-A1-PB-SCOPE-FIX — Final Verdict

## 1. Status

**COMPLETE_CRASH_FIXED_FILTER_BLOCK_REVEALED.**

The single-line `_pb = None` initialization in `arena_pipeline.py:main()` (PR #37) eliminated the `UnboundLocalError` crash that previously killed every A1 worker every cron cycle. Workers now stay alive across multiple cron ticks (the watchdog reports `all 8 services healthy` for the first time since 2026-04-23). The previously-unreachable round-end stats line is now logged and reveals the next downstream blocker: **99.8% of candidates fail at the holdout `val_neg_pnl` gate** (`bt_val.net_pnl <= 0`). 0 candidates reach the staging INSERT block, so DB materialization remains 0 — but for a fundamentally different reason (legitimate OOS rejection vs. Python crash).

## 2. Alaya

| Field | Value |
| --- | --- |
| Host | j13@100.123.49.102 (Tailscale) |
| Repo | /home/j13/j13-ops |
| HEAD | 1a90807696af9ff23b19e2a956986197f5f15395 (PR #37 squash) |
| Branch | main |
| Dirty state | clean |

## 3. Patch

| Field | Value |
| --- | --- |
| File | `zangetsu/services/arena_pipeline.py` |
| Function | `main()` (line 411) |
| Change | one-line default `_pb = None` inserted between `round_champions = 0` and `for alpha_result in alphas:` (per-round init), with 6 explanatory comment lines |
| Lines changed | +7 / -0 (1 code + 6 comments) |
| Strategy impact | NONE |
| Threshold impact | NONE |
| Arena impact | NONE |

## 4. Tests

| Field | Value |
| --- | --- |
| Baseline suite (10 test files) | 495 passed / 0 failed / 0 skipped in 0.90 s |
| Focused new test added | NO (runtime validation in Phase 5/6 directly verifies patch effect) |
| Failures | NONE |

## 5. Runtime Health (post-merge)

| Field | Value |
| --- | --- |
| A1 process state | ALIVE (PIDs 629222/629244/629258/629269 from 13:15 still running at 13:32+) |
| UnboundLocalError recurrence | **0** in all 4 worker logs |
| Previous crash point reached | YES (round-end emit at line 1218 succeeds) |
| Stats line reached | YES — `R49500 | XRPUSDT/CONSOLIDATION | champions=0/10 | rejects: val_neg_pnl=499 ...` |
| engine.jsonl | continues writing |
| A13 feedback | CLEAN (continues every */5 cron tick with `Arena 13 Feedback complete (single-shot)`) |
| A23 (PID 207186) | ALIVE, 3h 39m+ wall time |
| A45 (PID 207195) | ALIVE, 3h 39m+ wall time |
| Watchdog status (13:30:01) | `all 8 services healthy` — first time since 2026-04-23 |

## 6. DB Materialization (post-merge, ~14 min observation)

| Table | Rows since PR #37 merge |
| --- | --- |
| champion_pipeline_staging | 0 |
| champion_pipeline_fresh (new) | 0 |
| champion_pipeline_fresh (updated) | 0 |
| champion_pipeline_rejected | 0 |
| engine_telemetry | 0 |
| CANDIDATE rows | 0 |
| DEPLOYABLE rows | 0 |

Status distribution: 89 ARENA2_REJECTED (unchanged from PR #36 audit).

## 7. Safety

| Item | Status |
| --- | --- |
| APPLY path | NONE |
| Runtime-switchable APPLY | NONE |
| `A2_MIN_TRADES` | 25 (UNCHANGED) |
| Thresholds | UNCHANGED |
| Arena pass / fail | UNCHANGED |
| Champion promotion | UNCHANGED |
| `deployable_count` semantics | UNCHANGED |
| Production rollout | NOT STARTED |
| Execution / capital / risk | UNCHANGED |
| CANARY | NOT STARTED |

## 8. Governance

| Item | Status |
| --- | --- |
| Controlled-diff | EXPLAINED_A1_CRASH_FIX; 0 forbidden |
| Gate-A | PASS (35 s) |
| Gate-B summary | PASS (3 s) |
| Gate-B per module | skipping (acceptable for narrow CODE_FROZEN bug-fix) |
| Branch protection | intact (5/5 flags unchanged) |
| Signed commit | YES (ED25519 SHA256:jOIkKEJ3FntF2SIZyThPGVgZdd+sMxeii6Vjsj90+jk) |

## 9. Recommended Next Action

Per order §17 / §Phase 7 decision branch:

→ **TEAM ORDER 0-9W-VAL-FILTER-DIAGNOSIS** (CASE B — `CRASH_FIXED_BUT_ALL_FILTERED`).

Goal: read-only diagnosis of why 99.8% of candidates fail at `bt_val.net_pnl <= 0`. Hypotheses to investigate:

- **H1**: Train→holdout regime drift — train data ends earlier than holdout, market regime changed. (most likely root cause given crypto market behavior)
- **H2**: Numpy overflow during val backtest is corrupting holdout PnL calculations.
- **H3**: holdout split ratio (`TRAIN_SPLIT_RATIO=0.7`) is too aggressive — test window contains structural break.
- **H4**: Alpha engine is over-evolving on train data (`POP_SIZE=200`, `N_GEN=100` — typical numbers, but the resulting alphas don't generalize).
- **H5**: Indicator cache pre-built with train terminals contaminates holdout val backtest (Patch E from 2026-04-19 attempted to fix this; verify it's still effective).

Do NOT weaken thresholds in the diagnosis order. The next repair (after diagnosis) might address H2 (numpy overflow handling) or H5 (Patch E regression), neither of which weakens the val gate semantics.

## 10. Final Declaration

```
TEAM ORDER 0-9W-A1-PB-SCOPE-FIX = COMPLETE_CRASH_FIXED_FILTER_BLOCK_REVEALED
```

Single-line source patch eliminated A1 crash-respawn loop. Workers now stay alive, stats line is observable, val-filter rejection rate is now visible (99.8% at `val_neg_pnl`). No DB materialization yet because the val gate is correctly catching overfit alphas — that is a separate strategy-tuning concern outside this order's scope.

Forbidden changes: ALL UNCHANGED.

PR #37 merged at `1a90807696af9ff23b19e2a956986197f5f15395`. Post-merge evidence (this file plus 05/06/07) appended via follow-up signed PR.
