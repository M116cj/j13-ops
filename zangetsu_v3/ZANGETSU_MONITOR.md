ZANGETSU V3.2 — DEFINITIVE SYSTEM DIRECTIVE

Single source of truth. Supersedes ALL previous documents (including V3.1).
17 Q&A decisions integrated. Full concurrency at every layer.
ALL data in PostgreSQL — nothing on filesystem except deployment artifacts.

================================================================================
§0 CHANGELOG (V3.1 → V3.2)
================================================================================

- Added §0 Changelog for version tracking
- Added §1 Q&A Decision Index (Q01-Q17 was scattered, now centralized)
- Separated §2 CURRENT STATE from spec (operational snapshot, not architecture)
- Merged redundant concurrency descriptions (was repeated in 3 places)
- Consolidated Arena 3 generation loop (was split across §CONCURRENCY and §ARENA3)
- Added missing DB index recommendations
- Clarified card.json schema field list (was prose, now structured)
- Fixed: task dependency graph had circular reference (C11 depends on C0 but was in AFTER C0+C1)
- Fixed: WARM RESTART section referenced "old pool_version" without defining versioning scheme

================================================================================
§1 Q&A DECISION INDEX
================================================================================

Decisions made during V3 design. Referenced as (Q##) throughout this document.
If a future change contradicts any Q##, it must be explicitly noted.

Q01  Warmup: prefetch warmup_bars before each segment, compute features, truncate
Q02  PySR input: 34 columns (29 derived + 5 OHLCV) + rolling operators
Q03  Arena 1 fast: 34 columns (batch 1) + 5 OHLCV (batch 2) + rolling operators
Q04  Arena 2 compression: per-regime independent, pairwise corr on that regime only
Q05  Arena 3: no cross-regime warm start, each regime independent from scratch
Q06  Backtest cost: real per-symbol cost (BTC=4bps, DOGE=8bps etc.)
Q07  Segment order: shuffle segments in Rung 1 (not sequential)
Q08  Archive measures: [median_tpd, median_max_dd] for GridArchive dimensions
Q09  Rung reuse: Rung 1 reuses Rung 0 result (no re-backtest same segment)
Q10  SoS gate: 3-layer (floor 0.5 → adaptive P25 → adjusted_fitness = trimmed_min × min(SoS,2.0))
Q11  Holdout rules: TRAIN normalization params (no refit), Rung 1 cost level, same funding constants, each segment independent, median fitness (not trimmed_min)
Q12  Feature scaling: all features /close (scale invariant), per-regime normalization (one set medians+stds)
Q13  Scale filter: discard expressions with raw price not in ratio structure
Q14  Multi-timescale: all targets' factors into same regime pool, CMA-MAE decides weights
Q15  Card replacement: rolling holdout, old cards keep running, per-regime replacement
Q16  Card lifecycle: DEPLOYED→ACTIVE→DEGRADED→EXPIRED→REPLACED, DB-driven monitoring
Q17  Bot role: zangetsu_bot.py is NOTIFY ONLY, zero actions

================================================================================
§2 CURRENT STATE ON ALAYA (snapshot, update as needed)
================================================================================

Date: 2026-04-06
Code: ~/j13-ops/zangetsu_v3/
DB: deploy-postgres-1, 127.0.0.1:5432, database=zangetsu
  ohlcv_1m: 17,617,230 rows
Env: .venv → ribs 0.9.0, pysr 1.5.10, polars 1.39.3, numba 0.65.0,
     hmmlearn 0.3.3, scipy 1.17.1, pytest 9.0.2
Running: Arena 1 PySR in tmux (17/55 runs done, Julia crashed at run 18)
Tests: 88/117 pass, 29 fail (API mismatch)
V2: stopped, pushed to GitHub, cleanup pending
Katen collector: running

================================================================================
§3 STORAGE RULE (ABSOLUTE)
================================================================================

ALL data → PostgreSQL. No JSON/parquet/checkpoint files on disk.
Process killed at any point → restart → SELECT from DB → resume exactly.

Filesystem outputs (deployment artifacts ONLY):
  strategies/{REGIME}_expert/card.json
  strategies/{REGIME}_expert/regime_model.pkl
  strategies/{REGIME}_expert/checksum.sha256

Deleted filesystem patterns (now in DB):
  arena1_results/, arena1_fast_results/ → factor_candidates table
  factor_pool.json → factor_pool table
  orchestrator_state.json → orchestrator_state table
  orchestrator_events.json → orchestrator_events table
  runtime/status.json → runtime_status table (UPSERT every bar)
  live_journal.parquet → trade_journal table
  arena3 archive checkpoints → search_candidates table

================================================================================
§4 THREE PROCESSES
================================================================================

orchestrator.py  search lifecycle + card management + alerts via zangetsu_bot
main_loop.py     trade execution + writes trade_journal + runtime_status to DB
zangetsu_bot.py  reads DB → Telegram. NOTIFY ONLY. Zero actions. (Q17)

All IPC through PostgreSQL. No filesystem. No shared memory.

================================================================================
§5 REGIME SYSTEM
================================================================================

Rule-based 4h labeler (completed, verified): 13 states.

11 search regimes:
  BULL_TREND, BEAR_TREND, BULL_PULLBACK, BEAR_RALLY,
  TOPPING, BOTTOMING, CONSOLIDATION, SQUEEZE,
  CHOPPY_VOLATILE, DISTRIBUTION, ACCUMULATION

2 overlay-only (not searched, applied at runtime):
  PARABOLIC (weight 0.3), LIQUIDITY_CRISIS (weight 0.0)

Per-regime fully independent pipeline (Q04, Q05):
  NO shared factor pool. Each regime owns Arena 1→2→3→Gates→Card.
  11 pipelines run fully parallel with zero cross-regime dependencies.

================================================================================
§6 DATA PREPARATION
================================================================================

1. Read ohlcv_1m from DB
2. Resample to 4h, rule-based label 13 states, broadcast to 1m
3. Per regime: extract continuous segments (≥1440 bars) across 6 symbols
4. Sort by time → front 70% TRAIN, embargo gap, remainder HOLDOUT
5. Feature boundary (Q01): prefetch warmup_bars before segment,
   compute 29 features, truncate warmup portion
6. Segment metadata: regime, symbol, start_idx, end_idx, cost_bps, funding_rate

29 features all /close (scale invariant, Q12):
  Returns(9), Ranges(6), Volume ratios(4), Candle(4),
  Range position(3), Volatility(3)

PySR sampling: continuous chunk sampling
  (10 chunks × 1,500 bars, truncate last 30 per chunk). NOT random rows.

================================================================================
§7 ARENA 1: FACTOR DISCOVERY
================================================================================

Two lanes run in parallel per regime (Layer 2 concurrency).

--- LANE A: Random Expression Generator (arena1_fast.py) ---

Per regime (11 run in parallel via ProcessPoolExecutor):
  Batch 1: 5,000 ASTs from 34 columns (29 derived + 5 OHLCV) + rolling ops (Q03)
  Batch 2: 5,000 ASTs from 5 OHLCV + rolling ops (Q03)

  Operators: add, sub, mul, div(protected), abs, neg, square, sqrt(protected),
    log1p, ts_delta, ts_std, ts_mean, ts_max, ts_min, ts_rank, ts_corr
  Lookback pool: [1,2,3,5,7,10]. Depth: 2-5.

  Dedup: AST hash. Validity: <10% NaN/Inf on 1000 bars.
  Scale filter (Q13): discard raw price not in ratio structure. Volume must be ratio.
  Quick screen: 1 longest segment/regime, Pearson corr with next_5_bar_return, top 500.
  Full validation: all TRAIN segments, corr with next_1/5/10/30, keep abs(corr)>0.01 on ≥3 targets.
  Output: INSERT INTO factor_candidates (batch, source='random')

  Total: ~15 min for all 11 regimes simultaneously.

--- LANE B: PySR ---

55 runs (11 regimes × 5 targets), each in subprocess (prevents Julia memory leak).
ProcessPoolExecutor(max_workers=5): 5 concurrent, each procs=4 Julia workers.

  Input: 34 columns + rolling operators (Q02)
  Config: 400 iterations, maxsize=25, maxdepth=7, 50 populations × 60
  Sampling: continuous chunks ≤15,000 rows. Top 20 per run.
  Scale filter (Q13) on output.
  Output: INSERT INTO factor_candidates (per run, source='pysr')
  Resume: SELECT count WHERE source='pysr' AND regime=X AND horizon=Y → skip if >0

  55 runs / 5 concurrent = 11 batches × ~22 min = ~4-5 hours total.

Multi-timescale mixing (Q14): all targets' factors → same regime pool.

================================================================================
§8 ARENA 2: FACTOR COMPRESSION
================================================================================

Per regime (11 in parallel, Q04):

  Input: SELECT * FROM factor_candidates WHERE regime='{regime}'
  Compute factor values on TRAIN segments only (per-regime)
  Pairwise Pearson correlation on that regime's segments only

  Greedy dedup:
    Sort by score desc → add one-by-one → skip if corr>0.7 with any selected
    Weak filter: abs(corr with any target) < 0.01 → drop
    >20 factors: keep top 20
    <10 factors: relax threshold to 0.8

  Output: INSERT INTO factor_pool (regime, pool_version=timestamp)
  Normalization NOT done here (done in Arena 3 setup)

  Runs twice: first on Lane A results, then on combined A+B.

================================================================================
§9 ARENA 3: CMA-MAE SEARCH
================================================================================

11 regimes start simultaneously. No cross-regime warm start (Q05).

--- SETUP (per regime) ---

1. SELECT FROM factor_pool WHERE regime=X AND pool_version=latest
2. Compute factor values on all TRAIN segments (warmup prefetch Q01)
3. FactorNormalizer.fit_transform: per-regime medians+stds (Q12). Store for card.
4. SignalScaleEstimator: 1000 random weights → median signal std
   → bounds [0.3σ,1.5σ] entry, [0.05σ,0.8σ] exit
5. GridArchive(dims=[20,20], measures=[median_tpd, median_max_dd]) (Q08)

--- GENERATION LOOP (fully concurrent) ---

Each generation executes these steps:

Step 1: ask → N candidates (default 36)

Step 2: Hard clamp parameters
  entry [0.3σ,1.5σ], exit [0.05σ,0.8σ] then min(exit, entry×0.8)
  stop [0.5,5], pos [0.01,0.25], hold [3,480] int

Step 3: Batch signal computation (Layer 4 vectorization)
  signal_batch = factor_matrix @ weights_batch.T   # ONE matrix-matrix multiply
  # weights_batch: (N_candidates, N_factors)
  # signal_batch:  (N_bars, N_candidates)

Step 4: Vectorized Rung -1 prescreen
  numerator = weights_batch @ factor_mu                                    # (N,)
  denominator = sqrt(sum((weights_batch @ factor_cov) * weights_batch, 1)) # (N,)
  predicted_sharpe = numerator / (denominator + 1e-8)
  survivors = predicted_sharpe > 0   # boolean mask

Step 5: Parallel Rung 0 backtest (Layer 3 — ThreadPoolExecutor(20))
  Each survivor backtests on 1 random segment, real per-symbol cost (Q06)
  36 candidates × 15ms → ~30ms parallel

Step 6: Natural gap cutoff
  Sort rung0 fitness, find largest gap, promote top group. Min 3.

Step 7: Parallel Rung 1 backtest (Layer 3 — THE BIGGEST WIN)
  All promoted candidates simultaneously, each internally sequential.
  Early kill: every 5 segments, if fail_count ≥ 3 → return -999
  Reuse Rung 0 result (Q09). Shuffle segments (Q07).
  5 promoted × 150 segments × 15ms = 11.25s sequential
  → parallel with early kill ≈ 0.3-0.5s

Step 8: Fitness computation
  SoS 3-layer (Q10): floor 0.5 → adaptive P25 → adjusted = trimmed_min × min(SoS,2.0)
  Measures: [median_tpd, median_max_dd] (Q08)

Step 9: tell + persist
  scheduler.tell(all_objectives, all_measures)
  Batch INSERT INTO search_candidates (every candidate, every generation)
  INSERT INTO search_progress (generation summary)
  AdaptiveBounds update every 50 gen

--- PERFORMANCE ---

Per generation: ~12s (old) → ~0.5-1.0s (new)
1000 generations: 3.3h → ~8-17 min per regime
11 regimes parallel: wall time ≈ 8-17 min total

--- CONVERGENCE ---

QD delta < 0.1% over 100 gen AND gen ≥ 200 → stop regime.

--- WARM RESTART (after PySR Lane B merges) ---

SELECT FROM search_candidates WHERE regime=X AND is_elite=true AND pool_version=old
Re-evaluate on new factor pool (dimension changed: truncate/pad weights)
Seed new archive with surviving elites
Run 200-300 additional gen (not 1000)

================================================================================
§10 CONCURRENCY MODEL (4 Layers)
================================================================================

Layer 1: 11 regimes × full pipeline — ALL PARALLEL, no dependencies (Q05)
Layer 2: per regime, Arena 1 two lanes parallel (fast + PySR)
Layer 3: CMA-MAE generation-internal parallelism (ThreadPoolExecutor(20))
Layer 4: vectorized operations (numpy/numba BLAS-level SIMD)

Thread pool sharing: 20 threads shared across all 11 regimes in Arena 3.
Process pool: ProcessPoolExecutor(11) for Arena 1 fast, ProcessPoolExecutor(5) for PySR.

================================================================================
§11 THREE GATES
================================================================================

Gate 1: SoS 3-layer
  Enforced during search. Champions in result_archive passed.

Gate 2: DSR > 0.95
  n_trials = num_elites (not ask total)

Gate 3: HOLDOUT one-shot (Q11)
  Normalization: TRAIN params, no refit
  Cost: Rung 1 level (BTC=4, DOGE=8)
  Funding: same constants as TRAIN
  Each HOLDOUT segment independent
  HOLDOUT fitness = median (not trimmed_min)
  Pass: median_fitness > 0, median_wr > 0.52, total_trades ≥ 30
  Fail = permanent FAILED_HOLDOUT

All gate results: INSERT INTO validation_gates.

================================================================================
§12 STRATEGY CARD
================================================================================

--- Filesystem (deployment artifact only) ---

strategies/{REGIME}_expert/card.json
strategies/{REGIME}_expert/regime_model.pkl
strategies/{REGIME}_expert/checksum.sha256

--- card.json schema (v3.2) ---

version: "3.2"
regime: string
regime_includes: [list of fine states]
applicable_symbols: [all 6]
warmup_bars: int
normalization:
  medians: {factor_name: float}    # per-regime (Q12)
  stds: {factor_name: float}
factors:
  - name: string
    ast: string
    weight: float
params:
  entry_threshold: float
  exit_threshold: float
  stop_loss: float
  position_size: float
  max_hold_bars: int
cost_model:
  per_symbol: {symbol: bps}
backtest_stats:
  trimmed_min_fitness: float
  median_sharpe: float
  median_win_rate: float
  median_tpd: float
  median_max_dd: float
  total_segments: int
validation_stats:
  gate1_sos: float
  gate2_dsr: float
  gate3_holdout_fitness: float
  gate3_holdout_wr: float
  gate3_holdout_trades: int
regime_labeler:
  method: "rule_based_4h"
  version: string
deployment_hints:
  signal_std: float
  entry_bounds: [float, float]
  exit_bounds: [float, float]

Card data also in DB: strategy_champions table. Export = write to filesystem FROM DB.

--- LIFECYCLE (Q15, Q16) ---

DEPLOYED → ACTIVE → DEGRADED → EXPIRED → REPLACED

strategy_monitor runs daily 00:00:
  Reads trade_journal table (not filesystem)
  Computes daily_pnl, trade_count, win_rate, avg_slippage
  INSERT INTO card_daily_stats
  7-day: SUM(daily_pnl) < -max_dd → DEGRADED
  30-day: t-test, mean < 0, p < 0.05 → DEGRADED
  14 consecutive days DEGRADED → EXPIRED

Rolling holdout: old cards keep running, per-regime replacement (Q15).

================================================================================
§13 MAIN LOOP
================================================================================

on_new_bar:
  stale check
  → predict_coarse (11 regimes)
  → predict_fine (13 states, overlay)
  → select card
  → signal
  → position sizing: base × perf_mult × switch_conf × overlay_damper
  → risk check
  → execute
  → journal

Risk limits (hard):
  NET ≤ 0.25, GROSS ≤ 0.50
  PER_REGIME ≤ 0.15, PER_SYMBOL ≤ 0.15
  CONCURRENT ≤ 8

DB writes per bar:
  INSERT INTO trade_journal (card_id, symbol, timestamp, direction, signal_value,
    expected_price, actual_fill_price, slippage_bps, position_size,
    regime_at_entry, regime_confidence, switch_confidence, pnl_pct, hold_bars)
  UPSERT INTO runtime_status (singleton row: regime, confidence,
    bars_since_switch, switch_confidence, active_card_id, fine_regime,
    overlay_damper, stale_status, last_bar_time, today_pnl, cumulative_pnl,
    today_trades, open_positions, net_exposure, gross_exposure, updated_at)

Card reload: check DB for newer card version, not filesystem trigger.

================================================================================
§14 ONLINE PREDICTOR
================================================================================

LightGBM on rule-based labels. Past-only features from 4h bars. Temporal split.
predict_coarse() → 11 regimes
predict_fine() → 13 states
Debounce + switch_confidence (0.3→1.0 over 30 bars)
Accuracy target: >70%. Latency target: <10ms.

================================================================================
§15 ORCHESTRATOR
================================================================================

State machine:
  IDLE → ARENA1_FAST → ARENA2 → ARENA3 → GATING → DEPLOYING → MONITORING → trigger → loop

State: UPSERT INTO orchestrator_state (singleton, state + details_json + updated_at)
Events: INSERT INTO orchestrator_events (event_type, regime, details_json, timestamp)

ARENA1_FAST: arena1_fast.py (11 regimes parallel). Also launch PySR background.
ARENA2: compression per regime parallel. Read/write DB.
ARENA3: CMA-MAE 11 regimes parallel, full concurrency.
GATING: 3 gates per champion. Write DB.
DEPLOYING: export card.json FROM DB. Compare with existing → replace if better.
MONITORING: check every 60 min.
  Triggers: factor_age>30d, degraded>50%, expired_no_backup,
    rolling_holdout(90d), pysr_complete.

Crash recovery (all from DB):
  ARENA1: check factor_candidates → resume missing runs
  ARENA3: check search_candidates → reconstruct archive from elites → resume last gen
  GATING/DEPLOYING: idempotent, safe to rerun

================================================================================
§16 ZANGETSU BOT (Q17)
================================================================================

zangetsu_bot.py: SELECT from DB → Telegram. NOTIFY ONLY.
Does NOT restart, replace, or modify anything.
Heartbeat every 1h. Daily summary 00:00 UTC. Alerts on anomalies.

================================================================================
§17 DATABASE TABLES
================================================================================

--- Price Data ---
ohlcv_1m (symbol, timestamp, open, high, low, close, volume)
  INDEX: (symbol, timestamp) PRIMARY KEY
  ~17.5M rows, katen writes

--- Arena 1 ---
factor_candidates (id SERIAL, source TEXT, regime TEXT, horizon TEXT,
  ast_json JSONB, raw_expression TEXT, loss FLOAT, score FLOAT,
  corr_h1 FLOAT, corr_h5 FLOAT, corr_h10 FLOAT, corr_h30 FLOAT,
  lookback INT, run_id TEXT, created_at TIMESTAMPTZ)
  INDEX: (regime, source), (regime, horizon, source)

arena1_runs (id SERIAL, regime TEXT, horizon TEXT,
  status TEXT, candidates_found INT,
  started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ)
  INDEX: (regime, horizon, status)

--- Arena 2 ---
factor_pool (id SERIAL, regime TEXT, name TEXT, ast_json JSONB,
  raw_expression TEXT, lookback INT, score FLOAT,
  pool_version TIMESTAMPTZ, pairwise_max_corr FLOAT,
  avg_corr_with_target FLOAT, created_at TIMESTAMPTZ)
  INDEX: (regime, pool_version)

--- Arena 3 ---
search_candidates (id SERIAL, regime TEXT, generation INT,
  pool_version TIMESTAMPTZ, weights_json JSONB, params_json JSONB,
  per_segment_results_json JSONB, trimmed_min_fitness FLOAT,
  sos FLOAT, adjusted_fitness FLOAT, median_sharpe FLOAT,
  median_win_rate FLOAT, median_tpd FLOAT, median_max_dd FLOAT,
  median_hold_bars FLOAT, rung INT, survived_rung0 BOOL,
  is_elite BOOL, created_at TIMESTAMPTZ)
  INDEX: (regime, generation), (regime, is_elite, pool_version)

search_progress (id SERIAL, regime TEXT, generation INT,
  pool_version TIMESTAMPTZ, qd_score FLOAT, coverage FLOAT,
  num_elites INT, best_fitness FLOAT, rung0_survival_rate FLOAT,
  created_at TIMESTAMPTZ)
  INDEX: (regime, pool_version)

--- Gates ---
validation_gates (id SERIAL, champion_id INT, regime TEXT,
  gate1_pass BOOL, gate1_sos FLOAT,
  gate2_pass BOOL, gate2_dsr FLOAT,
  gate3_pass BOOL, gate3_holdout_fitness FLOAT,
  gate3_holdout_wr FLOAT, gate3_holdout_trades INT,
  created_at TIMESTAMPTZ)
  INDEX: (regime, champion_id)

--- Deployment ---
strategy_champions (id SERIAL, regime TEXT, pool_version TIMESTAMPTZ,
  generation INT, adjusted_fitness FLOAT, sharpe FLOAT,
  win_rate FLOAT, tpd FLOAT, max_dd FLOAT,
  weights_json JSONB, params_json JSONB,
  normalization_json JSONB, factors_json JSONB,
  gate1_pass BOOL, gate2_pass BOOL, gate3_pass BOOL,
  status TEXT, deployed_at TIMESTAMPTZ, expired_at TIMESTAMPTZ)
  INDEX: (regime, status), (status)
  CHECK: status IN ('ACTIVE','DEGRADED','EXPIRED','FAILED','REPLACED')

--- Live Trading ---
trade_journal (id SERIAL, card_id INT, symbol TEXT,
  timestamp TIMESTAMPTZ, direction TEXT, signal_value FLOAT,
  expected_price FLOAT, actual_fill_price FLOAT,
  slippage_bps FLOAT, position_size FLOAT,
  regime_at_entry TEXT, regime_confidence FLOAT,
  switch_confidence FLOAT, pnl_pct FLOAT, hold_bars INT,
  created_at TIMESTAMPTZ)
  INDEX: (card_id, timestamp), (timestamp)

runtime_status (singleton UPSERT row:
  regime TEXT, confidence FLOAT, bars_since_switch INT,
  switch_confidence FLOAT, active_card_id INT,
  fine_regime TEXT, overlay_damper FLOAT, stale_status TEXT,
  last_bar_time TIMESTAMPTZ, today_pnl FLOAT,
  cumulative_pnl FLOAT, today_trades INT,
  open_positions JSONB, net_exposure FLOAT,
  gross_exposure FLOAT, updated_at TIMESTAMPTZ)

card_daily_stats (card_id INT, date DATE,
  daily_pnl FLOAT, trade_count INT, win_rate FLOAT, avg_slippage FLOAT)
  INDEX: (card_id, date)

--- System ---
orchestrator_state (singleton UPSERT:
  state TEXT, details_json JSONB, updated_at TIMESTAMPTZ)

orchestrator_events (id SERIAL, event_type TEXT, regime TEXT,
  details_json JSONB, created_at TIMESTAMPTZ)
  INDEX: (event_type), (created_at)

meta_champions (historical record of all deployed champions)
factor_graveyard (retired factors)
factor_ic_history (factor IC tracking over time)

================================================================================
§18 TIMELINE (wall-clock estimate)
================================================================================

Min 0:   Arena 1 fast (11 regimes parallel) + PySR background (5 concurrent)
Min 15:  Arena 1 fast complete → Arena 2 (11 regimes parallel)
Min 20:  Arena 2 complete → Arena 3 (11 regimes, full concurrency)
Min 40:  Arena 3 complete → Gates → Export cards → Paper trading starts
Hour 5:  PySR Lane B complete → Arena 2 recompress → Arena 3 warm restart (200-300 gen)
Hour 5.5: System fully operational with best possible cards

================================================================================
§19 TASK LIST
================================================================================

--- IMMEDIATE (no dependencies) ---
[C0]  arena1_fast.py — HIGHEST PRIORITY — 11 regimes parallel, batch AST, vectorized screen
[C1]  fix 29 failing tests
[C2]  arena2_compress.py — reads/writes DB, per-regime independent
[C3]  online predictor
[C4]  dashboard_server.py — reads DB, 6 endpoints
[C5]  zangetsu_bot.py — reads DB, Telegram notify only
[C13] DB migration script — create all tables in §17
[G1]  security audit
[CL1] V2 cleanup

--- AFTER C0+C1 ---
[C6]  FactorNormalizer reads factor_pool from DB
[C7]  main_loop writes runtime_status + trade_journal to DB
[C8]  predict_fine() overlay integration
[C9]  7-day replay test
[C10] rolling holdout script
[C11] high concurrency Arena 3 (batch signal + parallel rungs + vectorized prescreen)
[C12] orchestrator.py (state in DB, events in DB, crash recovery)

--- SEQUENTIAL GATES ---
AFTER C2 → [G2] audit arena2
AFTER C3 → [G3] audit predictor
AFTER C4 → [CL2] deploy dashboard
AFTER C5 → [CL3] deploy bot
AFTER Arena 3 → [G4] audit results
AFTER all → [G5] audit orchestrator → [CL5] dry run → [CL7] checklist → [CL8] launch

================================================================================
§20 RED LINES
================================================================================

Any of these = STOP and escalate:
- Data stored only on filesystem (except card.json deployment artifact)
- Arena 1 produces 0 candidates for any regime
- Arena 2 < 5 factors for any regime
- Arena 3 all fitness = -999
- Gemini security audit RED
- HOLDOUT data used in search
- Trade bypasses risk_manager
- Bot performs any action
- OOM on Alaya

================================================================================
§21 VERIFICATION CHECKLIST
================================================================================

S01: all packages importable
S02: all tests green
S03: factor_candidates >30 rows per regime
S04: factor_pool 10-20 rows per regime, pairwise corr <0.7
S05: signal_std 1-10, consistent across symbols within regime
S06: online predictor >70% accuracy, <10ms
S07: search_progress shows QD grew for ≥6/11 regimes
S08: ≥1 regime passed all 3 gates
S09: entry_threshold not all hitting upper bound
S10: card.json v3.2 schema valid
S11: 7-day replay: 0 errors, trades>0, bar<100ms, trade_journal correct in DB
S12: dashboard reads DB, 6 endpoints correct
S13: zangetsu_bot heartbeat on Telegram
S14: paper trading running, trade_journal growing
S15: orchestrator state machine tested (all transitions in DB)
S16: kill orchestrator mid-Arena3, restart, resumes from DB
S17: security audit all GREEN
S18: Arena 3 per-generation time < 2s (concurrency working)
S19: zero data on filesystem except card.json

================================================================================
END OF DOCUMENT
================================================================================
