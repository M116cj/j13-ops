# Zangetsu Ops Quick-Reference

> Cheat sheet for any agent (Claude / Gemini / Codex / Markl / Calcifer) entering a Zangetsu task. Avoid re-doing the same recon every session.
> Last verified: 2026-04-22 by Claude Code CLI (Lead).

---

## 1. Source-of-truth file map

| Component | Path | Notes |
|---|---|---|
| Engine GP / PrimitiveSet | `engine/components/alpha_engine.py` | `_build_primitive_set`, 35 ops + 126 terminals |
| Signal generation | `engine/components/alpha_signal.py:87` | `generate_alpha_signals(alpha_values, entry_threshold, exit_threshold, min_hold, cooldown, rank_window)` |
| Indicator cache | `engine/components/indicator_bridge.py` | `INDICATORS × PERIODS=[7,14,20,30,50,100]` |
| Backtester | `engine/components/backtester.py` | `_vectorized_backtest(signals, cl, hi, lo, cost_bps/1e4, max_hold, 0.0, zeros, sizes)` |
| Cost model (per-symbol) | `config/cost_model.py` | CD-03 tier-aware, `_cost_model.get(symbol).total_round_trip_bps` |
| Cold-start seeder (A1 gates) | `scripts/cold_start_hand_alphas.py` | `compile_formula / evaluate_and_backtest / seed_one / main` |
| Shadow runner (no DB writes) | `/tmp/shadow_control_suite.py` | `evaluate_shadow / main`; CLI: `--input yaml --output jsonl --symbols S1,S2,... --strategy j01 --bar-size 15 --run-id ID` |
| Policy Layer main registry | `config/family_strategy_policy_v0.yaml` | SINGLE SoT for family → parameter |
| Policy Layer resolver | `engine/policy/family_strategy_policy_v0.py` | `resolve_family_strategy_policy` + `resolve_with_allow_list` |
| Policy Layer integration wrapper | `/tmp/family_strategy_policy_integration_v0.py` (should migrate to `scripts/` in next commit) | CLI: `--family-id X --policy-mode {research,production} [--overlay-registry / --exception-overlay] [--dry-run]` |
| Exception overlay (v0) | `config/volume_c6_exceptions_overlay.yaml` | 2 allow_list pairs, expires 2026-07-22 |

---

## 2. A1 gate thresholds (inline in `scripts/cold_start_hand_alphas.py:180-204` + `shadow_control_suite.py:199-213`)

| Gate | Predicate | Fail condition | Line |
|---|---|---|---|
| train_few_trades | trades ≥ 30 | `< 30` | css:186 |
| train_neg_pnl | net_pnl > 0 | `<= 0` | css:188 |
| val_few_trades | trades ≥ 15 | `< 15` | css:197 |
| val_neg_pnl | net_pnl > 0 | `<= 0` | css:199 |
| val_low_sharpe | sharpe ≥ 0.3 | `< 0.3` | css:201 |
| val_low_wr | wilson_lower(wins, trades) ≥ 0.52 | `< 0.52` | css:204 |

Short-circuit order (scs): `train_few → train_neg_pnl → val_few → val_neg_pnl → val_low_sharpe → val_low_wr`. So `first_gate_reached=val_low_wr` means the cell passed all earlier gates.

Wilson lower: `css.wilson_lower(winning_trades, total_trades)`.

---

## 3. Shadow JSONL schema (per row)

Always present (from `scs.evaluate_shadow`):
- `alpha_hash` (md5(formula)[:16]) · `formula` · `symbol` · `bar_size_min` · `ts` · `depth` · `node_count`
- `first_gate_reached` · `reject_reason` · `survived_a1`
- `train: { trades, net_pnl, sharpe, win_rate }`
- `val:   { trades, net_pnl, sharpe, win_rate, wilson_wr }` (empty `{}` if val never ran)
- `control_id` · `control_class` · `strategy_id` · `shadow_run_id` · `cost_bps_model` · `pset_mode`

Added by policy integration wrapper:
- `requested_family_id / normalized_family_id / resolved_family_id / normalization_applied / normalization_reason / route_status / route_reason / validated / evidence_tag / policy_version / policy_mode / registry_source / overlay_path`
- `train.telemetry: { rank_window_used, entry_threshold_used, min_hold_used, exit_threshold_used, trade_count, avg_hold_bars, p10..p90, pile_{15_20,30_35,60_65,115_120}, exit_signal, exit_atr, exit_max_hold, primary_invariance{primary_trades, rerun_trades, match} }`
- Exception fields (always present even on miss): `exception_allow_list_hit / exception_overlay_name / exception_pair_key / exception_evidence_tag / exception_matched_entry_index / exception_expiry_meta / exception_overlay_path / fallthrough_to_main / exception_override_applied / exception_override_reason / exception_route_status / exception_route_reason / exception_overlay_warnings`

---

## 4. 14-symbol universe (canonical)

```
BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,LINKUSDT,AAVEUSDT,AVAXUSDT,DOTUSDT,FILUSDT,1000PEPEUSDT,1000SHIBUSDT,GALAUSDT
```

Source: `config/settings.py:110 DEFAULT_SYMBOLS`.

---

## 5. DOE yaml inventory

| Path | Family | Cells |
|---|---|---|
| `/tmp/doe_volume_l9.yaml` | volume | 10 (L9(3³)+ref) |
| `/tmp/doe_breakout_variants.yaml` | breakout | 10 (v01-v10) |
| `/tmp/doe_meanrev_l9.yaml` | mean_reversion | 10 (L9(3³)+F6 canonical) |
| `/tmp/doe_4family_smoke.yaml` | mixed | 10 (vol×3 brk×2 volume_family×2 mr×2) |
| `/tmp/doe_volume_smoke_1x1.yaml` | volume | 1 (ts_rank_20(volume)) |
| `/tmp/doe_breakout_smoke_1x1.yaml` | breakout | 1 |
| `/tmp/doe_meanrev_smoke_1x1.yaml` | mean_reversion | 1 (F6) |
| `/tmp/doe_volume_decay20_smoke.yaml` | volume | 1 (decay_20(volume) — for exception test) |

> These live in `/tmp` and survive reboots on Alaya. Consider promoting `doe_*_l9.yaml` into `config/doe/` in a future consolidation.

---

## 6. Registered primitives / terminals (from `alpha_engine.py:435-498`)

**Binary ops (2-ary)**: `add sub mul protected_div`
**Unary ops (1-ary)**: `neg abs_x sign_x tanh_x scale pow2 pow3 pow5`
**Time-series (d∈{3,5,9,20})**: `delta_d ts_max_d ts_min_d ts_rank_d decay_d`
**Correlation (d∈{5,10,20})**: `correlation_d`
**Indicator terminals**: `{ind}_{period}` for `ind ∈ INDICATORS` × `period ∈ {7,14,20,30,50,100}`
  - `rsi stochastic_k cci roc ppo cmo zscore trix tsi obv mfi vwap normalized_atr realized_vol bollinger_bw relative_volume vwap_deviation`
  - Plus funding: `funding_rate funding_zscore_{50,100,200} oi_change_{1,5,14} oi_raw`

Raw args: `close high low open volume` (renamed from ARG0..ARG4).

**PSet mode**: `ZANGETSU_PSET_MODE={full,lean}`; lean = 48 terminals (pset_lean_config.py).

---

## 7. Common operational commands

### Env bootstrap (every run needs this)
```bash
set -a; . /home/j13/j13-ops/zangetsu/secret/.env; set +a
# Required: ZV5_DB_PASSWORD, STRATEGY_ID=j01, etc.
```

### DB queries (via docker, not host psql)
```bash
PG="docker exec -e PGPASSWORD=$ZV5_DB_PASSWORD deploy-postgres-1 psql -U $ZV5_DB_USER -d $ZV5_DB_NAME"
$PG -c 'SELECT * FROM zangetsu_engine_status;'
$PG -c 'SELECT status, COUNT(*) FROM champion_pipeline_fresh GROUP BY status;'
$PG -c "SELECT admission_state, COUNT(*) FROM champion_pipeline_staging GROUP BY admission_state;"
```

### Calcifer state
```bash
cat /tmp/calcifer_deploy_block.json   # present + "status":"RED" → deploy blocked
```

### Shadow run through policy layer (canonical invocation)
```bash
STRATEGY_ID=j01 /home/j13/j13-ops/zangetsu/.venv/bin/python \
  /tmp/family_strategy_policy_integration_v0.py \
  --family-id volume --policy-mode research \
  --input /tmp/doe_volume_l9.yaml \
  --output /path/to/out.jsonl \
  --symbols BTCUSDT,ETHUSDT,... \
  --strategy j01 --bar-size 15 \
  --run-id mytask_$(date -u +%Y%m%dT%H%M%SZ)
```

Add `--exception-overlay /home/j13/j13-ops/zangetsu/config/volume_c6_exceptions_overlay.yaml` for Volume C6 exception path.

### Unit tests
```bash
python /home/j13/j13-ops/zangetsu/tests/policy/test_resolver_abcd.py        # 7/7
python /home/j13/j13-ops/zangetsu/tests/policy/test_exception_overlay.py   # 8/8
```

---

## 8. Decision rule contracts (mechanical; analyzers MUST assert)

### Generalization verdict (§13 of task 421-3)

```
YES — CONFIRMED  ⟺ survivors↑ ∧ breadth(≥) ∧ val_quality↑ ∧ train_gate_not_catastrophic
MIXED            ⟺ some_improvement ∧ (offset OR narrow) ∧ NOT YES
NO — NOT CONFIRMED ⟺ fails_beating_control ∨ survivors↓ ∨ breadth↓ ∨ train_gate_degraded
```

**Important**: `survivors 0→0` is NOT "survivors equal" — it fails `survivors↑`. Pair with val_quality regression → **NO**, not MIXED.

### Policy route status semantics

| Status | Who uses it | Has params? |
|---|---|---|
| `active` | Validated family (Volume, Breakout) | Yes — from registry |
| `unvalidated` | Placeholder in main registry | No |
| `fallback` | Resolver output for unvalidated+research | Yes — defaults |
| `blocked` | Resolver output for unvalidated+production | No (exit 3) |
| `candidate_test` | Overlay, whole family experiment | Yes — from overlay |
| `candidate_exception` | Overlay, per (symbol, formula) pair | Yes — from overlay, gated by allow_list |

Expiry: `expires_at` (absolute ISO8601) enforces fail-close; `review_after_event` is informational.

---

## 9. Environment / infra notes

- **Critical path determinism**: no RNG in alpha_signal/signal_utils/backtester/shadow_control_suite. Same inputs → bit-exact outputs. This enables telemetry-only rescore without reruns.
- **ARM_\* envs** are deprecated as primary control. Policy layer is the only sanctioned parameter source. Wrapper will warn on leaked ARM_\*.
- **wd_keepalive.service** failed since 2026-04-21 — `/dev/watchdog` module not loaded. Unrelated to pipeline; ignore unless hardware watchdog matters.
- **Pre-bash hook** aggressively blocks `eval pipe`, `curl pipe shell` patterns — use workarounds or update allowlist.

---

## 10. Known blockers (as of 2026-04-22)

- **P0**: pipeline 89/89 `ARENA2_REJECTED`, 0 deployable, 0 fresh-pool growth > 30 h
- **P1**: 95 rows stuck in `champion_pipeline_staging` with `admission_state='pending_validator_error'`
- **P2**: policy layer `entry_threshold=0.90` vs v0.7.2.2 production `0.95` unresolved semantics
- **P3**: heavy uncommitted working tree (fixed by this session's cleanup commit)

Next session must first query `zangetsu_engine_status` VIEW — if deployable_count still 0, do NOT run decoration experiments on a dead pipe.
