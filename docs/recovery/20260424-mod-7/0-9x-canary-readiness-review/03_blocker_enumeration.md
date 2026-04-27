# 03 — Blocker Enumeration (Phase 3)

**Phase 3 Verdict:** `CRITICAL_BLOCKER_NO_CANARY`

## Summary table

| # | Blocker | Severity | Required before CANARY? |
|---|---|---|---|
| 1 | A1 produces 0 admissions for 6.5 days | **P0** | YES |
| 2 | Original 89 fresh alphas all `ARENA2_REJECTED` | **P0** | YES |
| 3 | `deployable_count = 0` ever | **P0** | YES |
| 4 | `last_live_at_age_h = NULL` (no live champion ever) | **P0** | YES |
| 5 | Feature space exhausted (60-bar fwd return on OHLCV+indicator) | **P0** | YES |
| 6 | live CANARY (paper-trade loop) | BLOCKED | YES — but starts trivially once #1–#5 unblock |
| 7 | alpha_zoo injection | BLOCKED | NO (alternative cold-start path) |
| 8 | runtime calibration | BLOCKED | NO (consumer of canary data) |
| 9 | production rollout (real-capital) | NOT STARTED | YES eventually — depends on order_router build |
| 10 | engine_telemetry table 0 rows ever | **P1** | NO (does not block canary) |
| 11 | §17.3 Calcifer predicate NULL-safety gap | **P1** | NO (governance hygiene) |
| 12 | Order router / real-capital execution | not-yet-built | YES (for live, not paper) |

## Detail

---

### Blocker #1 — A1 produces 0 admissions for ≥ 6.5 days

- **Status:** ACTIVE
- **Severity:** P0
- **What is blocked:** Any new alpha entering `champion_pipeline_staging` (admission_state=admitted) and onward to `champion_pipeline_fresh`.
- **Evidence:** Last admission `2026-04-21 04:34:21Z`. Phase 1 last-100-batches sample shows `pass_rate = 0/1000 = 0.0%` over a 5 min 54 s window (96.1% `COST_NEGATIVE`).
- **What unblocks:**
  - **P1 path** — change target (`triple-barrier` / `vol-normalized return` / `regime-conditional prediction`) per AKASHA next_steps
  - **P2 path** — extend feature space (order-book / funding / cross-symbol / sentiment)
  - **P3 path** — change horizon (1–5 bar micro-structure on tick data)
  - **結案** path — accept exhaustion, stop GP+LGBM development
- **Owner / next order:** `TEAM ORDER 0-9X-PIPELINE-DEPLOYABLE-FLOW-DIAGNOSIS` or one of `P1/P2/P3/結案` per j13 strategic decision.

---

### Blocker #2 — Original 89 fresh alphas all `ARENA2_REJECTED`

- **Status:** ACTIVE (historical artifact, never resolved)
- **Severity:** P0
- **What is blocked:** Any of the 89 admitted alphas progressing to A23 → A45 → DEPLOYED.
- **Evidence:** 100% of `champion_pipeline_fresh.card_status = INACTIVE`, `status = ARENA2_REJECTED` (89/89). `fresh_pool_outcome_health` shows `indicator_alpha_ratio_pct = 0.00` and `avg_depth = avg_nodes = 0.00` — formulas are degenerate raw-OHLCV-only.
- **What unblocks:** Re-evaluate why A2 (Arena 2 — backtest gate at `A2_MIN_TRADES = 25`) rejected all 89. Likely correlated with the same exhaustion as Blocker #1: even alphas that pass A1 fitness fail to produce ≥25 trades at A2 thresholds.
- **Owner / next order:** Same as #1 (root cause is the same).

---

### Blocker #3 — `deployable_count = 0` ever

- **Status:** ACTIVE since project start
- **Severity:** P0
- **What is blocked:** §17.3 Calcifer outcome watch (intended trigger), §17.5 `bump_version.py` ("deployable_count > previous" precondition), CANARY (no DEPLOYED cards to canary), version bump pipeline, AKASHA witness service.
- **Evidence:** `zangetsu_status.deployable_count = 0`; `fresh_pool_outcome_health.deployable_count = 0` for j01.
- **What unblocks:** First successful A1→A2→A23→A45 promotion to `DEPLOYED`.
- **Owner / next order:** Downstream consumer of #1 and #2.

---

### Blocker #4 — `last_live_at_age_h = NULL`

- **Status:** ACTIVE since project start
- **Severity:** P0
- **What is blocked:** §17.3 Calcifer predicate `deployable_count==0 AND last_live_at_age_h>6` cannot fire (NULL > 6 evaluates to NULL, not TRUE). Effectively, the outcome watch has never been able to turn RED.
- **Evidence:** Phase 0 query shows NULL.
- **What unblocks:** First live champion ever (entered into the pipeline → DEPLOYED → activated in card_rotation).
- **Owner / next order:** Downstream of #3. Independent fix: §17.3 spec upgrade to NULL-safe (`COALESCE(last_live_at_age_h, 999) > 6`) to handle the cold-start case — that is a separate governance order.

---

### Blocker #5 — Feature space exhausted (per AKASHA next_steps)

- **Status:** ACTIVE
- **Severity:** P0
- **What is blocked:** Any further within-formulation tuning yielding new viable alphas.
- **Evidence:** AKASHA carry-forward: "10h offline replay exhausted the space"; current 6.5-day live run produces 0 admissions; 89 historical alphas all `indicator_ratio = 0` (degenerate).
- **What unblocks:** Strategic path P1 / P2 / P3 / 結案 per AKASHA decision tree. **Requires j13 structural decision.** No code-only fix available.
- **Owner / next order:** j13 (strategic), then `/team` order to design new pipeline.

---

### Blocker #6 — live CANARY (paper-trade loop)

- **Status:** BLOCKED
- **Severity:** P0 (in the constitution)
- **What is blocked:** Starting `zangetsu/live/main_loop.py` to consume DEPLOYED cards.
- **Evidence:** No `live/main_loop.py` process running. `champion_pipeline_fresh.card_status DEPLOYED` count = 0.
- **What unblocks:** Resolve Blockers #1 + #2 + #3 → at least one card in `DEPLOYED` status → start the live loop. Loop start itself is trivial (single command); the upstream candidate supply is the real blocker.
- **Owner / next order:** `TEAM ORDER 0-9X-CANARY-START-PLAN` after upstream blockers resolved.

---

### Blocker #7 — alpha_zoo injection

- **Status:** BLOCKED
- **Severity:** P0 (in the constitution); but **NOT required before CANARY**
- **What is blocked:** Manually injecting curated alpha formulas into `champion_pipeline_staging` to seed the pool, bypassing GP search.
- **Evidence:** `zangetsu/scripts/alpha_zoo_injection.py`: `--no-db-write` default-on; `--confirm-write` default-off; default-deny abort branches.
- **What unblocks:** Explicit governance order from j13 to invoke with `--confirm-write` flag plus precondition checks.
- **Owner / next order:** Optional — can serve as cold-start path if structural blockers persist.

---

### Blocker #8 — runtime calibration

- **Status:** BLOCKED
- **Severity:** P1
- **What is blocked:** Post-deploy threshold / weight calibration based on live outcome data.
- **Evidence:** Constitution note carry-forward.
- **What unblocks:** First live trading window produces enough trades to compute calibration deltas. Consumer of #6 outcome.
- **Owner / next order:** Out of scope until #6 unblocks.

---

### Blocker #9 — production rollout (real-capital)

- **Status:** NOT STARTED
- **Severity:** P0 eventually
- **What is blocked:** Real-money trades on Binance Futures (or any exchange).
- **Evidence:** No order_router with `place_order` / `cancel_order` call sites in `zangetsu/`. `live/paper_trade.py` is the only execution layer present. `live/main_loop.py` instantiates a `PaperTrader`, not a `LiveTrader`.
- **What unblocks:**
  1. Successful paper-trade canary period (#6) producing acceptable PnL/risk profile
  2. New module `zangetsu/live/live_trader.py` (or equivalent) wired with real Binance Futures API (place_order / OCO / cancel)
  3. Capital allocator (sizing logic for real money)
  4. Real-money kill_switch + emergency_stop
  5. Audit trail / journal upgrade for real trades
- **Owner / next order:** Far future; depends on #6.

---

### Blocker #10 — `engine_telemetry` table 0 rows ever

- **Status:** ACTIVE since v0.7.1
- **Severity:** P1
- **What is blocked:** `fresh_pool_process_health` view returns 0 rows; v0.7.1 dual-evidence (process + outcome) has only outcome side functional.
- **Evidence:** Phase 0 query: `SELECT COUNT(*) FROM engine_telemetry` = 0; arena_pipeline.py:385 INSERT inside `try/except: pass` silently swallows any failure.
- **What unblocks:** Diagnose why `_telemetry_counters` never populates or never flushes. Possible causes: counter dict empty at flush time, flush threshold (`_last_telemetry_flush_ts`) never crossed, silent exception in INSERT.
- **Owner / next order:** `TEAM ORDER 0-9X-ENGINE-TELEMETRY-DIAGNOSIS` (P1, can be parallel).

---

### Blocker #11 — §17.3 NULL-safety predicate gap

- **Status:** ACTIVE
- **Severity:** P1 (governance hygiene)
- **What is blocked:** Calcifer outcome watch correctness for the cold-start case.
- **Evidence:** `last_live_at_age_h = NULL` → `NULL > 6 = NULL` → predicate never TRUE → block file never written → NO_BLOCK is meaningless.
- **What unblocks:** Spec change to `COALESCE(last_live_at_age_h, 999) > 6` or equivalent, plus Calcifer code update.
- **Owner / next order:** Constitution amendment + Calcifer follow-up order.

---

### Blocker #12 — Order router / real-capital execution layer

- **Status:** NOT BUILT
- **Severity:** P0 eventually (not for paper canary)
- **What is blocked:** Production rollout (#9).
- **Evidence:** No `place_order` / `cancel_order` / `OCO` call sites in `zangetsu/` source. `paper_trade.py` is the entire execution layer.
- **What unblocks:** Build new `zangetsu/live/order_router.py` with Binance Futures REST + WS order management. Estimate per AKASHA: "~1–2 weeks infra".
- **Owner / next order:** Long-running infra build; out of scope for canary readiness.

## Required Phase 3 classification

```
CRITICAL_BLOCKER_NO_CANARY
```

Rationale: `deployable_count = 0` ever (Blocker #3) is a **terminal blocker** — there is literally nothing to canary. Even paper-trade canary requires at least one DEPLOYED card; the system has never produced one. Blockers #1, #2, #4, #5 all converge on the same root cause: the alpha generation policy has exhausted its viable space and cannot deliver candidates that pass the existing A2 gates.

## What this implies for next-order routing

Per the order's routing table:

- **"If pipeline lacks deployables":** `TEAM ORDER 0-9X-PIPELINE-DEPLOYABLE-FLOW-DIAGNOSIS`

Recommended: this is the correct next order. The diagnosis order should specifically:
1. Quantify the A1 `COST_NEGATIVE` reject distribution per generation_profile / regime / symbol
2. Diagnose why the original 89 admitted alphas all hit `ARENA2_REJECTED`
3. Enumerate candidate options (P1 / P2 / P3 / 結案) with concrete cost / time / risk estimates
4. Surface the strategic decision back to j13

Until that order completes and produces the first `DEPLOYED` card, **no CANARY plan can be drafted** — there is no candidate to plan around.
