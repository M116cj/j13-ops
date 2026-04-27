# 02 — CANARY Infrastructure Inventory (Phase 2)

**Phase 2 Verdict:** `CANARY_INFRA_PRESENT_DRY_RUN_ONLY`

## Live execution module — `zangetsu/live/`

| File | Size | Last modified | Purpose |
|---|---|---|---|
| `__init__.py` | 870 B | 2026-04-10 | package init |
| `main_loop.py` | 10.7 kB | 2026-04-20 | live trading orchestrator (paper-trade mode) |
| `paper_trade.py` | 9.8 kB | 2026-04-10 | simulated execution engine |
| `risk_manager.py` | 4.4 kB | 2026-04-10 | risk gates + kill_switch (`_check_kill_switch()` confirmed via dependency graph) |
| `regime_labeler.py` | 18.1 kB | 2026-04-10 | live regime detection |
| `ws_feed.py` | 8.1 kB | 2026-04-17 | Binance Futures WebSocket feed |
| `card_rotation.py` | 8.0 kB | 2026-04-20 | hot-swap deployed cards |
| `journal.py` | 4.4 kB | 2026-04-10 | audit log |

### `live/main_loop.py` operating mode

Direct quote from module docstring:

> Live trading main loop — subscribe to WS feed, process bars, manage cards.
> Orchestrates the live trading flow:
>   1. Load active (DEPLOYED) cards from champion_pipeline_fresh
>   2. Subscribe to Binance Futures WS feed
>   3. On each completed bar: detect regime → match card → compute signal → **paper trade**
>   4. Every 5 min: check for card rotations
>   5. Binary position model: trigger = close 100%

`LiveLoop` instantiates a `paper_trader` of type `PaperTrader` (from `live.paper_trade`). There is **no live order router** wired into this loop — "live" here means "live market data, simulated execution".

### Live process running?

`ps aux | grep -E 'live/main_loop|paper_trade|alpha_signal_live'` → **no matches.** The live loop is implemented but not currently running. CANARY "start" in this system would mean activating this loop in paper-trade mode.

### Why CANARY would still be starved

Step 1 of `main_loop.py` is "Load active (DEPLOYED) cards from `champion_pipeline_fresh`". Current state:

```
SELECT card_status, status, COUNT(*) FROM champion_pipeline_fresh GROUP BY 1,2;
 card_status |     status      | count
-------------+-----------------+-------
 INACTIVE    | ARENA2_REJECTED |    89
```

**Zero `DEPLOYED` cards.** Starting the live loop now would yield an empty active-card set; the loop would idle on every bar without producing any paper trade.

## Sparse-canary observer — `zangetsu/services/sparse_canary_observer.py`

Implements TEAM ORDER 0-9S-CANARY observation layer:

```python
CANARY_VERSION = "0-9S-CANARY"
EVENT_TYPE_SPARSE_CANARY_OBSERVATION = "sparse_canary_observation"
MODE_DRY_RUN_CANARY = "DRY_RUN_CANARY"
```

Triple-layer dry-run invariant guard inside `__post_init__`:

```python
def __post_init__(self):
    self.mode = MODE_DRY_RUN_CANARY     # forced
    self.applied = False                # forced
    self.canary_version = CANARY_VERSION # forced
```

Effect: every observation record is **structurally dry-run**; `applied=True` is impossible without source-code change. ✅

Composite scoring weights 0.4 / 0.4 / 0.2 per TEAM ORDER 0-9S-CANARY §4 (matching the 0-9R / 0-9S-READY proposal).

## Budget allocator — `zangetsu/services/feedback_budget_allocator.py`

| Symbol | Status |
|---|---|
| `EVENT_TYPE_DRY_RUN_BUDGET_ALLOCATION` | dry-run only |
| `proposed_profile_weights_dry_run` | named field, never auto-applied |
| `allocate_dry_run_budget()` | computes recommendation only |
| `safe_allocate_dry_run_budget()` | safety wrapper around the above |

> "Compute proposed dry-run weights for the supplied actionable [...] all gates; weights are dry-run only"

## Generation profile metrics — `zangetsu/services/generation_profile_metrics.py`

`next_budget_weight_dry_run: float = EXPLORATION_FLOOR` — weights are "a recommendation only" (line 13). `compute_dry_run_budget_weight()` is the canonical entry point.

## Feedback decision record — `zangetsu/services/feedback_decision_record.py`

> "Append-only dry-run record. The mode / applied fields are enforced [...]"
>
> "captures a dry-run budget recommendation. The record is **never applied**"

`A2_MIN_TRADES_UNCHANGED` is one of the recorded structural invariants — confirms threshold lock holds at the decision layer.

## alpha_zoo injection — `zangetsu/scripts/alpha_zoo_injection.py`

Defense-in-depth ladder verified:

```
--inspect-only ⊂ --dry-run ⊂ --no-db-write ⊂ --confirm-write
```

| Flag | Default |
|---|---|
| `--no-db-write` | True (default-on) |
| `--confirm-write` | False (default-off) |
| `--dry-run` | False (must opt-in) |
| `--inspect-only` | False (must opt-in) |

Two abort branches:
- if `--no-db-write` is set → abort
- if `--confirm-write` is NOT set → abort

Effect: DB write requires **explicit opt-out of safety + opt-in of write**. ✅

## APPLY / runtime-switchable

`grep -RIn 'runtime-switchable|apply_budget|APPLY_MODE' zangetsu`:
- `zangetsu/tools/sparse_canary_readiness_check.py:115` — references `apply_budget` field name
- `zangetsu/tests/test_generation_profile_identity_and_scoring.py:409` — same

**Two hits, both test/tool scaffolding.** No runtime APPLY flag wired up. ✅

## Components missing or out of scope

| Component | State |
|---|---|
| Live order router (real trades, not paper) | NOT PRESENT — paper_trade.py is the only execution path |
| Capital allocation (real-money sizing) | NOT PRESENT — paper trade uses simulated account |
| Real-money kill-switch | NOT PRESENT — `risk_manager.py` operates inside paper-trade simulation |
| Binance API write scope (place_order / cancel) | Code references Binance for **OHLCV / funding / OI / WS feed** (read-only); no place_order call site found in this audit |
| Production rollout pipeline | NOT STARTED |

## Calcifer outcome watch hooks (§17.3)

Calcifer supervisor (`/home/j13/j13-ops/calcifer/supervisor.py`) is running (pid 885335). Its deploy-block file (`/tmp/calcifer_deploy_block.json`) currently absent → block file = NO_BLOCK.

However: §17.3 spec says `deployable_count==0 AND last_live_at_age_h>6 → RED`. With `last_live_at_age_h = NULL`, the comparison `NULL > 6` is NULL (not TRUE) — Calcifer's predicate likely never fires. The system has been deployable_count=0 for the entire 30+ day window without ever turning Calcifer RED. **This is a known §17.3 NULL-safe predicate gap** documented in prior memory; CANARY readiness should not rely on Calcifer's RED state alone as a blocker indicator.

## Watchdog status

`/usr/sbin/watchdog` (pid 3809) and kernel `watchdogd` (pid 162) running. Application-level watchdog at `/tmp/zangetsu_watchdog.log` reports "all 8 services healthy" at every 30-min checkpoint. Cold-boot recovery path verified by mtime markers (action=skipped reason=lockfile_present_main_loop_owns).

## Rollback path

Per Phase 7 (prior order): rollback path verified live — `zangetsu_ctl.sh restart` performs SIGTERM → 3s grace → SIGKILL → governance pre-flight → restart with full env injection. Backup `*.backup_*_claude_deploy/` directories are written by `safe-patch-deploy` skill (per CLAUDE.md memory). No additional rollback infra change needed for CANARY readiness.

## Required Phase 2 classification

```
CANARY_INFRA_PRESENT_DRY_RUN_ONLY
```

Rationale: paper-trade execution layer + risk_manager + ws_feed + regime_labeler + card_rotation + journal are all implemented; sparse_canary_observer enforces dry-run by construction; budget allocator + decision record are append-only dry-run; alpha_zoo write-guard intact. The live loop is **not currently running**, but that is by-design (start-on-demand) — and even if started, would have **zero `DEPLOYED` cards to canary**. The structural blocker is upstream (Phase 1: pipeline produces no candidates).
