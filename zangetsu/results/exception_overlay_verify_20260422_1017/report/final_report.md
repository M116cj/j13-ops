# Volume C6 Exception Overlay — Acceptance Report

**Project:** Zangetsu · **Task:** Approve 2 (symbol, formula) pairs via policy-layer exception overlay · **Commit:** `f098ead5…` (same-session since 421-3) · **Date (UTC):** 2026-04-22 10:17

---

## 1. Decision Recorded

Per j13 2026-04-22 (β path after Wilson WR 0.48 trial MIXED result):

> **Do not relax the global Wilson_wr 0.52 floor. Allow-list exactly two (symbol, formula) pairs via policy-layer overlay, both 250×0.90×60×0.50 Volume candidate, no other changes.**

The 2 approved pairs:
- `BTCUSDT` × `decay_20(volume)` (val_pnl +0.32, val_sharpe +3.18, wilson 0.4913)
- `DOTUSDT` × `decay_20(volume)` (val_pnl +0.29, val_sharpe +1.36, wilson 0.4841)

---

## 2. Deliverables

| # | Artifact | Path |
|---|---|---|
| 1 | **Exception overlay yaml** | `/tmp/volume_c6_exceptions_overlay.yaml` (and snapshot at run dir) |
| 2 | **Resolver (extended)** | `/home/j13/j13-ops/zangetsu/engine/policy/family_strategy_policy_v0.py` |
| 3 | **Integration wrapper (extended)** | `/tmp/family_strategy_policy_integration_v0.py` |
| 4 | **Unit tests** | `/tmp/policy_test_exception_overlay.py` (8/8 PASS) + regression `/tmp/policy_test_abcd.py` (7/7 PASS) |
| 5 | **Attribution analyzer** | `/tmp/exception_attribution.py` |
| 6 | **Run directory** | `/home/j13/j13-ops/zangetsu/results/exception_overlay_verify_20260422_1017/` |

---

## 3. Overlay Registry Design

### Key features (per j13 修正 §1–4)

| Constraint | Implementation |
|---|---|
| **§1 命名分開** | `route_status: "candidate_exception"` (distinct from `candidate_test`) + `overlay_kind: "candidate_exception"` |
| **§2 Dual-track expiry** | `review_after_event`/`review_by_date_hint` + `expiry_after_event`/`expires_at`. Resolver fail-closes only on absolute `expires_at` past-now; event-only fields are warnings |
| **§3 Primary-key = formula string, hash secondary** | `_match_allow_list()` matches on `(symbol, formula_string)`; `alpha_hash` is a defensive secondary verifier (warns on mismatch, rejects hash-only matches) |
| **§A overlay 不能修改 main registry** | `load_with_overlay()` raises on family_id collision with main families |
| **§B candidate_exception 不能 --family-id 直接跑** | `resolve_with_allow_list()` raises `PolicyRegistryError` if caller passes the exception family_id; wrapper also guards in its own flow |
| **§C full verify 表格** | `/tmp/exception_attribution.py` produces §C-compliant attribution table from any overlay-aware JSONL |
| **§D exception 命中寫 JSONL** | Each row carries `exception_allow_list_hit / exception_overlay_name / exception_pair_key / exception_evidence_tag / fallthrough_to_main / exception_override_applied / exception_override_reason` etc. Always present on both hit and miss rows (stable schema) |

### Schema snapshot

```yaml
policy_version: "v0"
overlay_kind: "candidate_exception"
families:
  volume_c6_approved_exceptions:
    validated: false
    route_status: "candidate_exception"
    evidence_tag: "wilson_wr_0.48_trial_verified_2026-04-22"
    rank_window: 250
    entry_threshold: 0.90
    min_hold: 60
    exit_threshold: 0.50
    approval_reason: "..."
    boundary_condition: "..."
    review_after_event: "next_volume_L9_cycle"
    review_by_date_hint: "2026-05-22T00:00:00Z"
    expiry_after_event: "1_experiment_cycle_or_quality_regression"
    expires_at: "2026-07-22T00:00:00Z"
    created_at: "2026-04-22T09:41:00Z"
    review_required: true
    allow_list:
      - { symbol: BTCUSDT, formula: "decay_20(volume)", alpha_hash: "0cea1d5ad3806aba", ... }
      - { symbol: DOTUSDT, formula: "decay_20(volume)", alpha_hash: "0cea1d5ad3806aba", ... }
```

---

## 4. Regression + Unit Tests

### 4.1 Resolver regression (`policy_test_abcd.py`) — **7/7 PASS**

A volume/research · B breakout/research · C mean_reversion/research · D mean_reversion/production · E alias volume_family · F alias mr · G unknown zzzz → all unchanged, all PASS.

### 4.2 Exception overlay unit tests (`policy_test_exception_overlay.py`) — **8/8 PASS**

| # | Case | Expectation | Result |
|---|---|---|:---:|
| U1 | HIT on BTCUSDT decay_20(volume) | candidate_exception, params 250×0.90×60×0.50, no warning | ✅ |
| U2 | MISS wrong symbol (ETHUSDT) | fallthrough to main active, no warning | ✅ |
| U3 | MISS wrong formula (BTCUSDT ts_rank_20(volume)) | fallthrough, no warning | ✅ |
| U4 | HIT DOTUSDT + correct alpha_hash | hit, no mismatch warning | ✅ |
| U5 | HIT BTCUSDT + WRONG alpha_hash | hit (formula wins), hash mismatch warning emitted | ✅ |
| U6 | Hash-only (wrong formula, correct hash+symbol) | NOT a pass; fallthrough + hash-only warning | ✅ |
| U7 | Direct invocation `--family-id volume_c6_approved_exceptions` | `PolicyRegistryError` raised | ✅ |
| U8 | Expired overlay (simulated) | exception NOT applied, fallthrough + expired warning | ✅ |

---

## 5. Dry-Run + Smoke

### Dry-run banner (excerpt)

```
===== family-strategy-policy v0 =====
requested_family_id   = 'volume'
resolved_family_id    = 'volume'
route_status          = 'active'
registry_source       = 'main'
...
[policy-integration-v0] === EXCEPTION OVERLAY LOADED ===
[policy-integration-v0] exception_overlay_path = /tmp/volume_c6_exceptions_overlay.yaml
[policy-integration-v0] overlay family = 'volume_c6_approved_exceptions' (evidence_tag='wilson_wr_0.48_trial_verified_2026-04-22', allow_list size=2)
[policy-integration-v0]   allow[0] symbol='BTCUSDT' formula='decay_20(volume)' alpha_hash='0cea1d5ad3806aba'
[policy-integration-v0]   allow[1] symbol='DOTUSDT' formula='decay_20(volume)' alpha_hash='0cea1d5ad3806aba'
[policy-integration-v0]   expires_at = '2026-07-22T00:00:00Z' (absolute; resolver will fail-close past this)
[policy-integration-v0] total allow_list entries = 2
```

### Smoke (1 formula × 3 symbols: BTC, DOT, ETH)

| Symbol | survived_a1 | first_gate | exception_hit | override_applied | fallthrough |
|---|:---:|---|:---:|:---:|:---:|
| BTCUSDT | ✅ True | `A1_PASSED` | True | True | False |
| DOTUSDT | ✅ True | `A1_PASSED` | True | True | False |
| ETHUSDT | ❌ False | `a1_val_low_wr` | False | False | True |

All three behave exactly as spec'd.

---

## 6. §C Full 140-Cell Verify Table (j13 Hard Rule C)

### 6.1 Population & attribution

| Slice | Count | Expected |
|---|---:|---|
| total cells | 140 | — |
| allow_list pairs declared | 2 | — |
| cells matching allow_list (actually ran) | **2** | 2 ✓ |
| ...with `exception_hit=True` | **2** | 2 ✓ |
| ...with `exception_hit=False` | **0** | 0 ✓ (investigate if > 0) |
| cells NOT matching allow_list | **138** | 138 ✓ |
| ...with `exception_hit=True` | **0** | **0 — MUST = 0 ✓** |
| ...with `fallthrough_to_main=True` | **138** | 138 ✓ |

**Total exception hits = 2.  Unexpected = 0.  VERIFY VERDICT: PASS.**

### 6.2 Per allow_list pair

| # | Symbol | Formula | In run | exc_hit | override | first_gate (after override) | survived_a1 |
|---:|---|---|:---:|:---:|:---:|---|:---:|
| 1 | BTCUSDT | `decay_20(volume)` | ✅ | True | True | `A1_PASSED` | True |
| 2 | DOTUSDT | `decay_20(volume)` | ✅ | True | True | `A1_PASSED` | True |

### 6.3 Gate-outcome summary (before vs after exception)

| Gate bucket | Without overlay (prior 421-3 / wilson_wr trial source JSONL) | With overlay (this run) | Δ |
|---|---:|---:|---:|
| survived_a1 (A1_PASSED) | 2 | **4** | **+2** |
| a1_train_neg_pnl | 101 | 101 | 0 |
| a1_val_neg_pnl | 19 | 19 | 0 |
| a1_val_low_wr | 17 | **15** | **−2** |
| a1_val_low_sharpe | 1 | 1 | 0 |
| **total** | 140 | 140 | 0 |

Exactly the 2 allow_list cells migrated from `a1_val_low_wr` into `A1_PASSED`. **No other cell moved.** Gate-outcome delta fully explained by the 2 declared exceptions — no drift, no leakage, no unintended collateral.

### 6.4 Non-allow_list fallthrough spot-check

All 138 cells outside the allow_list:
- `exception_allow_list_hit = False` (100 %)
- `exception_overlay_name = None`
- `fallthrough_to_main = True` (100 %)
- `exception_override_applied = False`
- JSONL schema stable (all exception_* fields present with correct null/False values)

---

## 7. Hard-Boundary Compliance

| Constraint | Status |
|---|---|
| **§A** overlay may only ADD families, cannot redefine main | ✅ `load_with_overlay()` collision check enforces this; tested via registry schema |
| **§B** candidate_exception cannot be used as `--family-id` | ✅ U7 unit test confirms PolicyRegistryError raised |
| **§C** full verify attribution table produced | ✅ §6 above + `report/attribution.json` |
| **§D** JSONL carries full exception metadata on every row | ✅ `exception_allow_list_hit`, `exception_overlay_name`, `exception_pair_key`, `exception_evidence_tag`, `exception_override_applied`, `fallthrough_to_main`, `exception_matched_entry_index`, `exception_expiry_meta` all present |
| 命名 `candidate_exception` separate from `candidate_test` | ✅ |
| Dual-track expiry (event + date) | ✅ U8 unit test confirms absolute expiry blocks, event-only is informational |
| formula-string primary key, alpha_hash secondary | ✅ U4/U5/U6 tests confirm |
| No global Wilson floor change | ✅ main registry untouched; only 2 specific (symbol, formula) cells bypass gate |
| No production source modification | ✅ zero edits to `scripts/cold_start_hand_alphas.py`, `shadow_control_suite.py`, backtester, cost model, DB schema |
| Same commit / session / data window | ✅ commit `f098ead5…`, same-session continuity |

---

## 8. Minimal Next Action

**Hold the current state for one experiment cycle.** Monitor:
- `exception_override_applied=True` rate on recurring runs (should stay at exactly 2 with these 2 pairs; any drift or spread = investigate)
- `expires_at` at `2026-07-22T00:00:00Z` — resolver will automatically fail-close past this date, forcing a human re-review
- Any quality-regression signal (val_sharpe, wilson_wr drift on either BTC or DOT decay_20(volume))

Next decisive task when a regression appears or cycle boundary hits:
- Either **remove** the 2 exceptions (if quality regressed) — just delete the overlay yaml
- Or **promote** these 2 pairs into the main registry as a formal refined `volume_decay20_subfamily` route (not via this overlay — requires a dedicated decision task and the same evidence chain we built here)

**Do not** use this overlay mechanism to accumulate more pairs without revisiting the β decision. Each new pair requires its own trial + approval flow.

---

## 9. Artifacts (on Alaya)

- `/home/j13/j13-ops/zangetsu/results/exception_overlay_verify_20260422_1017/commit.txt`
- `.../full/volume_with_exceptions.jsonl` — 140 rows, 2 exception overrides applied
- `.../smoke/smoke_3sym.jsonl` — 3 rows (BTC+DOT hit, ETH fallthrough)
- `.../dryrun/dryrun.log` — banner
- `.../report/attribution.json` — §C attribution table (machine-readable)
- `.../report/final_report.md` — this report
- `.../logs/{full,smoke}.log` — execution logs
- `/home/j13/j13-ops/zangetsu/config/family_strategy_policy_v0.yaml` — main registry (unchanged)
- `/home/j13/j13-ops/zangetsu/engine/policy/family_strategy_policy_v0.py` — resolver (extended)
- `/tmp/volume_c6_exceptions_overlay.yaml` — exception overlay
- `/tmp/family_strategy_policy_integration_v0.py` — integration wrapper (extended)
- `/tmp/policy_test_exception_overlay.py` — U1–U8 unit tests
- `/tmp/exception_attribution.py` — verify analyzer

---

## 10. Status

**READY.** Overlay is deployed, tested, and verified in full. 2 allow_list pairs are promoted to survivors via exception; 0 unintended side-effects; all hard boundaries satisfied.
